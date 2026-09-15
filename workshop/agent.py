"""The answering agent, shared by the terminal and the browser.

One retrieval call, one completion, no retries. The agent never rephrases and
never searches again, so the answer is only ever as good as the evidence
retrieve() returned. That is the lesson.

The three matters are invented for this workshop, so the model has no memory of
Harbor, Cedar, or Atlas to fall back on. Whatever it says about them, it read in
the chunks. `cite_check` proves the other half: every [n] in the reply has to
point at a chunk that actually came back.
"""

import json
import os
import re
import urllib.error
import urllib.request

from dotenv import load_dotenv

from .questions import MATTERS

PROMPT = """You are a legal assistant at a law firm. Your client {client} has asked a \
question about their agreement with {counterparty}, their supplier.

Answer it using only the numbered documents below, and write the way a lawyer writes to a \
client. Lead with the answer. Four sentences at most, plain English, no markdown, and no \
dashes. Name the \
document and section you rely on and put its number after it, as in "Section 7.2 of the \
Master Services Agreement [1]". Never mention retrieval, searching, or how the documents \
reached you. If they do not settle the question, say so, say what is missing, and name the \
document that would answer it.

The question is asked as of {as_of}, so answer under the terms in effect on that date.

Question:
{question}

Documents:
{chunks}"""

CITATION = re.compile(r"\[(\d+)\]")


def format_chunks(points):
    return "\n\n".join(
        f"[{i}] {p.payload['document_title']} s.{p.payload['section_id']} "
        f"({p.payload['heading']}, in effect from {p.payload['effective_from']})\n"
        f"{p.payload['text']}"
        for i, p in enumerate(points, 1)
    )


def cite_check(reply, count):
    """Split the citations into ones that came back and ones that did not."""
    cited = sorted({int(n) for n in CITATION.findall(reply)})
    return (
        [n for n in cited if 1 <= n <= count],
        [n for n in cited if not 1 <= n <= count],
    )


def answer(points, question, matter, as_of):
    """Return (reply, cited, invented). Raise RuntimeError with a readable message."""
    load_dotenv(".env")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Run `uv run python -m workshop.setup` to unlock it."
        )
    if not points:
        raise RuntimeError("retrieve() returned nothing, so the agent has nothing to answer from.")

    body = json.dumps(
        {
            "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT.format(
                        as_of=as_of,
                        client=MATTERS.get(matter, {}).get("name", matter),
                        counterparty=MATTERS.get(matter, {}).get("counterparty", "their supplier"),
                        question=question,
                        chunks=format_chunks(points),
                    ),
                }
            ],
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            reply = json.load(response)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenAI returned {exc.code}: {exc.read().decode()[:200]}") from None

    cited, invented = cite_check(reply, len(points))
    return reply, cited, invented


def demo():
    """Self-check: a citation outside the returned range must be caught."""
    assert cite_check("The cap is capped [1], subject to [2].", 5) == ([1, 2], [])
    assert cite_check("See [6] and [1].", 5) == ([1], [6])
    assert cite_check("No citations here.", 5) == ([], [])
    return "agent.py self-check passed"


if __name__ == "__main__":
    print(demo())
