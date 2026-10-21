from pathlib import Path
import hashlib
import json
import chromadb

CHROMA_DIR = Path("storage/chroma")
COLLECTION_NAME = "hr_policies"


class PolicyVectorStore:
    """Persist and retrieve HR policy chunks using ChromaDB."""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        chunks: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None:
        """Store chunks with stable IDs and source metadata."""

        if len(chunks) != len(embeddings):
            raise ValueError(
                "The number of chunks must match the number of embeddings."
            )

        if not chunks:
            return

        ids = []
        for chunk in chunks:
            identity = json.dumps(
                {
                    "source": chunk["source"],
                    "text": chunk["text"],
                },
                sort_keys=True,
            )
            chunk_id = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()
            ids.append(chunk_id)

        self.collection.upsert(
            ids=ids,
            documents=[chunk["text"] for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {"source": chunk["source"]}
                for chunk in chunks
            ],
        )

    def replace_all(
        self,
        chunks: list[dict[str, str]],
        embeddings: list[list[float]],
    ) -> None:
        """Replace stored policy chunks with the latest complete index."""

        if len(chunks) != len(embeddings):
            raise ValueError(
                "The number of chunks must match the number of embeddings."
            )

        existing = self.collection.get()

        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])

        if chunks:
            self.add_chunks(chunks, embeddings)
    
    def search(self, query_embedding, top_k: int = 3) -> list[dict]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        collection_count = self.collection.count()

        if collection_count == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection_count),
            include=["documents", "metadatas", "distances"],
        )

        matches = []

        for i, document in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]

            matches.append({
                "id": results["ids"][0][i],
                "text": document,
                "source": metadata.get("source", "unknown"),
                "distance": distance,
            })

        return matches