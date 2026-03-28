"""Tests for NativeSchema utility methods."""

# pylint: disable=missing-function-docstring,attribute-defined-outside-init
# pylint: disable=import-outside-toplevel

import pytest

from ansible_collections.pfrest.pfsense.plugins.module_utils.schema import NativeSchema


class TestFromSchemaType:
    """NativeSchema.from_schema_type — static, no schema needed."""

    def test_string(self):
        assert NativeSchema.from_schema_type("string") is str

    def test_integer(self):
        assert NativeSchema.from_schema_type("integer") is int

    def test_boolean(self):
        assert NativeSchema.from_schema_type("boolean") is bool

    def test_array(self):
        assert NativeSchema.from_schema_type("array") is list

    def test_object(self):
        assert NativeSchema.from_schema_type("object") is dict

    def test_double(self):
        assert NativeSchema.from_schema_type("double") is float

    def test_unknown_defaults_to_str(self):
        assert NativeSchema.from_schema_type("unknown_type") is str


class TestSchemaLookups:
    """Schema lookup methods using the real embedded schema."""

    @pytest.fixture(autouse=True)
    def _schema(self):
        self.ns = NativeSchema()

    def test_get_endpoint_schema_valid(self):
        schema = self.ns.get_endpoint_schema("/api/v2/firewall/rule")
        assert "model_class" in schema

    def test_get_endpoint_schema_invalid(self):
        with pytest.raises(LookupError, match="Could not find schema"):
            self.ns.get_endpoint_schema("/api/v2/nonexistent")

    def test_get_model_schema_valid(self):
        schema = self.ns.get_endpoint_schema("/api/v2/firewall/rule")
        model = self.ns.get_model_schema(schema["model_class"])
        assert "fields" in model

    def test_get_model_schema_invalid(self):
        with pytest.raises(LookupError, match="Could not find schema"):
            self.ns.get_model_schema("NonExistentModel")

    def test_get_model_schema_by_endpoint(self):
        model = self.ns.get_model_schema_by_endpoint("/api/v2/firewall/rule")
        assert "fields" in model
        assert "class" in model

    def test_get_model_schema_by_endpoint_missing_model_class(self, monkeypatch):
        """Endpoint exists but has no model_class assigned."""
        from ansible_collections.pfrest.pfsense.plugins.module_utils import (
            schema as schema_mod,
        )

        patched_schema = {
            "endpoints": {
                "/api/v2/no_model": {
                    "url": "/api/v2/no_model",
                    "model_class": None,
                    "many": False,
                }
            },
            "models": {},
        }
        monkeypatch.setattr(schema_mod, "SCHEMA_DICT", patched_schema)
        ns = NativeSchema()
        with pytest.raises(LookupError, match="Could not find a model assigned"):
            ns.get_model_schema_by_endpoint("/api/v2/no_model")

    def test_get_plural_endpoint(self):
        schema = self.ns.get_endpoint_schema("/api/v2/firewall/rule")
        plural = self.ns.get_plural_endpoint_by_model(schema["model_class"])
        assert plural != ""
        assert self.ns.is_endpoint_plural(plural) is True

    def test_get_singular_endpoint(self):
        schema = self.ns.get_endpoint_schema("/api/v2/firewall/rule")
        singular = self.ns.get_singular_endpoint_by_model(schema["model_class"])
        assert singular != ""
        assert self.ns.is_endpoint_plural(singular) is False

    def test_get_plural_endpoint_unknown_model(self):
        assert self.ns.get_plural_endpoint_by_model("FakeModel") == ""

    def test_get_singular_endpoint_unknown_model(self):
        assert self.ns.get_singular_endpoint_by_model("FakeModel") == ""
