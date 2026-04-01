"""Tests for BaseModule.validate_field_type and validate_data_fields."""

# pylint: disable=missing-function-docstring

import pytest
from ansible_collections.pfrest.pfsense.plugins.module_utils.base import BaseModule


class TestValidateFieldTypeScalar:
    """Non-nested field type validation."""

    def test_string_field_accepts_str(self):
        schema = {"name": "host", "type": "string", "many": False}
        BaseModule.validate_field_type(schema, "example")  # should not raise

    def test_string_field_rejects_int(self):
        schema = {"name": "host", "type": "string", "many": False}
        with pytest.raises(TypeError, match="expects type 'str'"):
            BaseModule.validate_field_type(schema, 123)

    def test_integer_field_accepts_int(self):
        schema = {"name": "port", "type": "integer", "many": False}
        BaseModule.validate_field_type(schema, 443)

    def test_integer_field_rejects_str(self):
        schema = {"name": "port", "type": "integer", "many": False}
        with pytest.raises(TypeError, match="expects type 'int'"):
            BaseModule.validate_field_type(schema, "443")

    def test_boolean_field_accepts_bool(self):
        schema = {"name": "enabled", "type": "boolean", "many": False}
        BaseModule.validate_field_type(schema, True)

    def test_boolean_field_rejects_str(self):
        schema = {"name": "enabled", "type": "boolean", "many": False}
        with pytest.raises(TypeError, match="expects type 'bool'"):
            BaseModule.validate_field_type(schema, "true")


class TestValidateFieldTypeManyScalar:
    """Many-enabled non-nested fields (list of scalars)."""

    def test_many_strings_accepts_list_of_str(self):
        schema = {"name": "tags", "type": "string", "many": True}
        BaseModule.validate_field_type(schema, ["a", "b"])

    def test_many_strings_rejects_int_element(self):
        schema = {"name": "tags", "type": "string", "many": True}
        with pytest.raises(TypeError, match="expects type 'str'"):
            BaseModule.validate_field_type(schema, ["a", 123])


class TestValidateFieldTypeNestedModel:
    """Nested model field validation."""

    def test_many_nested_accepts_list_of_dicts(self):
        schema = {
            "name": "aliases",
            "type": "array",
            "many": True,
            "nested_model_class": "SomeModel",
        }
        BaseModule.validate_field_type(schema, [{"host": "a"}])

    def test_many_nested_rejects_non_list(self):
        schema = {
            "name": "aliases",
            "type": "array",
            "many": True,
            "nested_model_class": "SomeModel",
        }
        with pytest.raises(TypeError, match="expects type 'list'"):
            BaseModule.validate_field_type(schema, {"host": "a"})

    def test_many_nested_rejects_non_dict_element(self):
        schema = {
            "name": "aliases",
            "type": "array",
            "many": True,
            "nested_model_class": "SomeModel",
        }
        with pytest.raises(TypeError, match="expects elements of type 'dict'"):
            BaseModule.validate_field_type(schema, ["not a dict"])

    def test_single_nested_accepts_dict(self):
        schema = {
            "name": "config",
            "type": "object",
            "many": False,
            "nested_model_class": "SomeModel",
        }
        BaseModule.validate_field_type(schema, {"key": "val"})

    def test_single_nested_rejects_list(self):
        schema = {
            "name": "config",
            "type": "object",
            "many": False,
            "nested_model_class": "SomeModel",
        }
        with pytest.raises(TypeError, match="expects type 'dict'"):
            BaseModule.validate_field_type(schema, [{"key": "val"}])


class TestValidateDataFields:
    """validate_data_fields checks fields against the model schema."""

    def test_skips_internal_args(self, base_module):
        data = {"api_host": "1.2.3.4", "api_protocol": "http", "name": "test"}
        base_module.validate_data_fields(data)  # should not raise

    def test_skips_id(self, base_module):
        data = {"id": 5, "name": "test"}
        base_module.validate_data_fields(data)

    def test_unknown_field_raises(self, base_module):
        with pytest.raises(LookupError, match="does not exist"):
            base_module.validate_data_fields({"nonexistent": "val"})

    def test_read_only_field_raises(self, base_module):
        with pytest.raises(ValueError, match="read-only"):
            base_module.validate_data_fields({"status": "active"})

    def test_type_mismatch_raises(self, base_module):
        with pytest.raises(TypeError):
            base_module.validate_data_fields({"enabled": "not_a_bool"})

    def test_valid_fields_pass(self, base_module):
        data = {"name": "test", "enabled": True}
        base_module.validate_data_fields(data)  # should not raise
