#!/usr/bin/env python3
"""Step 2 CLI: assign exact, close, or no-match proposals to extracted candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from lexical_matcher import load_glossary, match_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Candidate JSON produced by extract_candidates.py")
    parser.add_argument("-o", "--output", type=Path, help="Output path (default: <input>.matched.json)")
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
    output_path = args.output or args.input.with_name(f"{args.input.stem}.matched.json")
    if not 0 <= args.jw_threshold <= 1 or args.jw_min_length < 1:
        print("Use a --jw-threshold between 0 and 1 and a --jw-min-length of at least 1.", file=sys.stderr)
        return 2

    try:
        document: Any = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("records"), list):
            raise ValueError("Expected candidate JSON with a records array.")
        glossary = load_glossary(args.database, args.project)
        result = match_document(document, glossary, args.jw_threshold, args.jw_min_length, args.database)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, sqlite3.Error, ValueError) as error:
        print(f"Could not run lexical matcher: {error}", file=sys.stderr)
        return 2

    print(f"Wrote lexical match proposals to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
