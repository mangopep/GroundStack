"""Regression coverage for safe, repeatable OpenSearch initialization."""

from unittest.mock import MagicMock

from scripts.init_opensearch import INDEX_NAME, create_index


def test_existing_index_is_preserved():
    client = MagicMock()
    client.indices.exists.return_value = True

    assert create_index(client) is True

    client.indices.delete.assert_not_called()
    client.indices.create.assert_not_called()


def test_missing_index_is_created():
    client = MagicMock()
    client.indices.exists.return_value = False

    assert create_index(client) is True

    client.indices.delete.assert_not_called()
    client.indices.create.assert_called_once()
    assert client.indices.create.call_args.kwargs["index"] == INDEX_NAME
