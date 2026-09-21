"""Guards against zip-bomb docx/xlsx attachments: the file-size cap in
readers/filetype.py only bounds the *compressed* upload, not what it
would decompress to."""
import io
import zipfile

import defusedxml

# openpyxl and python-docx both parse XML via the stdlib's ElementTree with
# no entity-expansion guard of their own. defuse_stdlib() patches the
# stdlib's XML modules process-wide against XML bombs (billion-laughs,
# quadratic blowup, external entity/DTD expansion) — the officially
# recommended way to secure third-party libraries that use stdlib XML
# internally without a hook to swap parsers.
defusedxml.defuse_stdlib()

MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_ZIP_ENTRIES = 10_000


class UnsafeZipError(Exception):
    pass


def check_zip_bomb_safety(
    data: bytes,
    max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES,
    max_entries: int = MAX_ZIP_ENTRIES,
) -> None:
    """Raise UnsafeZipError before anything opens `data` as docx/xlsx if its
    declared entry count or total uncompressed size looks like a bomb."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > max_entries:
                raise UnsafeZipError(f"zip has too many entries: {len(infos)} > {max_entries}")
            total_uncompressed = sum(i.file_size for i in infos)
            if total_uncompressed > max_uncompressed_bytes:
                raise UnsafeZipError(
                    f"zip declares {total_uncompressed} uncompressed bytes > {max_uncompressed_bytes}"
                )
    except zipfile.BadZipFile as e:
        raise UnsafeZipError("not a valid zip file") from e
