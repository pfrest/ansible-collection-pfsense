"""Tests for BaseModule CRUD operations and state management."""

# pylint: disable=missing-function-docstring,too-few-public-methods

from unittest.mock import MagicMock

import pytest

from ansible_collections.pfrest.pfsense.plugins.module_utils.base import (
    BaseModule,
    INTERNAL_ARGS,
)
from tests.conftest import (
    _make_json_response,
    FAKE_PLURAL_ENDPOINT,
)


class TestSetObjectState:
    """set_object_state: create / update / delete / no-op branching."""

    def _data_with_internals(self, **overrides):
        """Build a data dict that includes required internal args."""
        base = {
            "api_host": "fw",
            "api_port": 443,
            "api_protocol": "https",
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

    def test_api_protocol_is_internal_arg(self):
        assert "api_protocol" in INTERNAL_ARGS


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


class TestResolveParentId:
    """resolve_parent_id: resolves the parent object's ID from a lookup query dict."""

    def test_resolves_single_parent(self, child_base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "parent1", "id": 42}]}
        )

        parent_id = child_base_module.resolve_parent_id({"name": "parent1"})

        assert parent_id == 42
        mock_rest_client.get.assert_called_once_with(
            FAKE_PLURAL_ENDPOINT, params={"name": "parent1"}
        )

    def test_raises_when_no_parent_found(self, child_base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": []}
        )

        with pytest.raises(LookupError, match="matched no existing objects"):
            child_base_module.resolve_parent_id({"name": "missing"})

    def test_raises_when_multiple_parents_found(
        self, child_base_module, mock_rest_client
    ):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "dup", "id": 1}, {"name": "dup", "id": 2}]}
        )

        with pytest.raises(LookupError, match="matched multiple existing objects"):
            child_base_module.resolve_parent_id({"name": "dup"})

    def test_raises_when_parent_has_no_id(self, child_base_module, mock_rest_client):
        mock_rest_client.get.return_value = _make_json_response(
            {"code": 200, "data": [{"name": "no_id_parent"}]}
        )

        with pytest.raises(LookupError, match="has no 'id' field"):
            child_base_module.resolve_parent_id({"name": "no_id_parent"})

    def test_raises_when_model_has_no_parent(self, base_module, mock_rest_client):
        with pytest.raises(LookupError, match="does not have a parent model class"):
            base_module.resolve_parent_id({"name": "obj1"})


class TestSetObjectStateWithParent:
    """set_object_state with parent_lookup_query: resolves parent ID before CRUD."""

    def _data_with_internals(self, **overrides):
        base = {
            "api_host": "fw",
            "api_port": 443,
            "api_protocol": "https",
            "api_username": "admin",
            "api_password": "pw",
            "api_key": "",
            "validate_certs": True,
            "lookup_fields": ["label"],
            "parent_lookup_query": {"name": "parent1"},
            "state": "present",
            "label": "child1",
            "value": "v1",
        }
        base.update(overrides)
        return base

    def test_creates_child_with_resolved_parent_id(
        self, child_base_module, mock_rest_client
    ):
        # First call: resolve parent → returns parent with id=10
        # Second call: lookup child → not found
        mock_rest_client.get.side_effect = [
            _make_json_response({"code": 200, "data": [{"name": "parent1", "id": 10}]}),
            _make_json_response({"code": 200, "data": []}),
        ]
        mock_rest_client.post.return_value = _make_json_response(
            {"code": 200, "data": {"label": "child1", "parent_id": 10, "id": 0}}
        )

        data = self._data_with_internals()
        changed, resp = child_base_module.set_object_state(
            "present", data, ["label"], parent_lookup_query={"name": "parent1"}
        )

        assert changed is True
        assert data["parent_id"] == 10
        mock_rest_client.post.assert_called_once()

    def test_no_change_when_child_identical(self, child_base_module, mock_rest_client):
        existing = {"label": "child1", "value": "v1", "parent_id": 10, "id": 5}
        mock_rest_client.get.side_effect = [
            _make_json_response({"code": 200, "data": [{"name": "parent1", "id": 10}]}),
            _make_json_response({"code": 200, "data": [existing]}),
        ]

        data = self._data_with_internals()
        changed, _resp = child_base_module.set_object_state(
            "present", data, ["label"], parent_lookup_query={"name": "parent1"}
        )

        assert changed is False

    def test_deletes_child_with_parent_id(self, child_base_module, mock_rest_client):
        existing = {"label": "child1", "parent_id": 10, "id": 5}
        mock_rest_client.get.side_effect = [
            _make_json_response({"code": 200, "data": [{"name": "parent1", "id": 10}]}),
            _make_json_response({"code": 200, "data": [existing]}),
        ]
        mock_rest_client.delete.return_value = _make_json_response(
            {"code": 200, "data": {}}
        )

        data = self._data_with_internals(state="absent")
        changed, _resp = child_base_module.set_object_state(
            "absent", data, ["label"], parent_lookup_query={"name": "parent1"}
        )

        assert changed is True
        mock_rest_client.delete.assert_called_once()


