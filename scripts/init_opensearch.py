#!/usr/bin/env python3
"""Initialize OpenSearch index for RAG chunks."""

import os

from opensearchpy import OpenSearch

# Get configuration from environment variables
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
INDEX_NAME = "rag_chunks"


def create_index(client: OpenSearch) -> bool:
    """Create the rag_chunks index with mappings and settings."""

    index_mapping = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "english_content": {
                        "type": "standard",
                        "stopwords": "_english_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "title": {
                    "type": "text"
                },
                "content": {
                    "type": "text",
                    "analyzer": "english"
                },
                "section_path": {
                    "type": "keyword"
                },
                "doc_id": {
                    "type": "keyword"
                },
                "page_number": {
                    "type": "integer"
                },
                "chunk_type": {
                    "type": "keyword"
                },
                "parent_id": {
                    "type": "keyword"
                },
                "version": {
                    "type": "integer"
                },
                "chunk_hash": {
                    "type": "keyword"
                },
                "ingested_at": {
                    "type": "date"
                }
            }
        }
    }

    try:
        if client.indices.exists(index=INDEX_NAME):
            print(f"Index '{INDEX_NAME}' already exists. Deleting and recreating...")
            client.indices.delete(index=INDEX_NAME)

        client.indices.create(index=INDEX_NAME, body=index_mapping)
        print(f"Successfully created index '{INDEX_NAME}'")
        return True
    except Exception as e:
        print(f"Error creating index: {e}")
        return False


def main():
    """Main function to connect to OpenSearch and create the index."""
    host = OPENSEARCH_HOST
    port = OPENSEARCH_PORT

    # Create client with basic auth if credentials provided
    username = os.getenv("OPENSEARCH_USERNAME")
    password = os.getenv("OPENSEARCH_PASSWORD")

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(username, password) if username and password else None,
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )

    # Test connection
    try:
        info = client.info()
        print(f"Connected to OpenSearch: {info['version']['number']}")
    except Exception as e:
        print(f"Error connecting to OpenSearch: {e}")
        return

    # Create index
    if create_index(client):
        print("OpenSearch initialization completed successfully!")
    else:
        print("OpenSearch initialization failed!")
        exit(1)


if __name__ == "__main__":
    main()

