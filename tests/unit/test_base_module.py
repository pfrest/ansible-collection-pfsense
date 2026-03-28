"""Tests for BaseModule CRUD operations and state management."""

# pylint: disable=missing-function-docstring,too-few-public-methods

from unittest.mock import MagicMock

import pytest

from ansible_collections.pfrest.pfsense.plugins.module_utils.base import (
    BaseModule,
    INTERNAL_ARGS,
)
from tests.conftest import _make_json_response


class TestSetObjectState:
    """set_object_state: create / update / delete / no-op branching."""

    def _data_with_internals(self, **overrides):
        """Build a data dict that includes required internal args."""
        base = {
            "api_host": "fw",
            "api_port": 443,
            "api_username": "admin",
            "api_password": "pw",
            "api_key": "",
            "validate_certs": True,
            "lookup_fields": ["name"],
            "state": "present",
            "name": "obj1",
            "enabled": True,
        }
        base.update(overrides)
        return base

    def test_creates_when_not_found(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": []}
        )
        mock_rest_client.post.return_value = _make_json_response(
            {"code": 200, "data": {"name": "obj1", "id": 0}}
        )

        data = self._data_with_internals()
        changed, _resp = base_module.set_object_state("present", data, ["name"])

        assert changed is True
        mock_rest_client.post.assert_called_once()

    def test_updates_when_different(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "obj1", "enabled": False, "id": 5}]}
        )
        mock_rest_client.patch.return_value = _make_json_response(
            {"code": 200, "data": {"name": "obj1", "enabled": True, "id": 5}}
        )

        data = self._data_with_internals(enabled=True)
        changed, _resp = base_module.set_object_state("present", data, ["name"])

        assert changed is True
        mock_rest_client.patch.assert_called_once()

    def test_no_change_when_identical(self, base_module, mock_rest_client):
        existing = {"name": "obj1", "enabled": True, "id": 5}
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [existing]}
        )

        data = self._data_with_internals()
        changed, _resp = base_module.set_object_state("present", data, ["name"])

        assert changed is False
        mock_rest_client.post.assert_not_called()
        mock_rest_client.patch.assert_not_called()

    def test_deletes_when_absent(self, base_module, mock_rest_client):
        existing = {"name": "obj1", "id": 5}
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [existing]}
        )
        mock_rest_client.delete.return_value = _make_json_response(
            {"code": 200, "data": {}}
        )

        data = self._data_with_internals(state="absent")
        changed, _resp = base_module.set_object_state("absent", data, ["name"])

        assert changed is True
        mock_rest_client.delete.assert_called_once()

    def test_no_change_when_absent_and_not_found(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": []}
        )

        data = self._data_with_internals(state="absent")
        changed, _resp = base_module.set_object_state("absent", data, ["name"])

        assert changed is False
        mock_rest_client.delete.assert_not_called()


class TestReplaceObjects:
    """replace_objects: change detection before PUT."""

    def test_skips_put_when_unchanged(self, base_module, mock_rest_client):
        existing = [{"name": "a", "id": 0}, {"name": "b", "id": 1}]
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": existing}
        )

        changed, _resp = base_module.replace_objects([{"name": "a"}, {"name": "b"}])

        assert changed is False
        mock_rest_client.put.assert_not_called()

    def test_puts_when_different(self, base_module, mock_rest_client):
        existing = [{"name": "a", "id": 0}]
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": existing}
        )
        mock_rest_client.put.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "z", "id": 0}]}
        )

        changed, _resp = base_module.replace_objects([{"name": "z"}])

        assert changed is True
        mock_rest_client.put.assert_called_once()

    def test_puts_when_lengths_differ(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": []}
        )
        mock_rest_client.put.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "new", "id": 0}]}
        )

        changed, _resp = base_module.replace_objects([{"name": "new"}])

        assert changed is True


