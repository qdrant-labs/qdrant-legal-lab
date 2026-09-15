"""Edit this file during the lab. The web app reloads it on every run.

The collection is preloaded and read-only. It contains the three fictional
client matters used in the lab, plus public contracts from other clients.

Keep the signature of retrieve() unchanged.

Qdrant references:
https://qdrant.tech/documentation/concepts/hybrid-queries/
https://qdrant.tech/documentation/concepts/filtering/

AGENTS.md lists the available vectors and their models.

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

You can inspect the collection and a sample point from this file:

    params = client.get_collection(collection).config.params
    print(params.vectors, params.sparse_vectors)
    print(client.query_points(collection, limit=1, with_payload=True).points[0])
"""

from qdrant_client import models

# Qdrant Cloud Inference embeds each query. The starter uses two of the six
# available vectors. Test any change against the board; a larger model is not
# necessarily a better fit for this corpus.
#
#   minilm_l6_clause     sentence-transformers/all-MiniLM-L6-v2   the clause body
#   minilm_l6_document   sentence-transformers/all-MiniLM-L6-v2   title + heading + body
#   mxbai_large_v1       mixedbread-ai/mxbai-embed-large-v1       the clause body
#   bm25                 Qdrant/bm25                              sparse, exact terms
#   splade_pp_v1         prithivida/Splade_PP_en_v1               sparse, term expansion
#   colbert_small_v1     answerdotai/answerai-colbert-small-v1    late interaction
#
DENSE_VECTOR = "minilm_l6_clause"
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_VECTOR = "bm25"
SPARSE_MODEL = "Qdrant/bm25"

CANDIDATES = 5
LIMIT = 5


def build_filter(matter_id, as_of):
    """Filter chunks using the matter and date supplied with the question."""
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
    """Return ranked chunks for one dated question about one matter."""
    query_filter = build_filter(matter_id, as_of)
    dense = models.Document(text=question, model=DENSE_MODEL)
    sparse = models.Document(text=question, model=SPARSE_MODEL)

    return client.query_points(
        collection,
        prefetch=[
            models.Prefetch(
                query=dense,
                using=DENSE_VECTOR,
                filter=query_filter,
                limit=CANDIDATES,
            ),
            models.Prefetch(
                query=sparse,
                using=SPARSE_VECTOR,
                filter=query_filter,
                limit=CANDIDATES,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    ).points
