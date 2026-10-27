# CQ question candidate extraction

This standalone first pass proposes noun phrases and named entities found in
the `question` field of a JSON array of CQ objects. It does not access the
database, annotate spans automatically, or infer terms that are not written in
the question. Each candidate retains its exact surface text and character
offsets in the question.

## Setup

```sh
python -m pip install -r requirements-pos.txt
python -m spacy download de_core_news_sm
```

The German model is the default because the supplied CQ questions are mainly
German. An installed spaCy model can be selected with `--model`.

## Run

```sh
python extract_candidates.py cqs.json
```

By default, this writes `cqs.candidates.json` beside the input. Set `-o` to
choose another output path. The script reads only each record's `question`
field and carries through its `id` for review. The stopword list is
[`stopwords.txt`](stopwords.txt), one word per line; `#` lines are comments.
Configured function words are trimmed only from the edges of a proposed noun
phrase, so stopwords inside a phrase do not erase it.

The output contains each question plus sorted candidate objects. Candidate
objects include exact `text`, character `start`/`end` offsets (end-exclusive),
lemma, extraction rule, and token-level POS/tag metadata. Noun chunks must
contain a `NOUN` or `PROPN`; boundary determiners (`DET`) are trimmed
automatically, while other configured function words are trimmed when listed
in the stopword file. Nested candidates are retained when the parser proposes
them, and identical spans from noun chunking and NER are merged with both
rules recorded.
