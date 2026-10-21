from app.services.ai.chunking import chunk_documents


def test_chunk_documents():
    documents = [
        {
            "text": "A" * 1200,
            "source": "test_policy.txt",
        }
    ]

    chunks = chunk_documents(
        documents,
        chunk_size=500,
        chunk_overlap=100,
    )

    assert len(chunks) == 3
    assert all(len(chunk["text"]) <= 500 for chunk in chunks)
    assert all(chunk["source"] == "test_policy.txt" for chunk in chunks)

    # Verify that adjacent chunks share the expected overlap.
    assert chunks[0]["text"][-100:] == chunks[1]["text"][:100]
    assert chunks[1]["text"][-100:] == chunks[2]["text"][:100]


def test_empty_document():
    chunks = chunk_documents(
        [{"text": "", "source": "empty.txt"}]
    )

    assert chunks == []


def test_invalid_overlap():
    try:
        chunk_documents(
            [{"text": "Example policy text", "source": "policy.txt"}],
            chunk_size=100,
            chunk_overlap=100,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for invalid overlap")