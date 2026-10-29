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
from context_matcher import DEFAULT_EMBEDDING_MODEL, match_contexts
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
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="Sentence Transformers model used for context matching",
    )
    parser.add_argument(
        "--context-threshold",
        type=float,
        default=0.92,
        help="Minimum cosine score for a broader embedding match",
    )
    parser.add_argument("--context-top-k", type=int, default=3, help="Annotated contexts averaged per glossary term")
    parser.add_argument("--embedding-batch-size", type=int, default=32, help="Texts embedded per model batch")
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        help="Path for the local annotation-context embedding cache (default: annotation-generation/.cache)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output or args.input.with_name(f"{args.input.stem}.proposals.json")
    if (
        not 0 <= args.jw_threshold <= 1
        or args.jw_min_length < 1
        or not 0 <= args.context_threshold <= 1
        or args.context_top_k < 1
        or args.embedding_batch_size < 1
    ):
        print(
            "Use similarity thresholds between 0 and 1 and positive values for minimum length, context k, and batch size.",
            file=sys.stderr,
        )
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
        result = match_contexts(
            result,
            glossary,
            model_name=args.embedding_model,
            threshold=args.context_threshold,
            top_k=args.context_top_k,
            batch_size=args.embedding_batch_size,
            cache_path=args.embedding_cache,
        )
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except ImportError as error:
        print(f"A required Python dependency is missing: {error}", file=sys.stderr)
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
