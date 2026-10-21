import logging

from app.services.ai.document_loader import load_policy_documents
from app.services.ai.chunking import chunk_documents

logger = logging.getLogger(__name__)


def ingest_policy_documents() -> list[dict[str, str]]:
    """Load policy documents and split them into chunks."""

    documents = load_policy_documents()
    chunks = chunk_documents(documents)

    logger.info(
        "Policy ingestion complete: %d documents, %d chunks.",
        len(documents),
        len(chunks),
    )

    return chunks
