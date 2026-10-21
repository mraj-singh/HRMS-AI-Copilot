from app.services.ai.embeddings import embedding_service


def test_embed_text():
    vector = embedding_service.embed_text(
        "Work from home requires manager approval."
    )

    assert len(vector) == 384
    assert all(isinstance(value, float) for value in vector)


def test_embed_documents():
    vectors = embedding_service.embed_documents(
        [
            "Employees can work remotely with manager approval.",
            "Casual leave is 12 days per year.",
        ]
    )

    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
