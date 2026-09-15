"""THE ONE FILE YOU EDIT.

Everything else is fixed. Change this file, run

    uv run python -m workshop.run score

and watch the score move. The browser at localhost:8000 re-reads this file on
every run, so you never have to restart it.

The collection is read-only and preloaded. It holds the three client matters
this lab is about, and several hundred real public contracts belonging to other
clients. It also holds more representations than this starter asks for; `score`
prints how many it uses against how many are there.

Keep the signature of retrieve() exactly as it is. The scorer calls it.

New to Qdrant? The two pages that explain the code below are
https://qdrant.tech/documentation/concepts/hybrid-queries/ for prefetch and
fusion, and https://qdrant.tech/documentation/concepts/filtering/ for filter
conditions. AGENTS.md lists what the collection holds. Paste both at your
coding agent, because it cannot see the Evidence Playbook in the browser.

Every chunk carries these payload fields:

    matter_id          which client the document belongs to
    effective_from     ISO date, filterable with models.DatetimeRange
    effective_to       ISO date, 9999-12-31 when nothing replaced it
    status             operative or superseded
    instrument_type    agreement, amendment, exhibit, memo, operational_record
    source_family      copies of one document share this
    document_id        one per document
    section_id         the clause number, as a lawyer would cite it
    heading            the clause heading
    references         passage ids this clause points at

There are more fields than these. Look before you tune, because both of these
are allowed and neither is in this file:

    params = client.get_collection(collection).config.params
    print(params.vectors, params.sparse_vectors)
    print(client.query_points(collection, limit=1, with_payload=True).points[0])
"""

from qdrant_client import models

# Cloud Inference embeds the query server-side, so no model runs on your laptop.
# A named vector and the model behind it are two different things: this queries
# the vector "minilm_l6_clause", which was built with all-MiniLM-L6-v2. The
# collection carries others. `run score` prints how many, and nothing tells you
# which of them is worth using except measuring it.
DENSE_VECTOR = "minilm_l6_clause"
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_VECTOR = "bm25"
SPARSE_MODEL = "Qdrant/bm25"

CANDIDATES = 5
LIMIT = 5


def build_filter(matter_id, as_of):
    """Scope the search.

    You are given two facts about every question: which client matter it is
    about, and the date it is asked on. Both are yours to use here.
    """
    return models.Filter(
        must=[
            models.FieldCondition(
                key="status", match=models.MatchValue(value="operative")
            ),
            models.FieldCondition(
                key="effective_from", range=models.DatetimeRange(lte=as_of)
            ),
            models.FieldCondition(
                key="effective_to", range=models.DatetimeRange(gte=as_of)
            ),
        ]
    )


def retrieve(client, collection, question, matter_id, as_of, limit=LIMIT):
    """Return ranked chunks for one dated question about one matter.

    Keep this signature. Return a list of ScoredPoint with payloads.
    """
    query_filter = build_filter(matter_id, as_of)
    dense = models.Document(text=question, model=DENSE_MODEL)
    sparse = models.Document(text=question, model=SPARSE_MODEL)

    return client.query_points(
        collection,
        prefetch=[
            models.Prefetch(query=dense, using=DENSE_VECTOR,
                            filter=query_filter, limit=CANDIDATES),
            models.Prefetch(query=sparse, using=SPARSE_VECTOR,
                            filter=query_filter, limit=CANDIDATES),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    ).points
