"""
Create Vector Search index for product embeddings
"""
from databricks import sdk
from databricks.sdk.service import vectorsearch
import time
import json

w = sdk.WorkspaceClient()

# Index configuration
ENDPOINT_NAME = "fashion-vector-search"
INDEX_NAME = "main.fashion_sota.product_embeddings_index"
SOURCE_TABLE = "main.fashion_sota.product_embeddings"
PRIMARY_KEY = "product_id"
EMBEDDING_COLUMN = "embedding"
EMBEDDING_DIM = 512

print(f"Creating Vector Search index: {INDEX_NAME}")
print(f"Source table: {SOURCE_TABLE}")
print(f"Endpoint: {ENDPOINT_NAME}")
print()

try:
    # Create the index using SDK
    from databricks.sdk.service.vectorsearch import (
        DeltaSyncVectorIndexSpecRequest,
        EmbeddingVectorColumn,
        PipelineType
    )

    delta_sync_spec = DeltaSyncVectorIndexSpecRequest(
        source_table=SOURCE_TABLE,
        embedding_vector_columns=[
            EmbeddingVectorColumn(
                name=EMBEDDING_COLUMN,
                embedding_dimension=EMBEDDING_DIM
            )
        ],
        pipeline_type=PipelineType.TRIGGERED
    )

    response = w.vector_search_indexes.create_index(
        name=INDEX_NAME,
        endpoint_name=ENDPOINT_NAME,
        primary_key=PRIMARY_KEY,
        index_type=vectorsearch.VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=delta_sync_spec
    )

    print(f"✅ Vector Search index creation initiated!")
    print(f"   Index: {INDEX_NAME}")
    print(f"   Status: {response.status}")
    print()

    # Wait for index to be ready
    print("Waiting for index to sync...")
    for i in range(60):  # Wait up to 5 minutes
        try:
            index_info = w.vector_search_indexes.get_index(index_name=INDEX_NAME)
            state = index_info.status.detailed_state if index_info.status else "UNKNOWN"
            indexed_rows = index_info.status.indexed_row_count if index_info.status else 0
            print(f"  [{i+1}/60] Status: {state}, Rows indexed: {indexed_rows}")

            if state == vectorsearch.VectorIndexStatus.DetailedState.ONLINE:
                print(f"\n✅ Index is ONLINE and ready to use!")
                print(f"   Indexed rows: {indexed_rows}")
                break
            elif "FAILED" in str(state):
                print(f"\n❌ Index creation failed: {state}")
                break
        except Exception as e:
            print(f"  [{i+1}/60] Checking status... ({e})")

        time.sleep(5)

except Exception as e:
    print(f"❌ Error creating index: {e}")
    print(f"\nIf index already exists, you can sync it with:")
    print(f"  w.vector_search_indexes.sync_index(index_name='{INDEX_NAME}')")
