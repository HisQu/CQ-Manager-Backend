# CQ term candidate workflow

The workflow reads the `question` field from a JSON array of CQ objects and
proposes candidate annotations. It extracts noun phrases and named entities,
tries narrow lexical matching against the selected project's current glossary
annotations and labels, then ranks broader matches by comparing full question
contexts. It only reads the SQLite database. It does not save annotations or
create terms.

## Modules and entry points

- `candidate_extractor.py` contains the spaCy POS, noun-chunk, and NER rules.
- `lexical_matcher.py` loads glossary terms and current annotations, then
  assigns `exact_text`, `exact_glossary`, `close_text`, `close_glossary`, or
  `none` results.
- `context_matcher.py` embeds full questions with the original term text using
  Sentence Transformers, caches annotation-context embeddings, and adds
  broader context-to-usage rankings.
- `main.py` runs extraction and both matching stages in memory.
- `match_candidates.py` runs only the narrow lexical matcher on an existing
  candidate JSON file.

The German spaCy model is the default. Install it in the environment used to
run the scripts if it is not already available:

```sh
uv run python -m spacy download de_core_news_sm
```

The default embedding model is `intfloat/multilingual-e5-small`. Its files are
downloaded the first time it is used and then reused from the local model
cache. Other potentially relevant models are listed below and can be selected
with `--embedding-model`:

| Model | Notes |
| --- | --- |
| [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) | Default; multilingual retrieval model. Both sides use the `query:` prefix for symmetric similarity. |
| [`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) | Smaller, straightforward multilingual sentence-similarity alternative; no E5 prefix is added. |
| [`sentence-transformers/distiluse-base-multilingual-cased-v2`](https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2) | Another multilingual sentence-embedding model to compare in later trials. |

All question embeddings in one run use the same configured model. Changing the
model or context strategy invalidates the annotation embedding cache automatically.

## Full workflow

Run from this directory:

```sh
uv run python main.py cqs.json -o cqs.proposals.json
```

The database defaults to `database/cq-database.sqlite`, and the stopword file
defaults to `stopwords.txt`. When the database contains more than one project,
select one with `--project "Project name"`. The narrow matcher defaults to a
Jaro-Winkler threshold of `0.90` and a minimum comparison length of four
characters; change them with `--jw-threshold` and `--jw-min-length`.

Context matching only runs for candidates whose narrow match status is
`none`. It embeds the complete, original question with the candidate text
retained. Reference embeddings likewise retain the annotated text in the full
question. Stopwords are kept to preserve grammar; the configured stopword file
is still used by candidate extraction. Identical questions are embedded only
once. All unresolved candidates in the same question therefore receive the
same broader ranking. This also means that different terms annotated in the
same reference question share that question's embedding.

The candidate context is compared with every annotated context, grouped by
glossary term. The term score is the mean of its best `k` context similarities
(default `k=3`, or all available examples if fewer than three). Similarities
are cosine scores from normalized embeddings. The single highest-scoring term
and its best supporting examples are included when its score reaches
`--context-threshold` (default `0.92`). Otherwise the match status remains
`none`.

Step 1 reads only each record's `question` field. Candidates retain their
original surface text and character offsets. Noun chunks must contain a
`NOUN` or `PROPN`; boundary determiners (`DET`) are trimmed automatically, and
other configured function words are trimmed only when present in
`stopwords.txt`. Nested candidates are retained, while duplicate spans from
noun chunking and NER are merged.

Step 2 compares normalized candidate text with current annotated surface forms
(`exact_text`), then glossary labels (`exact_glossary`). If neither is exact,
Jaro-Winkler compares the candidate with those lexical forms. Comparison
normalization uses Unicode NFKC, case folding, and whitespace collapsing, but
the original candidate text is preserved. Close comparisons require the same
number of whitespace-separated words. Match output omits internal term and
question IDs; candidate offsets remain on each candidate.

Run with the default E5 model:

```sh
uv run python main.py cqs.json \
  --context-threshold 0.92 \
  --context-top-k 3 \
  --embedding-batch-size 32 \
  -o cqs.proposals.json
```

The local annotation-context cache defaults to
`annotation-generation/.cache/annotation-context-embeddings.json`. It reuses
unchanged annotated-context vectors across runs. New candidate contexts are
embedded for the current run; if an accepted annotation later becomes a
reference example, its context is added to the cache. The cache is local and
should not be committed. Override its path with `--embedding-cache`.
The former masked-context cache is invalidated automatically and rebuilt on
the next run.

## Output

Every candidate retains its original surface text and character offsets.
`match.status` classifies the result as `exact_text`, `exact_glossary`,
`close_text`, `close_glossary`, `broad_embedding`, or `none`. Exact and close
results keep their existing `matches` entries. A `broad_embedding` result uses
the same `matches` field and contains only the single highest-scoring glossary
term, its aggregated score, the number of available examples, and its
supporting annotated text, questions, and example scores. The redundant
`context` field is omitted because the embedding input is the question itself.
The threshold is applied to decide
between `broad_embedding` and `none`, but is not repeated on individual
matches. Top-level `context_matcher` metadata records the model, context
strategy, configured threshold, evidence count, and cache path. Embedding
vectors are not written to the proposal JSON.

## Run narrow matching separately

`match_candidates.py` remains useful for step 2 without loading an embedding
model:

```sh
uv run python match_candidates.py cqs.candidates.json -o cqs.matched.json
```

The full `main.py` workflow is required to produce broader context rankings.
