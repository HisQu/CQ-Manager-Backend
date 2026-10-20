import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

sys.path.append("src/app/")

from lib.orm import AsyncSqlPlugin

# `passage` as created before annotation versioning: shared between questions, unique per content and term.
LEGACY_PASSAGE = """
CREATE TABLE passage (
    id BINARY(16) NOT NULL,
    content VARCHAR NOT NULL,
    term_id BINARY(16) NOT NULL,
    sa_orm_sentinel INTEGER,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT pk_passage PRIMARY KEY (id),
    CONSTRAINT uq_passage_content UNIQUE (content, term_id)
)
"""
INSERT = (
    "INSERT INTO passage (id, content, term_id, created_at, updated_at{extra}) "
    "VALUES (:id, 'Pfründen', X'01', '2026-01-01', '2026-01-01'{values})"
)


@pytest.mark.parametrize("columns_added_before", [False, True])
def test_legacy_passage_table_accepts_the_same_passage_in_several_annotation_versions(
    tmp_path: Path, columns_added_before: bool
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text(LEGACY_PASSAGE))
        if columns_added_before:
            for column in ('annotation_version_id BINARY(16)', '"start" INTEGER', '"end" INTEGER'):
                connection.execute(text(f"ALTER TABLE passage ADD COLUMN {column}"))
        connection.execute(text(INSERT.format(extra="", values="")), {"id": b"legacy"})

        AsyncSqlPlugin._rebuild_legacy_passage_table(connection)
        AsyncSqlPlugin._rebuild_legacy_passage_table(connection)  # a second startup changes nothing

        assert {"annotation_version_id", "start", "end"} <= {c["name"] for c in inspect(connection).get_columns("passage")}
        assert connection.execute(text("SELECT id FROM passage")).scalars().all() == [b"legacy"]
        insert = INSERT.format(extra=', annotation_version_id, start, "end"', values=", :version, 36, 44")
        connection.execute(text(insert), {"id": b"first", "version": b"v1"})
        connection.execute(text(insert), {"id": b"second", "version": b"v2"})
        assert connection.execute(text("SELECT count(*) FROM passage")).scalar() == 3
