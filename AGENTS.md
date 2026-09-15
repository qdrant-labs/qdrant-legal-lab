# Working in this repository

This is a timed retrieval-tuning exercise. A person has thirty minutes. Do not spend their budget reading the repository.

## The only file you may edit

`lab.py`, at the top of the repository. Everything else is fixed, including the scorer, the corpus, and the questions. Keep the signature of `retrieve()` exactly as it is.

## What you are optimising

Run `uv run python -m workshop.run score`. It scores fourteen cases and prints, per case and in total:

- `evidence found`, the controlling chunks retrieved out of the number the case needs. This is the primary score.
- `graded ranking`, NDCG at rank 5 over the graded results. Tiebreaker. It is not independent of coverage: a missing controlling chunk lowers it too.
- `wrong client`, `not in effect`, `duplicate`, three counts of visible failures. Drive them to zero.
- `score`, out of 100: `100 x (0.75 x evidence found + 0.25 x graded ranking)`, times the usable share of the five slots. Each visible failure wastes the slot it sits in, and a slot with two faults at once still costs one slot. The run's score is the mean of the case scores.

Change one thing in `lab.py`, run `score`, keep the change if the numbers improve. That is the whole method.

Two cases are marked with `*`. No configuration anyone has tried retrieves their evidence, and they are scored like the rest, so the best total we measured is 77 rather than 100. Do not read a total below 100 as a bug.

## Facts about the collection you would otherwise have to discover

Read the header of `lab.py` first. It lists the payload fields, their values, and two lines that print what the collection holds. The rest:

- It is read-only and preloaded. Do not try to write, re-ingest, or re-embed.
- Every embedding is produced by Qdrant Cloud Inference. No model runs locally. Use `models.Document(text=..., model=...)`.
- It carries more named vectors than `lab.py` queries. Each name states the model and the text it was built from, and none of them states whether it is any good on this corpus, which is a measurement rather than a guess. Two of the six are empty.
- The starter searches the whole collection, and approximate search returns a slightly different set each run, so its score moves a few points. Scoped configurations are steady.

## Out of scope

Find the evidence by searching for it. The scorer needs the graded chunk ids, so they sit in `workshop/questions.py`, and a lookup from question text to those ids is not a retrieval result and does not count.

Do not rewrite or expand the question text, and do not call `retrieve()` more than once per question. The agent that consumes this evidence makes exactly one call and never retries. Tuning the query string is not the exercise; tuning Qdrant is.

Do not look for the held-out questions. They are not in this repository.
