import logging

from app.services.ai.ingestion import ingest_policy_documents
from app.services.ai.embeddings import embedding_service
from app.services.ai.vector_store import PolicyVectorStore

logger = logging.getLogger(__name__)


def index_hr_policies() -> int:
    """Load, chunk, embed, and synchronize the HR policy index."""

    chunks = ingest_policy_documents()

    # Generate embeddings before changing the existing index.
    embeddings = (
        embedding_service.embed_documents(
            [chunk["text"] for chunk in chunks]
        )
        if chunks
        else []
    )

    store = PolicyVectorStore()
    store.replace_all(chunks, embeddings)

    logger.info("Indexed %d policy chunks.", len(chunks))

    return len(chunks)