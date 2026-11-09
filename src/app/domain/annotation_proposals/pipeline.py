"""Reusable, read-only candidate extraction and glossary matching pipeline."""

from __future__ import annotations

import os
import threading
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import spacy

from .candidate_extractor import extract_question, load_stopwords
from .context_matcher import DEFAULT_EMBEDDING_MODEL, match_contexts
from .lexical_matcher import match_document

DEFAULT_SPACY_MODEL = os.getenv("CQ_ANNOTATION_SPACY_MODEL", "de_core_news_sm")
DEFAULT_CONTEXT_THRESHOLD = float(os.getenv("CQ_ANNOTATION_CONTEXT_THRESHOLD", "0.85"))
DEFAULT_LEXICAL_THRESHOLD = float(os.getenv("CQ_ANNOTATION_LEXICAL_THRESHOLD", "0.90"))
DEFAULT_CONTEXT_MODEL = os.getenv("CQ_ANNOTATION_CONTEXT_MODEL", DEFAULT_EMBEDDING_MODEL)
DEFAULT_CONTEXT_CACHE = Path(
    os.getenv("CQ_ANNOTATION_CONTEXT_CACHE", "/tmp/cq-annotation-context-embeddings.json")
)
STOPWORDS_PATH = Path(__file__).with_name("stopwords.txt")
_PIPELINE_LOCK = threading.Lock()


@lru_cache(maxsize=2)
def load_language_model(model_name: str = DEFAULT_SPACY_MODEL) -> Any:
    """Load and cache the configured spaCy pipeline."""
    return spacy.load(model_name)


def normalize_unmatched_term(span: str) -> str:
    """
    Trim outer whitespace and punctuation, preserving punctuation inside terms.
    The output of this will later be the title of a new glossary term.
    """
    start, end = 0, len(span)
    while start < end and (span[start].isspace() or unicodedata.category(span[start]).startswith("P")):
        start += 1
    while end > start and (span[end - 1].isspace() or unicodedata.category(span[end - 1]).startswith("P")):
        end -= 1
    return span[start:end]


def to_utf16_offset(text: str, python_offset: int) -> int:
    """Convert a Python character index to a browser/JavaScript UTF-16 code-unit index."""
    return len(text[:python_offset].encode("utf-16-le", errors="surrogatepass")) // 2


def generate_proposals(
    text: str,
    glossary: dict[str, Any],
    question_id: str,
    *,
    excluded_spans: list[tuple[int, int]] | None = None,
    nlp: Any | None = None,
    context_model: str = DEFAULT_CONTEXT_MODEL,
    context_threshold: float = DEFAULT_CONTEXT_THRESHOLD,
    lexical_threshold: float = DEFAULT_LEXICAL_THRESHOLD,
    cache_path: Path = DEFAULT_CONTEXT_CACHE,
) -> dict[str, Any]:
    """Analyze one question and return candidates with ranked glossary suggestions.
    For this, we first extract candidates from the question text based on POS-Tags, then
    match them against the glossary using lexical similarity first and context-based 
    similarity via embedding as fallback. If no glossary term is found, we return a normalized 
    version of the candidate as a suggestion for a new term.
    """
    nlp = nlp or load_language_model()
    excluded_span_set = set(excluded_spans or [])
    # prevent concurrent access to the spaCy model and the context embedding model, which are not thread-safe
    with _PIPELINE_LOCK:
        document = {
            "source": "api",
            "model": DEFAULT_SPACY_MODEL,
            "records": [
                {
                    "id": question_id,
                    "question": text,
                    "candidates": [
                        candidate
                        for candidate in extract_question(text, nlp, load_stopwords(STOPWORDS_PATH))
                        if (
                            to_utf16_offset(text, candidate["start"]),
                            to_utf16_offset(text, candidate["end"]),
                        )
                        not in excluded_span_set
                    ],
                }
            ],
        }
        document = match_document(
            document,
            glossary,
            threshold=lexical_threshold,
            minimum_length=4,
            database_path=Path("."),
        )
        document = match_contexts(
            document,
            glossary,
            nlp,
            model_name=context_model,
            threshold=context_threshold,
            top_k=3,
            batch_size=32,
            cache_path=cache_path,
        )

    terms_by_label = {term["label"]: term for term in glossary["terms"]}
    proposals = []
    for candidate in document["records"][0]["candidates"]:
        status = candidate["match"]["status"]
        matches = candidate["match"].get("matches", [])
        if matches:
            chosen = terms_by_label[matches[0]["term"]]
            suggestion = {
                "id": chosen["id"],
                "content": chosen["label"],
                "definition": chosen.get("definition"),
                "conceptIri": chosen.get("concept_iri"),
                "isNew": False,
            }
        else:
            normalized = normalize_unmatched_term(candidate["text"])
            suggestion = {
                "id": None,
                "content": normalized,
                "definition": None,
                "conceptIri": None,
                "isNew": True,
            }
        proposals.append(
            {
                **candidate,
                "start": to_utf16_offset(text, candidate["start"]),
                "end": to_utf16_offset(text, candidate["end"]),
                "match_status": status,
                "matches": matches,
                "suggested_term": suggestion,
            }
        )

    return {
        "candidates": proposals,
        "matcher": {key: value for key, value in document.get("matcher", {}).items() if key != "database"},
        "context_matcher": document.get("context_matcher", {}),
    }
