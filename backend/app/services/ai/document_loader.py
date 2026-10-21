import hashlib
import logging
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

POLICY_DIR = Path("storage/hr-policies")


def load_policy_documents() -> list[dict[str, str]]:
    """Load policy files, extract text, and remove duplicate content."""
    documents = []
    seen_hashes = set()

    if not POLICY_DIR.exists():
        raise FileNotFoundError(
            f"Policy directory not found: {POLICY_DIR.resolve()}"
        )

    for file_path in sorted(POLICY_DIR.iterdir()):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                reader = PdfReader(str(file_path))
                text = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            elif suffix == ".txt":
                text = file_path.read_text(
                    encoding="utf-8", errors="replace"
                )
            else:
                logger.info("Skipping unsupported file: %s", file_path.name)
                continue

            text = " ".join(text.split())

            if not text:
                logger.warning("Skipping empty document: %s", file_path.name)
                continue

            content_hash = hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest()

            if content_hash in seen_hashes:
                logger.info("Skipping duplicate document: %s", file_path.name)
                continue

            seen_hashes.add(content_hash)

            documents.append(
                {
                    "text": text,
                    "source": file_path.name,
                }
            )

        except Exception:
            logger.exception("Failed to load policy file: %s", file_path.name)

    return documents
