"""The published dimensions, scored against the graded chunks each case names.

coverage   Share of the controlling chunks that were retrieved. Two controlling
           chunks means retrieving one earns one half. Printed as a fraction,
           "1 of 2", and as Evidence Found.
ranking    NDCG over graded results at rank k, reported as Graded Ranking
           (NDCG@5). A source family contributes once, so the second and later
           copies of a memo take a rank slot and earn nothing. It is not
           independent of coverage: a missing controlling chunk lowers it too.
score      One number out of 100, from case_score below: coverage and ranking in
           the weights that function names, multiplied by the share of the k
           slots a lawyer could rely on.

Rank on the score, and on coverage before ranking quality, as the brief sets
out. The three failures stay as counts rather than one average, because an
average of 1.000 hid the concrete failures a reader can see in the result list.
"""

import json
import math
from pathlib import Path

# The previous run, so a delta answers "did the change I just made help".
# Both the browser and `run score` write it, so the two routes agree.
STATE = Path(__file__).resolve().parents[1] / ".workshop" / "last_run.json"

K = 5
GRADE = {"controlling": 3.0, "supporting": 1.0}


def grades(question):
    out = {pid: GRADE["controlling"] for pid in question["controlling"]}
    out.update({pid: GRADE["supporting"] for pid in question["supporting"]})
    return out


def applicable(chunk, question):
    return (
        chunk["matter_id"] == question["matter_id"]
        and chunk["effective_from"] <= question["as_of"] < chunk["effective_to"]
    )


def _dcg(gains):
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def score(question, chunks, k=K):
    """Score one ranked list of returned payloads against one validation question.

    Payloads, not ids, so the scorer grades what the system actually returned
    and never needs to look anything up in the corpus.
    """
    ranked = list(chunks)[:k]
    table = grades(question)

    seen_families = set()
    gains = []
    duplicate_families = 0
    # Which rank slots a lawyer could not rely on. A slot with two faults at
    # once, such as a second copy of another client's memo, is still one slot.
    unusable = set()
    for position, payload in enumerate(ranked):
        family = payload["source_family"]
        gain = table.get(payload["passage_id"], 0.0)
        if family in seen_families:
            gain = 0.0  # repetition is not corroboration
            duplicate_families += 1
            unusable.add(position)
        seen_families.add(family)
        gains.append(gain)
        if not applicable(payload, question):
            unusable.add(position)

    ideal = sorted(table.values(), reverse=True)[:k]
    ranking = _dcg(gains) / _dcg(ideal) if ideal else 0.0

    found = {p["passage_id"] for p in ranked} & set(question["controlling"])
    coverage = len(found) / len(question["controlling"])

    # Counts a person can see in the result list, rather than an average that
    # hides them. A leak is another client's document. A temporal violation is
    # this client's document outside its effective window on the question date.
    leaks = [p["passage_id"] for p in ranked if p["matter_id"] != question["matter_id"]]
    stale = [
        p["passage_id"]
        for p in ranked
        if p["matter_id"] == question["matter_id"] and not applicable(p, question)
    ]

    row = {
        "question_id": question["question_id"],
        "coverage": coverage,
        "found": len(found),
        "controlling": len(question["controlling"]),
        "ranking": ranking,
        "tenant_leaks": len(leaks),
        "temporal_violations": len(stale),
        "duplicate_families": duplicate_families,
        "wasted": len(unusable),
        "missing": sorted(set(question["controlling"]) - found),
        "returned": [p["passage_id"] for p in ranked],
    }
    row["score"] = round(case_score(row, k))
    return row


# What the evidence set is worth, and what is wrong with it. Coverage leads,
# ordering quality follows it, and both are earned back only on the share of the
# result list a lawyer could actually use.
COVERAGE_WEIGHT = 0.75
ORDER_WEIGHT = 0.25


def case_score(row, k=K):
    """Score one case out of 100.

    Every term is a share of something, so the units are comparable and a
    different retrieval that returns the same quality of evidence scores the
    same. Quality is coverage first and graded ranking second, in the proportions the
    brief sets out. Usable is the share of the k slots that a lawyer could rely
    on: a chunk from another client, a chunk that was not in effect, and a
    repeat copy of a document already returned each waste the slot it sits in.
    One slot with two faults at once is still one slot.
    """
    quality = COVERAGE_WEIGHT * row["coverage"] + ORDER_WEIGHT * row["ranking"]
    usable = max(0.0, 1 - min(row["wasted"], k) / k)
    return 100 * quality * usable


def total(result):
    """The run's score: the mean of its case scores, rounded."""
    return round(sum(case_score(row) for row in result["rows"]) / len(result["rows"]))


def score_all(questions, retrieve, k=K):
    """retrieve(question, matter_id, as_of) must return ranked payload dicts."""
    rows = [
        score(x, retrieve(x["question"], x["matter_id"], x["as_of"]), k)
        for x in questions
    ]
    mean = lambda key: sum(r[key] for r in rows) / len(rows)
    total_of = lambda key: sum(r[key] for r in rows)
    result = {
        "coverage": mean("coverage"),
        "ranking": mean("ranking"),
        "solved": sum(1 for r in rows if r["coverage"] == 1.0),
        "questions": len(rows),
        "tenant_leaks": total_of("tenant_leaks"),
        "temporal_violations": total_of("temporal_violations"),
        "duplicate_families": total_of("duplicate_families"),
        "rows": rows,
    }
    result["score"] = total(result)
    return result


def remember(result):
    """Return the previous run's case scores, then record this one."""
    try:
        previous = json.loads(STATE.read_text())["rows"]
    except Exception:
        # Both surfaces write this file, so an interleaved write can truncate
        # it. A missing comparison is a smaller loss than a dead score command.
        previous = None
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(
        {"rows": {r["question_id"]: r["score"] for r in result["rows"]}}
    ))
    return previous
