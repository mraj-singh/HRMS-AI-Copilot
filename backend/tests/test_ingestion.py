from app.services.ai.ingestion import ingest_policy_documents


def test_ingest_policy_documents():
    chunks = ingest_policy_documents()

    assert len(chunks) > 0
    assert all(chunk["text"].strip() for chunk in chunks)
    assert all(chunk["source"] for chunk in chunks)

    print(f"\nTotal chunks created: {len(chunks)}")

    for index, chunk in enumerate(chunks, start=1):
        print(f"\nChunk {index} | Source: {chunk['source']}")
        print(chunk["text"][:150])
