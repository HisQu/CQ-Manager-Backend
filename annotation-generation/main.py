#!/usr/bin/env python3
"""Run candidate extraction and lexical glossary matching as one workflow."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from candidate_extractor import extract_records, load_stopwords
from lexical_matcher import load_glossary, match_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of CQ objects with a question field")
    parser.add_argument("-o", "--output", type=Path, help="Output path (default: <input>.proposals.json)")
    parser.add_argument("--model", default="de_core_news_sm", help="Installed spaCy model")
    parser.add_argument(
        "--stopwords", type=Path, default=Path(__file__).with_name("stopwords.txt"), help="Editable stopword file"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).with_name("database") / "cq-database.sqlite",
        help="SQLite database containing glossary terms and annotations",
    )
    parser.add_argument("--project", help="Glossary project name (auto-selected when there is only one project)")
    parser.add_argument("--jw-threshold", type=float, default=0.90, help="Minimum Jaro-Winkler score for close matches")
    parser.add_argument("--jw-min-length", type=int, default=4, help="Minimum form length for fuzzy comparison")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output or args.input.with_name(f"{args.input.stem}.proposals.json")
    if not 0 <= args.jw_threshold <= 1 or args.jw_min_length < 1:
        print("Use a --jw-threshold between 0 and 1 and a --jw-min-length of at least 1.", file=sys.stderr)
        return 2

    try:
        source_records: Any = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(source_records, list):
            raise ValueError("Expected the input JSON root to be an array of CQ objects.")
        import spacy

        nlp = spacy.load(args.model)
        extraction_document = {
            "source": str(args.input),
            "model": args.model,
            "stopwords": str(args.stopwords),
            "records": extract_records(source_records, nlp, load_stopwords(args.stopwords)),
        }
        glossary = load_glossary(args.database, args.project)
        result = match_document(
            extraction_document, glossary, args.jw_threshold, args.jw_min_length, args.database
        )
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except ImportError:
        print("spaCy is required. Install it with `python -m pip install spacy`.", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not load input, spaCy model, database, or output: {error}", file=sys.stderr)
        return 2
    except (sqlite3.Error, ValueError) as error:
        print(f"Could not run the workflow: {error}", file=sys.stderr)
        return 2

    print(f"Wrote proposals for {len(result['records'])} questions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
