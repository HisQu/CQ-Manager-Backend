"""Read-only glossary lookup and exact / Jaro-Winkler candidate matching."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any
from uuid import UUID

from jarowinkler import jarowinkler_similarity


def normalize_for_match(text: str) -> str:
    """Light comparison normalization; the stored/displayed candidate stays unchanged."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def uuid_text(value: bytes) -> str:
    return str(UUID(bytes=value))


def load_glossary(database_path: Path, project_name: str | None) -> dict[str, Any]:
    """Read project terms and their current annotation examples from SQLite, read-only."""
    uri = f"file:{database_path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.row_factory = sqlite3.Row
        projects = connection.execute("SELECT id, name FROM project ORDER BY name").fetchall()
        if project_name is None:
            if len(projects) != 1:
                names = ", ".join(row["name"] for row in projects) or "(none)"
                raise ValueError(f"Database has {len(projects)} projects ({names}); select one with --project.")
            project = projects[0]
        else:
            project = next((row for row in projects if row["name"] == project_name), None)
            if project is None:
                raise ValueError(f"Project {project_name!r} was not found in {database_path}.")

        term_rows = connection.execute(
            "SELECT id, content FROM term WHERE project_id = ? ORDER BY content", (project["id"],)
        ).fetchall()
        terms: dict[bytes, dict[str, Any]] = {
            row["id"]: {
                "id": uuid_text(row["id"]),
                "label": row["content"],
                "normalized_label": normalize_for_match(row["content"]),
                "annotations": [],
            }
            for row in term_rows
        }

        # Match the backend's definition of current annotations: current question
        # revision, then the latest annotation snapshot attached to that revision.
        annotation_rows = connection.execute(
            """
            WITH current_revisions AS (
                SELECT v.id AS version_id, q.id AS question_id, q.question
                FROM question q
                JOIN version v
                  ON v.question_id = q.id AND v.version_number = q.version_number
                WHERE q.deleted_at IS NULL
            ), latest_annotation_versions AS (
                SELECT av.question_version_id, MAX(av.version_number) AS version_number
                FROM annotation_version av
                JOIN current_revisions cr ON cr.version_id = av.question_version_id
                GROUP BY av.question_version_id
            )
            SELECT p.term_id, p.content AS annotated_text, p.start AS annotation_start,
                   p.end AS annotation_end, q.id AS question_id, q.question AS question_text
            FROM latest_annotation_versions latest
            JOIN annotation_version av
              ON av.question_version_id = latest.question_version_id
             AND av.version_number = latest.version_number
            JOIN version v ON v.id = av.question_version_id
            JOIN question q ON q.id = v.question_id
            JOIN passage p ON p.annotation_version_id = av.id
            JOIN term t ON t.id = p.term_id
            WHERE t.project_id = ?
            ORDER BY p.content, t.content
            """,
            (project["id"],),
        ).fetchall()
        for row in annotation_rows:
            term = terms.get(row["term_id"])
            if term is not None:
                term["annotations"].append(
                    {
                        "text": row["annotated_text"],
                        "normalized_text": normalize_for_match(row["annotated_text"]),
                        "start": row["annotation_start"],
                        "end": row["annotation_end"],
                        "question_id": uuid_text(row["question_id"]),
                        "question": row["question_text"],
                    }
                )
        return {"project": project["name"], "terms": list(terms.values())}
    finally:
        connection.close()


def match_candidate(
    candidate: dict[str, Any],
    terms: list[dict[str, Any]],
    threshold: float = 0.90,
    minimum_length: int = 4,
) -> dict[str, Any]:
    """Classify a candidate as exact, close, or none, retaining term evidence."""
    normalized_candidate = normalize_for_match(candidate["text"])

    exact_annotation_matches: dict[str, dict[str, Any]] = {}
    for term in terms:
        for annotation in term["annotations"]:
            if normalized_candidate == annotation["normalized_text"] and term["id"] not in exact_annotation_matches:
                exact_annotation_matches[term["id"]] = {
                    "term": term["label"],
                    "matched_text": annotation["text"],
                    "question": annotation["question"],
                }
    if exact_annotation_matches:
        return {"status": "exact_text", "matches": list(exact_annotation_matches.values())}

    exact_label_matches = [
        {"term": term["label"], "matched_text": term["label"]}
        for term in terms
        if normalized_candidate == term["normalized_label"]
    ]
    if exact_label_matches:
        return {"status": "exact_glossary", "matches": exact_label_matches}

    if len(normalized_candidate) < minimum_length:
        return {"status": "none", "matches": []}

    close_matches = []
    for term in terms:
        scores: dict[tuple[str, str], dict[str, Any]] = {}
        lexical_forms = [("glossary_label", term["label"], term["normalized_label"], None)]
        lexical_forms.extend(
            ("annotated_text", item["text"], item["normalized_text"], item)
            for item in term["annotations"]
        )
        for source, surface, normalized_surface, annotation in lexical_forms:
            if len(normalized_surface) < minimum_length:
                continue
            # Character-level similarity across different word counts often
            # overvalues shared prefixes in unrelated single- and multiword forms.
            if len(normalized_candidate.split()) != len(normalized_surface.split()):
                continue
            score = jarowinkler_similarity(normalized_candidate, normalized_surface)
            if score < threshold:
                continue
            evidence = {"source": source, "matched_text": surface, "score": round(score, 4)}
            if annotation is not None:
                evidence.update(
                    {
                        "annotation_start": annotation["start"],
                        "annotation_end": annotation["end"],
                        "question_id": annotation["question_id"],
                        "question": annotation["question"],
                    }
                )
            scores[(source, surface)] = evidence

        if scores:
            best_score = max(item["score"] for item in scores.values())
            best_evidence = min(
                (item for item in scores.values() if item["score"] == best_score),
                key=lambda item: (item["source"], item["matched_text"].casefold()),
            )
            compact_match = {
                "status": "close_text" if best_evidence["source"] == "annotated_text" else "close_glossary",
                "term": term["label"],
                "score": best_score,
                "matched_text": best_evidence["matched_text"],
            }
            if "question" in best_evidence:
                compact_match["question"] = best_evidence["question"]
            close_matches.append(compact_match)

    close_matches.sort(key=lambda item: (-item["score"], item["term"].casefold()))
    if close_matches:
        return {"status": close_matches[0]["status"], "matches": close_matches}
    return {"status": "none", "matches": []}


def match_document(
    document: dict[str, Any],
    glossary: dict[str, Any],
    threshold: float,
    minimum_length: int,
    database_path: Path,
) -> dict[str, Any]:
    """Return a copy of an extraction document enriched with matcher results."""
    result = dict(document)
    result["records"] = []
    for record in document.get("records", []):
        result["records"].append(
            {
                **record,
                "candidates": [
                    {
                        **candidate,
                        "match": match_candidate(candidate, glossary["terms"], threshold, minimum_length),
                    }
                    for candidate in record.get("candidates", [])
                ],
            }
        )

    result.update(
        {
            "database": str(database_path),
            "project": glossary["project"],
            "matcher": {
                "exact_normalization": "Unicode NFKC, casefold, collapse whitespace",
                "close_similarity": "Jaro-Winkler",
                "jaro_winkler_threshold": threshold,
                "jaro_winkler_min_length": minimum_length,
                "close_match_requires_same_word_count": True,
                "statuses": ["exact_text", "exact_glossary", "close_text", "close_glossary", "none"],
            },
        }
    )
    return result
