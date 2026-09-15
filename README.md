# The Qdrant Legal Retrieval Lab

A law firm keeps every client's contracts in one Qdrant collection: three client matters, and several hundred real commercial contracts belonging to other clients. You run retrieval at the firm.

A client's in-house team asks a dated question about their own matter. So "we" in a question is that client, and the company on the other side of the agreement is their supplier. Your job is to return the five chunks their answer should rest on.

The retrieval you have been given works. It is also wrong in ways that would end a career in a regulated practice, and it will not tell you that.

## Setup

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and about two minutes.

```bash
uv sync
uv run python -m workshop.setup
```

Setup asks for the workshop password, unlocks the credentials on your laptop, and runs the connection checks. The facilitator announces the password when the lab starts, and nothing prints while you type it. If it does not end with `ready`, show the first `FAIL` line to the facilitator. The cluster and the keys are shared, so that one is theirs to fix, not yours.

The collection is hosted and read-only, so no model runs on your laptop and there is nothing to download beyond the small Python project.

## The Loop

You edit one file, `lab.py`. Everything else is fixed.

```bash
uv run python -m workshop.app     # then open http://localhost:8000 yourself
```

Leave that terminal running and use a second one for the commands below. The first screen is the answering agent. Pick a case, read the answer, then read the five chunks the answer was built from. Each chunk names the client whose file it came from and the dates it was in effect. Decide what looks unsafe or incomplete, change one retrieval choice in `lab.py`, and run again. The app re-reads that file every time, so leave it open. Opening a case on the board shows the client's question and the five chunks that came back for it.

The browser also carries the Evidence Playbook, which is the legal half of this exercise. It renders only there. Read it before you tune.

The same loop works in the terminal:

```bash
uv run python -m workshop.run ask "how long do we have to fix the problem?" -m harbor -d 2026-01-20
uv run python -m workshop.run score
uv run python -m workshop.run answer "Are we cleared to build with the new 8841-C connector?" -m atlas -d 2026-09-01
```

A supplied case carries its own client and its own date, because the date decides which version of a clause governed. A question you write yourself uses today's date and the client you pick, the same way a real application takes the client from the file you have open rather than from the wording of the question.

The agent gets one retrieval call and no retries, and the three matters are invented for this workshop, so it has no memory to fall back on. Every citation it makes is checked against the chunks you returned, and a citation that points at nothing is marked in red.

## The Rules

1. You edit `lab.py` and nothing else. Its header lists the payload fields and links the two Qdrant pages that explain the starter code.
2. Keep the signature of `retrieve()` exactly as it is. The scorer calls it.
3. Query-time Qdrant code only. The collection is read-only and preloaded.
4. Find the evidence by searching for it. The scorer needs the graded ids, so they sit in `workshop/questions.py`, and fetching them by id is not a retrieval result.
5. Do not rewrite the question. The agent makes one call and never tries again, so the answer is only ever as good as what `retrieve()` returned.

## The Score

The board scores each of the fourteen cases out of 100 and shows the five columns behind that number. The first two rank you.

| Column | Meaning |
| --- | --- |
| Evidence Found | Controlling chunks you retrieved, out of the number the case needs. This ranks you first. |
| Graded Ranking (NDCG@5) | Normalized discounted cumulative gain over the graded results at rank 5. It falls when a controlling chunk is missing too, so it moves with Evidence Found. Tiebreaker. |
| Wrong Client | Chunks from another client's files. |
| Not in Effect | This client's chunks that were not in effect on the question date. A clause that was later replaced is in effect for any question dated while it governed. |
| Duplicate | Rank slots taken by a repeat copy of a document you already returned. |

```
case score = 100 x (0.75 x evidence found + 0.25 x graded ranking) x the usable share of your five slots
```

The run's score is the mean of the case scores. Every term is a share of something, so two retrievals that return evidence of the same quality score the same, whatever vectors, fusion, or filters produced it. A wrong client, a chunk that was not in effect, and a repeat copy each waste the slot it sits in: a case with all its evidence, ordered perfectly, and one wasted slot scores 80. A slot with two faults at once still costs one slot.

Until you scope the search, the score moves a few points between identical runs. The starter searches all 3,653 chunks, and approximate search returns a slightly different set each time. Do not chase it.

The board holds fourteen cases and its total is the number you call out at the end. Two of them carry a challenge tag: nothing we have tried reaches their evidence, and they are scored like the rest. The best we measured is 77, so the board does not top out at 100 and beating 77 is the target.

A larger set of questions stays with the facilitator. The fourteen here teach you the rubric, and the rest is the check on whether a change helps in general or only on the cases you can see.

## Coding Agents

Allowed, and encouraged. A generic request such as "improve this retrieval" will usually find conventional changes and miss the legal retrieval policy, which your agent cannot read from this repository. Tell it the observations you think matter, ask it to inspect the collection and current Qdrant capabilities, and require it to keep only changes that improve the score.

The exercise is not a test of whether an agent can type Qdrant code. It is a test of whether you can give the agent the right retrieval policy, the observations you made, and a loop that measures them.

## About the Documents

The three client matters, their parties, documents, dates, and every clause in them are invented for this workshop. They are not legal advice and they do not describe any real agreement.

The remaining contracts are real public filings from [CUAD](https://www.atticusprojectai.org/cuad), the Contract Understanding Atticus Dataset, published by The Atticus Project under CC BY 4.0. They keep their own names and parties, and no invented history has been attached to any of them.
