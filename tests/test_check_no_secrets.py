from scripts import check_no_secrets as cns


class _FakeCompletedProcess:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def test_blocks_nested_env_file_not_just_root():
    assert any(p.search("config/.env") for p in cns.BLOCKED_PATH_PATTERNS)
    assert any(p.search(".env") for p in cns.BLOCKED_PATH_PATTERNS)
    assert any(p.search("deploy/.env.production") for p in cns.BLOCKED_PATH_PATTERNS)


def test_env_example_is_allowed_at_any_depth():
    assert cns._is_allowed_env_file(".env.example")
    assert cns._is_allowed_env_file("config/.env.example")


def test_secret_scan_reads_staged_content_not_working_tree(monkeypatch):
    # A secret removed from disk but still staged must still be caught —
    # scanning the working tree instead of the index would miss it.
    # Built at runtime (not a literal) so this test file doesn't itself trip
    # the very scanner it's testing when *this* file gets committed.
    fake_key = "AIzaSy" + "A" * 20
    monkeypatch.setattr(cns, "staged_files", lambda: ["app/config_snippet.py"])

    def fake_run(cmd, **kwargs):
        assert cmd[:2] == ["git", "show"]
        assert cmd[2] == ":app/config_snippet.py"
        return _FakeCompletedProcess(stdout=f'API_KEY = "{fake_key}"')

    monkeypatch.setattr(cns.subprocess, "run", fake_run)

    assert cns.main() == 1


def test_secret_scan_passes_when_staged_content_is_clean(monkeypatch):
    monkeypatch.setattr(cns, "staged_files", lambda: ["app/config_snippet.py"])
    monkeypatch.setattr(
        cns.subprocess, "run", lambda cmd, **kwargs: _FakeCompletedProcess(stdout="API_KEY = None")
    )

    assert cns.main() == 0
