"""POS-based candidate extraction for CQ question text."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_stopwords(path: Path) -> set[str]:
    """Read one stopword per line; blank lines and # comments are ignored."""
    if not path.exists():
        return set()
    return {
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def trim_boundary_stopwords(span: Any, stopwords: set[str]) -> Any:
    """Trim boundary determiners and configured function words, preserving the interior."""
    start = 0
    end = len(span)
    while start < end:
        token = span[start]
        if token.pos_ != "DET" and not (
            token.text.casefold() in stopwords and token.pos_ in {"ADP", "PRON", "CCONJ", "SCONJ"}
        ):
            break
        start += 1
    while end > start:
        token = span[end - 1]
        if token.pos_ != "DET" and not (
            token.text.casefold() in stopwords and token.pos_ in {"ADP", "PRON", "CCONJ", "SCONJ"}
        ):
            break
        end -= 1
    return span[start:end]


def is_stopword_only(span: Any, stopwords: set[str]) -> bool:
    content = [token for token in span if not token.is_punct and not token.is_space]
    return not content or all(token.text.casefold() in stopwords for token in content)


def candidate_from_span(span: Any, rule: str, stopwords: set[str]) -> dict[str, Any] | None:
    span = trim_boundary_stopwords(span, stopwords)
    if not span or is_stopword_only(span, stopwords):
        return None

    return {
        "text": span.text,
        "start": span.start_char,
        "end": span.end_char,
        "lemma": " ".join(token.lemma_ for token in span if not token.is_punct),
        "rule": rule,
        "tokens": [
            {"text": token.text, "lemma": token.lemma_, "pos": token.pos_, "tag": token.tag_}
            for token in span
        ],
    }


def extract_question(question: str, nlp: Any, stopwords: set[str]) -> list[dict[str, Any]]:
    doc = nlp(question)
    found: dict[tuple[int, int], dict[str, Any]] = {}

    # Noun chunks propose nominal expressions; NER adds proper names that the parser
    # may not include in a noun chunk. Keep nested candidates for human review.
    proposals = [(chunk, "noun_chunk") for chunk in doc.noun_chunks]
    proposals.extend((entity, f"ner:{entity.label_}") for entity in doc.ents)

    for span, rule in proposals:
        if rule == "noun_chunk" and not any(token.pos_ in {"NOUN", "PROPN"} for token in span):
            continue
        candidate = candidate_from_span(span, rule, stopwords)
        if candidate is None:
            continue
        key = (candidate["start"], candidate["end"])
        if key in found:
            old_rules = found[key]["rule"].split("+")
            if rule not in old_rules:
                found[key]["rule"] += f"+{rule}"
        else:
            found[key] = candidate

    return sorted(found.values(), key=lambda item: (item["start"], item["end"], item["text"].casefold()))


def extract_records(records: list[Any], nlp: Any, stopwords: set[str]) -> list[dict[str, Any]]:
    """Extract candidates from each CQ object's question field."""
    results = []
    for record in records:
        if not isinstance(record, dict):
            continue
        question = record.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        results.append(
            {
                "id": record.get("id"),
                "question": question,
                "candidates": extract_question(question, nlp, stopwords),
            }
        )
    return results
