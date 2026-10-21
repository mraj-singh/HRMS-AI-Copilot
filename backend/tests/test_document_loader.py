from app.services.ai.document_loader import load_policy_documents


def test_load_policy_documents():
    documents = load_policy_documents()

    assert len(documents) == 3
    assert all(document["text"] for document in documents)
    assert all(document["source"] for document in documents)

    print(f"Loaded {len(documents)} unique policy documents:")
    for document in documents:
        print(f"- {document['source']}")
