from app.services.ai.embeddings import embedding_service
from app.services.ai.vector_store import PolicyVectorStore


def test_policy_vector_store():
    store = PolicyVectorStore(collection_name="hr_policies_test")

    chunks = [
        {
            "text": "Work from home requires manager approval.",
            "source": "hr_policy.pdf",
        },
        {
            "text": "Casual leave allowance is 12 days per year.",
            "source": "leave_policy.pdf",
        },
    ]

    vectors = embedding_service.embed_documents(
        [chunk["text"] for chunk in chunks]
    )

    store.add_chunks(chunks, vectors)

    query_vector = embedding_service.embed_text(
        "Can I work remotely?"
    )

    results = store.search(query_vector, top_k=2)

    assert len(results) >= 1
    assert results[0]["source"] == "hr_policy.pdf"

    print("\nSearch results:")
    for result in results:
        print(result["source"], result["distance"], result["text"])
