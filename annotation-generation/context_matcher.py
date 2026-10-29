"""Context-to-usage matching using cached Sentence Transformers embeddings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
CACHE_VERSION = 2
CONTEXT_STRATEGY = "Full question with candidate and annotation text retained (v2)"


def _cache_key(context: str) -> str:
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


def _load_cache(path: Path, project: str, model_name: str) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if (
        not isinstance(payload, dict)
        or payload.get("cache_version") != CACHE_VERSION
        or payload.get("project") != project
        or payload.get("model") != model_name
        or payload.get("context_strategy") != CONTEXT_STRATEGY
        or not isinstance(payload.get("embeddings"), dict)
    ):
        return {}
    return payload["embeddings"]


def _save_cache(path: Path, project: str, model_name: str, embeddings: dict[str, list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_version": CACHE_VERSION,
        "project": project,
        "model": model_name,
        "context_strategy": CONTEXT_STRATEGY,
        "embeddings": embeddings,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def _context_index(glossary: dict[str, Any]) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for term in glossary["terms"]:
        for annotation in term["annotations"]:
            question = annotation["question"]
            contexts.append(
                {
                    "term_id": term["id"],
                    "term": term["label"],
                    "context": question,
                    "key": _cache_key(question),
                    "annotation": annotation,
                }
            )
    return contexts


def _embed_missing(
    contexts: dict[str, str],
    cached: dict[str, list[float]],
    model_name: str,
    batch_size: int,
) -> dict[str, list[float]]:
    missing = [(key, context) for key, context in contexts.items() if key not in cached]
    if not missing:
        return cached

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise ImportError(
            "Broader context matching requires sentence-transformers. Add it with `uv add sentence-transformers`."
        ) from error

    model = SentenceTransformer(model_name)
    # E5 uses the same query prefix for both sides of symmetric similarity tasks.
    prefix = "query: " if model_name.startswith("intfloat/multilingual-e5") else ""
    texts = [f"{prefix}{context}" for _, context in missing]
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    for (key, _), vector in zip(missing, vectors, strict=True):
        cached[key] = vector.astype(np.float32).tolist()
    return cached


def match_contexts(
    document: dict[str, Any],
    glossary: dict[str, Any],
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    threshold: float = 0.92,
    top_k: int = 3,
    batch_size: int = 32,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Add broader context-to-usage rankings for candidates without narrow matches."""
    result = dict(document)
    result["records"] = []
    matcher_metadata = result.get("matcher")
    if isinstance(matcher_metadata, dict):
        matcher_metadata = dict(matcher_metadata)
        statuses = list(matcher_metadata.get("statuses", []))
        if "broad_embedding" not in statuses:
            statuses.append("broad_embedding")
        matcher_metadata["statuses"] = statuses
        result["matcher"] = matcher_metadata
    pending: list[dict[str, Any]] = []
    for record_index, record in enumerate(document.get("records", [])):
        new_candidates = []
        for candidate_index, candidate in enumerate(record.get("candidates", [])):
            narrow = candidate.get("match", {})
            if narrow.get("status") != "none":
                new_candidates.append(candidate)
            else:
                question = record["question"]
                pending.append(
                    {
                        "record_index": record_index,
                        "candidate_index": candidate_index,
                        "context": question,
                        "key": _cache_key(question),
                    }
                )
                new_candidates.append(candidate)
        result["records"].append({**record, "candidates": new_candidates})

    reference_contexts = _context_index(glossary)
    if not pending:
        result["context_matcher"] = _metadata(model_name, threshold, top_k, cache_path)
        return result
    if not reference_contexts:
        result["context_matcher"] = _metadata(model_name, threshold, top_k, cache_path)
        return result

    path = cache_path or Path(__file__).with_name(".cache") / "annotation-context-embeddings.json"
    cached = _load_cache(path, glossary["project"], model_name)
    contexts_to_embed = {_cache_key(item["context"]): item["context"] for item in reference_contexts}
    contexts_to_embed.update({_cache_key(item["context"]): item["context"] for item in pending})
    cached = _embed_missing(contexts_to_embed, cached, model_name, batch_size)
    # Drop stale reference entries so removed/changed annotations do not accumulate.
    active_reference_keys = {item["key"] for item in reference_contexts}
    active_run_keys = active_reference_keys | {item["key"] for item in pending}
    run_embeddings = {key: vector for key, vector in cached.items() if key in active_run_keys}
    persistent_embeddings = {key: vector for key, vector in cached.items() if key in active_reference_keys}
    _save_cache(path, glossary["project"], model_name, persistent_embeddings)

    reference_matrix = np.asarray([run_embeddings[item["key"]] for item in reference_contexts], dtype=np.float32)
    candidate_matrix = np.asarray([run_embeddings[item["key"]] for item in pending], dtype=np.float32)
    similarities = candidate_matrix @ reference_matrix.T

    references_by_term: dict[str, list[int]] = {}
    term_labels: dict[str, str] = {}
    for reference_index, item in enumerate(reference_contexts):
        references_by_term.setdefault(item["term_id"], []).append(reference_index)
        term_labels[item["term_id"]] = item["term"]

    for candidate_row, item in enumerate(pending):
        term_matches = []
        for term_id, reference_indices in references_by_term.items():
            ranked_indices = sorted(
                reference_indices,
                key=lambda index: float(similarities[candidate_row, index]),
                reverse=True,
            )[:top_k]
            scores = [float(similarities[candidate_row, index]) for index in ranked_indices]
            score = sum(scores) / len(scores)
            evidence = []
            for index, example_score in zip(ranked_indices, scores, strict=True):
                annotation = reference_contexts[index]["annotation"]
                evidence.append(
                    {
                        "score": round(example_score, 4),
                        "annotated_text": annotation["text"],
                        "question": annotation["question"],
                    }
                )
            term_matches.append(
                {
                    "term": term_labels[term_id],
                    "score": score,
                    "example_count": len(reference_indices),
                    "evidence": evidence,
                }
            )
        term_matches.sort(key=lambda match: (-match["score"], match["term"].casefold()))
        if term_matches and term_matches[0]["score"] >= threshold:
            candidate = result["records"][item["record_index"]]["candidates"][item["candidate_index"]]
            best_match = {**term_matches[0], "score": round(term_matches[0]["score"], 4)}
            candidate["match"] = {"status": "broad_embedding", "matches": [best_match]}

    result["context_matcher"] = _metadata(model_name, threshold, top_k, path)
    return result


def _metadata(
    model_name: str,
    threshold: float,
    top_k: int,
    cache_path: Path | None,
) -> dict[str, Any]:
    return {
        "model": model_name,
        "similarity": "cosine",
        "context_strategy": CONTEXT_STRATEGY,
        "candidate_prefix": "query: " if model_name.startswith("intfloat/multilingual-e5") else "",
        "annotation_prefix": "query: " if model_name.startswith("intfloat/multilingual-e5") else "",
        "stopwords_removed": False,
        "threshold": threshold,
        "top_k_examples": top_k,
        "cache": (
            str(cache_path)
            if cache_path is not None
            else "annotation-generation/.cache/annotation-context-embeddings.json"
        ),
    }