class TestValidateFieldType:
    """validate_field_type: nested model and primitive type validation."""

    # -- Nested model, many=True -------------------------------------------------

    def test_nested_many_valid_list_of_dicts(self):
        """Valid list[dict] for a nested many field passes silently."""
        schema = {"name": "aliases", "nested_model_class": "FakeAlias", "many": True}
        BaseModule.validate_field_type(schema, [{"host": "h1"}, {"host": "h2"}])

    def test_nested_many_rejects_non_list(self):
        """Non-list value for a nested many field raises TypeError."""
        schema = {"name": "aliases", "nested_model_class": "FakeAlias", "many": True}
        with pytest.raises(TypeError, match="expects type 'list'"):
            BaseModule.validate_field_type(schema, "not-a-list")

    def test_nested_many_rejects_non_dict_element(self):
        """List element that isn't a dict raises TypeError."""
        schema = {"name": "aliases", "nested_model_class": "FakeAlias", "many": True}
        with pytest.raises(TypeError, match="expects elements of type 'dict'"):
            BaseModule.validate_field_type(schema, [{"host": "ok"}, 42])

    # -- Nested model, many=False ------------------------------------------------

    def test_nested_single_valid_dict(self):
        """Valid dict for a nested non-many field passes silently."""
        schema = {"name": "detail", "nested_model_class": "FakeDetail", "many": False}
        BaseModule.validate_field_type(schema, {"key": "val"})

    def test_nested_single_rejects_non_dict(self):
        """Non-dict value for a nested non-many field raises TypeError."""
        schema = {"name": "detail", "nested_model_class": "FakeDetail", "many": False}
        with pytest.raises(TypeError, match="expects type 'dict'"):
            BaseModule.validate_field_type(schema, "not-a-dict")

    # -- Non-nested: None short-circuit ------------------------------------------

    def test_none_allowed_for_non_required_field(self):
        """None value on a non-required, non-nested field returns without error."""
        schema = {"name": "descr", "type": "string", "required": False, "many": False}
        BaseModule.validate_field_type(schema, None)  # should not raise

    # -- Non-nested: type validation (non-many) ----------------------------------

    def test_non_many_valid_type(self):
        """Correct primitive type passes silently."""
        schema = {"name": "enabled", "type": "boolean", "required": False, "many": False}
        BaseModule.validate_field_type(schema, True)  # should not raise

    def test_non_many_wrong_type(self):
        """Wrong primitive type raises TypeError."""
        schema = {"name": "enabled", "type": "boolean", "required": False, "many": False}
        with pytest.raises(TypeError, match="expects type 'bool'"):
            BaseModule.validate_field_type(schema, "not-a-bool")

    # -- Non-nested: type validation (many) --------------------------------------

    def test_many_wrong_element_type(self):
        """Wrong element type inside a many-enabled primitive field raises TypeError."""
        schema = {"name": "tags", "type": "string", "required": False, "many": True}
        with pytest.raises(TypeError, match="expects type 'str'"):
            BaseModule.validate_field_type(schema, [123])


class TestValuesMatch:
    """_values_match: edge cases for the recursive comparison helper."""

    def test_none_matches_empty_list(self):
        """None desired is considered equivalent to an existing empty list."""
        assert BaseModule._values_match(None, []) is True

    def test_none_matches_empty_dict(self):
        """None desired is considered equivalent to an existing empty dict."""
        assert BaseModule._values_match(None, {}) is True

    def test_empty_list_matches_none(self):
        """Empty list desired is considered equivalent to existing None."""
        assert BaseModule._values_match([], None) is True

    def test_empty_dict_matches_none(self):
        """Empty dict desired is considered equivalent to existing None."""
        assert BaseModule._values_match({}, None) is True

    def test_missing_key_with_none_value_still_matches(self):
        """A desired key with value None that is absent from existing is OK."""
        assert BaseModule._values_match({"a": 1, "b": None}, {"a": 1}) is True

    def test_missing_key_with_non_none_value_does_not_match(self):
        """A desired key with a real value absent from existing is a mismatch."""
        assert BaseModule._values_match({"a": 1, "b": "x"}, {"a": 1}) is False

    def test_list_comparison_equal(self):
        """Two equal flat lists match."""
        assert BaseModule._values_match([1, 2, 3], [1, 2, 3]) is True

    def test_list_comparison_different_lengths(self):
        """Lists of different lengths do not match."""
        assert BaseModule._values_match([1, 2], [1, 2, 3]) is False

    def test_list_comparison_nested_dicts(self):
        """Lists of dicts are compared element-by-element with subset logic."""
        desired = [{"a": 1}]
        existing = [{"a": 1, "id": 99}]
        assert BaseModule._values_match(desired, existing) is True


class TestValidateDataFields:
    """validate_data_fields: unknown field and read-only field errors."""

    def test_raises_for_unknown_field(self, base_module):
        """A field not in the model schema raises LookupError."""
        with pytest.raises(LookupError, match="does not exist for model"):
            base_module.validate_data_fields({"totally_unknown": "val"})

    def test_raises_for_read_only_field(self, base_module):
        """Setting a read-only field raises ValueError."""
        with pytest.raises(ValueError, match="read-only and cannot be set"):
            base_module.validate_data_fields({"status": "active"})


