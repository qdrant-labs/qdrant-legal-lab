"""Your feedback loop. Three commands, all read-only.

    uv run python -m workshop.run ask "how long do we have to fix it?" -m harbor
    uv run python -m workshop.run answer "are we cleared to build?" -m atlas
    uv run python -m workshop.run score

ask     Prints the ranked chunks, with the client each one belongs to.
answer  Sends those chunks to the agent, and marks the ones it cited.
score   Scores the fourteen cases out of 100.

The question date defaults to today. A case carries its own date, because the
date decides which version of a clause was in effect.
"""

import argparse
import datetime
import os
import textwrap
from dotenv import load_dotenv
from qdrant_client import models
from . import agent
from .display import client_name
from .client import collection, connect, lab, representations
from .questions import CALIBRATION as QUESTIONS, CHALLENGE_IDS, MATTERS
from .score import remember, score_all, K

TODAY = datetime.date.today().isoformat()


def ask(args):
    qc, name = connect(), collection()
    points = lab().retrieve(qc, name, args.question, args.matter, args.date)
    print(f"\n{args.question}\nmatter {args.matter}, as of {args.date}\n")
    for i, p in enumerate(points, 1):
        d = p.payload
        flag = "" if d["effective_to"] == "9999-12-31" else f"  [superseded {d['effective_to']}]"
        print(f"{i:2}. {p.score:7.3f}  {d['document_title'][:56]} s.{d['section_id']}{flag}")
        print(f"     {client_name(d)}  ({d['instrument_type']}, from {d['effective_from']})")
        print(f"     {d['heading']}")
        print(textwrap.fill(d["text"], 92, initial_indent="     ", subsequent_indent="     "))
        print()
    print(representations(qc, name))


def score(args):
    qc, name = connect(), collection()
    current = lab()
    run = lambda q, m, d: [p.payload for p in current.retrieve(qc, name, q, m, d, limit=K)]
    result = score_all(QUESTIONS, run)
    previous = remember(result)
    print(f"\ncalibration set, {len(QUESTIONS)} questions, top {K}. Two are marked "
          f"challenge and nobody has reached their evidence yet.\n")
    head = (f"{'case':30} {'score':>5} {'was':>5} {'evidence found':>14} "
            f"{'graded ranking':>14} {'wrong client':>13} {'not in effect':>14} "
            f"{'duplicate':>9}")
    print(head + "  missing")
    print("-" * len(head))
    # "was" is this case in the previous run, from either the terminal or the
    # browser. Blank on the first run of the evening, when there is nothing yet.
    was = lambda qid: (previous or {}).get(qid)
    for row in result["rows"]:
        before = was(row["question_id"])
        mark = " *" if row["question_id"] in CHALLENGE_IDS else "  "
        print(
            f"{row['question_id']:28}{mark} {row['score']:5} "
            f"{'' if before is None or before == row['score'] else before:>5} "
            f"{row['found']:>7}/{row['controlling']:<6} "
            f"{row['ranking']:14.2f} {row['tenant_leaks']:13} {row['temporal_violations']:14} "
            f"{row['duplicate_families']:9}  {', '.join(row['missing']) or '-'}"
        )
    print("-" * len(head))
    print(
        f"{'TOTAL':30} {result['score']:5} {'':5} {result['coverage'] * 100:13.0f}% "
        f"{result['ranking']:14.2f} {result['tenant_leaks']:13} "
        f"{result['temporal_violations']:14} {result['duplicate_families']:9}"
        f"   {result['solved']}/{result['questions']} solved"
    )
    print(f"\nSCORE {result['score']} out of 100, the mean of the case scores.")
    # The legend is reference, and a person runs this command fifteen times in
    # thirty minutes. Print it once, while it is still news.
    if previous is None:
        print(
            "\nscore           this case out of 100: evidence found and graded ranking, over the\n"
            "                usable slots\n"
            "evidence found  controlling chunks you retrieved, the largest part of the score\n"
            "graded ranking  NDCG at rank 5 over the graded results, shown as Graded Ranking\n"
            "                (NDCG@5) in the browser. A missing controlling chunk lowers it too,\n"
            "                so it moves with evidence found\n"
            "wrong client    chunks from another client's files\n"
            "not in effect   this client's chunks that were not in effect on the question date\n"
            "duplicate       rank slots taken by a repeat copy of a document you already returned\n"
            "missing         the controlling chunks this case needed and you did not return\n"
            "*               a challenge case, scored like the rest and not yet solved by anyone\n"
            "\nA slot with two faults at once, such as a second copy of another client's memo,\n"
            "costs one slot rather than two. Until you scope the search, the score moves a few\n"
            "points between identical runs, because approximate search over the whole collection\n"
            "returns a slightly different set each time."
        )

    print(f"\n{representations(qc, name)}")


