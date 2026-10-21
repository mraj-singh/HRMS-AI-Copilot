from app.services.ai.ingest_policies import index_hr_policies
from app.services.ai.vector_store import PolicyVectorStore


def test_index_hr_policies():
    indexed_count = index_hr_policies()

    store = PolicyVectorStore()
    assert indexed_count == 3
    assert store.collection.count() == 3

    # Re-running ingestion must not increase the record count.
    second_count = index_hr_policies()

    assert second_count == 3
    assert store.collection.count() == 3

    print(f"\nIndexed chunks: {second_count}")
    print(f"Stored records after rerun: {store.collection.count()}")