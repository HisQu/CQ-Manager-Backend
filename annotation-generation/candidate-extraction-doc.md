# CQ term candidate workflow

The workflow reads the `question` field from a JSON array of CQ objects,
proposes noun phrases and named entities, and matches each candidate against
the selected project's glossary labels and current annotated text. It only
reads the SQLite database. It does not save annotations or create terms.

## Modules and command-line entry points

- `candidate_extractor.py` contains the spaCy-based POS and noun-chunk rules.
- `lexical_matcher.py` loads the glossary and current annotations, then assigns
  `exact`, `close`, or `none` match results. Jaro-Winkler comes from the
  installed `jarowinkler` package.
- `extract_candidates.py` runs step 1 by itself.
- `match_candidates.py` runs step 2 on a step 1 JSON file.
- `main.py` runs both steps in memory as the full workflow.

The German spaCy model is the default. Install it in the environment used to
run the scripts if it is not already available:

```sh
python -m spacy download de_core_news_sm
```

## Full workflow

Run from this directory:

```sh
python main.py cqs.json -o cqs.proposals.json
```

The database defaults to `database/cq-database.sqlite`, and the stopword file
defaults to `stopwords.txt`. When the database contains more than one project,
select one with `--project "Project name"`. The matching defaults are a
Jaro-Winkler threshold of `0.90` and a minimum comparison length of four
characters; change them with `--jw-threshold` and `--jw-min-length`.

## Run the steps separately

```sh
python extract_candidates.py cqs.json -o cqs.candidates.json
python match_candidates.py cqs.candidates.json -o cqs.matched.json
```

Step 1 reads only each record's `question` field. Candidates retain exact
surface text and character offsets. Noun chunks must contain a `NOUN` or
`PROPN`; boundary determiners (`DET`) are trimmed automatically, and other
configured function words are trimmed only when present in `stopwords.txt`.
Nested candidates are retained, while duplicate spans produced by noun
chunking and named-entity recognition are merged.

Step 2 first compares normalized candidate text with current annotated surface
forms, then with glossary labels. If neither is exact, Jaro-Winkler compares
the candidate with those same lexical forms. Comparison normalization applies
Unicode NFKC, case folding, and whitespace collapsing, but the proposed
candidate's original text is preserved. Close comparisons require the same
number of whitespace-separated words to reduce misleading matches between
single- and multiword forms. Evidence includes the matched form and, for
annotated text, one example question per matched term. Match output omits
internal term/question IDs and annotation offsets; candidate text offsets from
step 1 remain available on the candidate itself.
