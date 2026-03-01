import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchField,
    SearchFieldDataType,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)

load_dotenv()

INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "groundedagent-chunks")


def main():
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    key = os.environ["AZURE_SEARCH_API_KEY"]

    index_client = SearchIndexClient(endpoint, AzureKeyCredential(key))

    # NOTE: dimensions must match your embeddings model output.
    # text-embedding-3-small is commonly 1536, but do not assume.
    # We'll set it dynamically in the upload script later if you prefer.
    # For now, set to 1536 and adjust if needed.
    vector_dimensions = int(os.environ.get("AZURE_EMBEDDING_DIMENSIONS", "1536"))

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="en.lucene"),
        SimpleField(name="source_uri", type=SearchFieldDataType.String, filterable=False, sortable=False),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.lucene"),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=vector_dimensions,
            vector_search_profile_name="vectorProfile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="vectorProfile", algorithm_configuration_name="hnsw")],
    )

    semantic_config = SemanticConfiguration(
        name="semanticConfig",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
        ),
    )

    semantic_search = SemanticSearch(configurations=[semantic_config])

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    # Create or update
    index_client.create_or_update_index(index)
    print(f"Index '{INDEX_NAME}' created/updated successfully.")


if __name__ == "__main__":
    main()