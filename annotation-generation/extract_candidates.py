#!/usr/bin/env python3
"""Step 1 CLI: extract POS-based candidates from CQ question text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from candidate_extractor import extract_records, load_stopwords


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of CQ objects with a question field")
    parser.add_argument("-o", "--output", type=Path, help="Output path (default: <input>.candidates.json)")
    parser.add_argument("--model", default="de_core_news_sm", help="Installed spaCy model")
    parser.add_argument(
        "--stopwords", type=Path, default=Path(__file__).with_name("stopwords.txt"), help="Editable stopword file"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output or args.input.with_name(f"{args.input.stem}.candidates.json")

    try:
        records: Any = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read input JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("Expected the input JSON root to be an array of CQ objects.", file=sys.stderr)
        return 2

    try:
        import spacy

        nlp = spacy.load(args.model)
    except ImportError:
        print("spaCy is required. Install it with `python -m pip install spacy`.", file=sys.stderr)
        return 2
    except OSError:
        print(f"Could not load spaCy model {args.model!r}. Install it with `python -m spacy download {args.model}`.", file=sys.stderr)
        return 2

    result = {
        "source": str(args.input),
        "model": args.model,
        "stopwords": str(args.stopwords),
        "records": extract_records(records, nlp, load_stopwords(args.stopwords)),
    }
    try:
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"Could not write output JSON: {error}", file=sys.stderr)
        return 2

    print(f"Wrote candidates for {len(result['records'])} questions to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