def preflight(args):
    """Run this before the room does. It fails loudly instead of at minute 12."""
    ok = True
    try:
        qc, name = connect(), collection()
    except SystemExit as exc:
        print(f"FAIL  .env: {exc}")
        return
    try:
        info = qc.get_collection(name)
    except Exception as exc:
        print(f"FAIL  cannot read collection {name}: {str(exc)[:120]}")
        print("      Check QDRANT_URL and that the key is scoped to this collection.")
        return
    dense = set(info.config.params.vectors or {})
    sparse = set(info.config.params.sparse_vectors or {})
    count = qc.count(name, exact=True).count
    print(f"OK    collection {name}: {count} chunks")
    # How many chunks carry each representation. A declared vector with zero
    # chunks is one the cluster cannot embed yet, and is a dead end today. Which
    # of the loaded ones helps is a measurement, and this does not say.
    for vector in sorted(dense | sparse):
        loaded = qc.count(
            name,
            count_filter=models.Filter(must=[models.HasVectorCondition(has_vector=vector)]),
            exact=True,
        ).count
        state = f"{loaded} chunks" if loaded else "empty, the cluster cannot embed this yet"
        print(f"{'OK   ' if loaded else 'note '} vector {vector:18} {state}")

    for matter in sorted(MATTERS):
        n = qc.count(name, count_filter=models.Filter(
            must=[models.FieldCondition(key="matter_id", match=models.MatchValue(value=matter))]
        ), exact=True).count
        if n < 20:
            ok = False
            print(f"FAIL  matter {matter} has only {n} chunks")
        else:
            print(f"OK    matter {matter}: {n} chunks")

    # Check the models lab.py actually names. The collection declares more
    # representations than the starter uses, and finding out what they are is
    # part of the exercise, so preflight reports their names and stops there.
    current = lab()
    for signal, model in ((current.DENSE_VECTOR, current.DENSE_MODEL),
                          (current.SPARSE_VECTOR, current.SPARSE_MODEL)):
        try:
            qc.query_points(
                name,
                query=models.Document(text="termination for cause", model=model),
                using=signal,
                limit=1,
            )
            print(f"OK    inference {signal:18} {model}")
        except Exception as exc:
            ok = False
            reason = ("needs billing on the cluster" if "Authentication failed" in str(exc)
                      else str(exc)[:70])
            print(f"FAIL  inference {signal:18} {model} :: {reason}")

    load_dotenv(".env")
    points = current.retrieve(qc, name, "how long do we have to fix the problem", "harbor", "2026-01-20")
    print(f"{'OK   ' if points else 'FAIL '} lab.retrieve returned {len(points)} chunks")
    if not points:
        ok = False

    print(f"{'OK   ' if os.getenv('OPENAI_API_KEY') else 'FAIL '} OPENAI_API_KEY "
          f"{'set' if os.getenv('OPENAI_API_KEY') else 'missing, so the answering agent will not run'}")
    print("\nready" if ok and points else "\nnot ready, fix the FAIL lines above")


def answer(args):
    """What the agent says, given the evidence your retrieve() returned."""
    qc, name = connect(), collection()
    points = lab().retrieve(qc, name, args.question, args.matter, args.date)
    try:
        reply, cited, invented = agent.answer(points, args.question, args.matter, args.date)
    except RuntimeError as exc:
        return print(exc)

    print(f"\n{reply}\n")
    print("-" * 72)
    print("The chunks the agent saw:")
    for i, p in enumerate(points, 1):
        d = p.payload
        mark = "*" if i in cited else " "
        stale = "" if d["effective_to"] == "9999-12-31" else f"  superseded {d['effective_to']}"
        print(f" {mark}[{i}] {client_name(d)[:34]:34}  {d['document_title'][:40]} "
              f"s.{d['section_id']}{stale}")
    print("  * cited in the answer above.")
    if invented:
        print(f"  The answer cites {invented}, which was never retrieved.")


def main():
    parser = argparse.ArgumentParser(prog="workshop.run", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("ask", help="run one question and read the chunks")
    a.add_argument("question")
    a.add_argument("-m", "--matter", required=True, choices=sorted(MATTERS))
    a.add_argument("-d", "--date", default=TODAY, help=f"question date, YYYY-MM-DD, default {TODAY}")
    a.set_defaults(func=ask)

    s = sub.add_parser("score", help="score the calibration set")
    s.set_defaults(func=score)

    n = sub.add_parser("answer", help="what the agent says, given your evidence")
    n.add_argument("question")
    n.add_argument("-m", "--matter", required=True, choices=sorted(MATTERS))
    n.add_argument("-d", "--date", default=TODAY, help=f"question date, YYYY-MM-DD, default {TODAY}")
    n.set_defaults(func=answer)

    p = sub.add_parser("preflight", help="check the setup before the room does")
    p.set_defaults(func=preflight)

    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
