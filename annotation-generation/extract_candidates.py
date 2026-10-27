#!/usr/bin/env python3
"""Extract reviewable term candidates from CQ question text using spaCy."""

from __future__ import annotations

import argparse
import json
import sys
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing CQ objects with a question field")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path (default: <input>.candidates.json)")
    parser.add_argument("--model", default="de_core_news_sm", help="Installed spaCy model (default: de_core_news_sm)")
    parser.add_argument(
        "--stopwords",
        type=Path,
        default=Path(__file__).with_name("stopwords.txt"),
        help="Editable UTF-8 stopword file (default: stopwords.txt beside this script)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output or args.input.with_name(f"{args.input.stem}.candidates.json")

    try:
        import spacy
    except ImportError:
        print("spaCy is required. Install it with `python -m pip install spacy`.", file=sys.stderr)
        return 2

    try:
        nlp = spacy.load(args.model)
    except OSError:
        print(
            f"Could not load spaCy model {args.model!r}. Install it with "
            f"`python -m spacy download {args.model}` or pass --model.",
            file=sys.stderr,
        )
        return 2

    try:
        records = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read input JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("Expected the input JSON root to be an array of CQ objects.", file=sys.stderr)
        return 2

    stopwords = load_stopwords(args.stopwords)
    results = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            print(f"Skipping array entry {index}: expected an object.", file=sys.stderr)
            continue
        question = record.get("question")
        if not isinstance(question, str) or not question.strip():
            print(f"Skipping array entry {index}: missing a non-empty question field.", file=sys.stderr)
            continue
        results.append(
            {
                "id": record.get("id"),
                "question": question,
                "candidates": extract_question(question, nlp, stopwords),
            }
        )

    output = {
        "source": str(args.input),
        "model": args.model,
        "stopwords": str(args.stopwords),
        "records": results,
    }
    try:
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"Could not write output JSON: {error}", file=sys.stderr)
        return 2

    print(f"Wrote candidates for {len(results)} questions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
