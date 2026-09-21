"""A minimal in-memory stand-in for the supabase-py fluent query API, just
enough of it to unit-test storage/supabase_store.py and app/queries.py
without a live Supabase project. Not a general-purpose Postgres emulator:
no real joins, no SQL — just enough chained .select/.eq/.order/.range/
.single/.insert/.upsert/.update/.execute to exercise our call sites.
"""
from __future__ import annotations


class _Result:
    def __init__(self, data):
        self.data = data


class _SelectQuery:
    def __init__(self, table: "FakeTable", columns: str):
        self.table = table
        self.columns = columns
        self._filters: list[tuple[str, object]] = []
        self._order = None
        self._limit = None
        self._range = None
        self._single = False

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        rows = [dict(r) for r in self.table.rows if all(r.get(c) == v for c, v in self._filters)]
        if self._order:
            col, desc = self._order
            rows.sort(key=lambda r: r.get(col), reverse=desc)
        if self._range is not None:
            start, end = self._range
            rows = rows[start : end + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        if self._single:
            return _Result(rows[0] if rows else None)
        return _Result(rows)


class _UpdateQuery:
    def __init__(self, table: "FakeTable", payload: dict):
        self.table = table
        self.payload = payload
        self._filters: list[tuple[str, object]] = []

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def execute(self):
        matched = [r for r in self.table.rows if all(r.get(c) == v for c, v in self._filters)]
        for r in matched:
            r.update(self.payload)
        return _Result(matched)


class _InsertQuery:
    def __init__(self, table: "FakeTable", payload):
        self.table = table
        self.payload = payload

    def execute(self):
        self.table.insert_calls += 1
        rows = self.payload if isinstance(self.payload, list) else [self.payload]
        created = []
        for r in rows:
            row = dict(r)
            row.setdefault("id", self.table._new_id())
            self.table.rows.append(row)
            created.append(row)
        return _Result(created)


class _UpsertQuery:
    def __init__(self, table: "FakeTable", payload, on_conflict: str | None):
        self.table = table
        self.payload = payload
        self.on_conflict = on_conflict

    def execute(self):
        self.table.upsert_calls += 1
        keys = [k.strip() for k in self.on_conflict.split(",")] if self.on_conflict else []
        rows = self.payload if isinstance(self.payload, list) else [self.payload]
        result = []
        for r in rows:
            existing = None
            if keys:
                existing = next(
                    (row for row in self.table.rows if all(row.get(k) == r.get(k) for k in keys)), None
                )
            if existing is not None:
                existing.update(r)
                result.append(existing)
            else:
                row = dict(r)
                row.setdefault("id", self.table._new_id())
                self.table.rows.append(row)
                result.append(row)
        return _Result(result)


class FakeTable:
    def __init__(self, name: str):
        self.name = name
        self.rows: list[dict] = []
        self.insert_calls = 0
        self.upsert_calls = 0
        self._next_id = 0

    def _new_id(self) -> str:
        self._next_id += 1
        return f"{self.name}-{self._next_id}"

    def select(self, columns: str = "*"):
        return _SelectQuery(self, columns)

    def insert(self, payload):
        return _InsertQuery(self, payload)

    def upsert(self, payload, on_conflict: str | None = None):
        return _UpsertQuery(self, payload, on_conflict)

    def update(self, payload):
        return _UpdateQuery(self, payload)


class FakeClient:
    def __init__(self):
        self._tables: dict[str, FakeTable] = {}

    def table(self, name: str) -> FakeTable:
        if name not in self._tables:
            self._tables[name] = FakeTable(name)
        return self._tables[name]