class TestLookupObject:
    """lookup_object: single-object retrieval."""

    def test_returns_single_object(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "obj1", "id": 0}]}
        )
        result = base_module.lookup_object({"name": "obj1"})
        assert result["data"] == {"name": "obj1", "id": 0}

    def test_returns_empty_when_not_found(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": []}
        )
        result = base_module.lookup_object({"name": "missing"})
        assert result["data"] == {}

    def test_raises_when_multiple_found(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"id": 1}, {"id": 2}]}
        )
        with pytest.raises(LookupError, match="multiple existing objects"):
            base_module.lookup_object({"name": "dup"})


class TestLookupObjects:
    """lookup_objects: multi-object retrieval."""

    def test_returns_all(self, base_module, mock_rest_client):
        data = [{"name": "a", "id": 0}, {"name": "b", "id": 1}]
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": data}
        )
        result = base_module.lookup_objects()
        assert result["data"] == data


class TestStaticHelpers:
    """get_lookup_query and exclude_internal_args."""

    def test_get_lookup_query(self):
        query = BaseModule.get_lookup_query(
            ["name", "domain"],
            {"name": "a", "domain": "b", "extra": "x"},
        )
        assert query == {"name": "a", "domain": "b"}

    def test_exclude_internal_args(self):
        data = {arg: "val" for arg in INTERNAL_ARGS}
        data["name"] = "keep"
        result = BaseModule.exclude_internal_args(data)
        assert "name" in result
        for arg in INTERNAL_ARGS:
            assert arg not in result


class TestExecuteAction:
    """execute_action: delegates to create_object and always returns changed=True."""

    def test_returns_changed_true(self, base_module, mock_rest_client):
        mock_rest_client.post.return_value = _make_json_response(
            {"code": 200, "data": {"result": "ok"}}
        )
        changed, resp = base_module.execute_action({"name": "action1"})
        assert changed is True
        assert resp["data"] == {"result": "ok"}
        mock_rest_client.post.assert_called_once()


class TestUpdateSingleton:
    """update_singleton: skip PATCH when unchanged, apply PATCH when different."""

    def test_no_change_when_identical(self, base_module, mock_rest_client):
        existing = {"code": 200, "data": {"name": "obj1", "enabled": True}}
        mock_rest_client.get.return_value = _make_json_response(existing)

        changed, resp = base_module.update_singleton({"name": "obj1", "enabled": True})

        assert changed is False
        assert resp == existing
        mock_rest_client.patch.assert_not_called()

    def test_patches_when_different(self, base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": {"name": "obj1", "enabled": False}}
        )
        mock_rest_client.patch.return_value = _make_json_response(
            {"code": 200, "data": {"name": "obj1", "enabled": True}}
        )

        changed, resp = base_module.update_singleton({"name": "obj1", "enabled": True})

        assert changed is True
        assert resp["data"]["enabled"] is True
        mock_rest_client.patch.assert_called_once()


class TestValidateLookupFields:
    """validate_lookup_fields: requires self.module to be set."""

    def test_raises_when_no_lookup_fields(self, base_module):
        base_module.module = MagicMock()
        base_module.module.params = {"lookup_fields": []}
        with pytest.raises(ValueError, match="At least one lookup field"):
            base_module.validate_lookup_fields()

    def test_raises_for_invalid_lookup_field(self, base_module):
        base_module.module = MagicMock()
        base_module.module.params = {"lookup_fields": ["nonexistent_field"]}
        with pytest.raises(LookupError, match="does not exist"):
            base_module.validate_lookup_fields()

    def test_allows_id_lookup_field(self, base_module):
        base_module.module = MagicMock()
        base_module.module.params = {"lookup_fields": ["id"]}
        base_module.validate_lookup_fields()  # should not raise

    def test_allows_valid_schema_field(self, base_module):
        base_module.module = MagicMock()
        base_module.module.params = {"lookup_fields": ["name"]}
        base_module.validate_lookup_fields()  # should not raise

    def test_allows_mixed_id_and_valid_field(self, base_module):
        base_module.module = MagicMock()
        base_module.module.params = {"lookup_fields": ["id", "name"]}
        base_module.validate_lookup_fields()  # should not raise
