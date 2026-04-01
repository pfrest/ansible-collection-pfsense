"""Shared pytest fixtures for the pfrest.pfsense collection test suite."""

# pylint: disable=redefined-outer-name

from unittest.mock import MagicMock

import pytest

from ansible_collections.pfrest.pfsense.plugins.module_utils.rest import RestClient
from ansible_collections.pfrest.pfsense.plugins.module_utils.base import BaseModule

# Minimal schema fixtures — enough to construct a BaseModule without hitting
# the real embedded schema.


FAKE_MODEL_CLASS = "FakeModel"
FAKE_SINGULAR_ENDPOINT = "/api/v2/fake/object"
FAKE_PLURAL_ENDPOINT = "/api/v2/fake/objects"

FAKE_CHILD_MODEL_CLASS = "FakeChildModel"
FAKE_CHILD_SINGULAR_ENDPOINT = "/api/v2/fake/object/child"
FAKE_CHILD_PLURAL_ENDPOINT = "/api/v2/fake/object/children"

FAKE_SCHEMA = {
    "endpoints": {
        FAKE_SINGULAR_ENDPOINT: {
            "url": FAKE_SINGULAR_ENDPOINT,
            "model_class": FAKE_MODEL_CLASS,
            "many": False,
            "request_method_options": ["GET", "POST", "PATCH", "DELETE"],
        },
        FAKE_PLURAL_ENDPOINT: {
            "url": FAKE_PLURAL_ENDPOINT,
            "model_class": FAKE_MODEL_CLASS,
            "many": True,
            "request_method_options": ["GET", "PUT"],
        },
        FAKE_CHILD_SINGULAR_ENDPOINT: {
            "url": FAKE_CHILD_SINGULAR_ENDPOINT,
            "model_class": FAKE_CHILD_MODEL_CLASS,
            "many": False,
            "request_method_options": ["GET", "POST", "PATCH", "DELETE"],
        },
        FAKE_CHILD_PLURAL_ENDPOINT: {
            "url": FAKE_CHILD_PLURAL_ENDPOINT,
            "model_class": FAKE_CHILD_MODEL_CLASS,
            "many": True,
            "request_method_options": ["GET"],
        },
    },
    "models": {
        FAKE_MODEL_CLASS: {
            "class": FAKE_MODEL_CLASS,
            "verbose_name": "Fake Object",
            "verbose_name_plural": "Fake Objects",
            "many": True,
            "parent_model_class": "",
            "parent_id_type": None,
            "fields": {
                "name": {
                    "name": "name",
                    "type": "string",
                    "required": True,
                    "read_only": False,
                    "default": None,
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "enabled": {
                    "name": "enabled",
                    "type": "boolean",
                    "required": False,
                    "read_only": False,
                    "default": True,
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "tags": {
                    "name": "tags",
                    "type": "string",
                    "required": False,
                    "read_only": False,
                    "default": [],
                    "choices": [],
                    "many": True,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "status": {
                    "name": "status",
                    "type": "string",
                    "required": False,
                    "read_only": True,
                    "default": None,
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "aliases": {
                    "name": "aliases",
                    "type": "array",
                    "required": False,
                    "read_only": False,
                    "default": [],
                    "choices": [],
                    "many": True,
                    "sensitive": False,
                    "nested_model_class": "FakeAlias",
                },
            },
        },
        "FakeAlias": {
            "class": "FakeAlias",
            "verbose_name": "Fake Alias",
            "verbose_name_plural": "Fake Aliases",
            "many": True,
            "parent_model_class": "",
            "parent_id_type": None,
            "fields": {
                "host": {
                    "name": "host",
                    "type": "string",
                    "required": True,
                    "read_only": False,
                    "default": None,
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "descr": {
                    "name": "descr",
                    "type": "string",
                    "required": False,
                    "read_only": False,
                    "default": "",
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
            },
        },
        FAKE_CHILD_MODEL_CLASS: {
            "class": FAKE_CHILD_MODEL_CLASS,
            "verbose_name": "Fake Child Object",
            "verbose_name_plural": "Fake Child Objects",
            "many": True,
            "parent_model_class": FAKE_MODEL_CLASS,
            "parent_id_type": "integer",
            "fields": {
                "label": {
                    "name": "label",
                    "type": "string",
                    "required": True,
                    "read_only": False,
                    "default": None,
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
                "value": {
                    "name": "value",
                    "type": "string",
                    "required": False,
                    "read_only": False,
                    "default": "",
                    "choices": [],
                    "many": False,
                    "sensitive": False,
                    "nested_model_class": None,
                },
            },
        },
    },
}


def _make_json_response(data: dict) -> MagicMock:
    """Create a mock `requests.Response` whose `.json()` returns *data*."""
    resp = MagicMock()
    resp.json.return_value = data
    return resp


@pytest.fixture()
def mock_rest_client():
    """Return a `RestClient` mock with all HTTP methods pre-stubbed."""
    client = MagicMock(spec=RestClient)
    # Default: every method returns an empty-ish successful response
    empty_resp = _make_json_response({"code": 200, "data": {}})
    client.get.return_value = empty_resp
    client.post.return_value = empty_resp
    client.patch.return_value = empty_resp
    client.put.return_value = empty_resp
    client.delete.return_value = empty_resp
    return client


@pytest.fixture()
def base_module(mock_rest_client, monkeypatch):
    """Return a `BaseModule` wired to the fake schema and mock REST client.

    The real `NativeSchema` is monkey-patched so it reads from
    `FAKE_SCHEMA` instead of the embedded schema dict.
    """
    monkeypatch.setattr(
        "ansible_collections.pfrest.pfsense.plugins.module_utils.schema.SCHEMA_DICT",
        FAKE_SCHEMA,
    )
    return BaseModule(FAKE_SINGULAR_ENDPOINT, mock_rest_client)


@pytest.fixture()
def child_base_module(mock_rest_client, monkeypatch):
    """Return a `BaseModule` for the fake child model (has parent_model_class).

    The real `NativeSchema` is monkey-patched so it reads from
    `FAKE_SCHEMA` instead of the embedded schema dict.
    """
    monkeypatch.setattr(
        "ansible_collections.pfrest.pfsense.plugins.module_utils.schema.SCHEMA_DICT",
        FAKE_SCHEMA,
    )
    return BaseModule(FAKE_CHILD_SINGULAR_ENDPOINT, mock_rest_client)

