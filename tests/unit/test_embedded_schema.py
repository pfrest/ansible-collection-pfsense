"""Tests for accessing embedded schemas."""

from ansible_collections.pfrest.pfsense.plugins.module_utils.embedded_schema import SCHEMA_DICT

def test_embedded_schema():
    """Tests accessing embedded schema."""
    assert SCHEMA_DICT
    assert isinstance(SCHEMA_DICT, dict)
    assert "endpoints" in SCHEMA_DICT
    assert "models" in SCHEMA_DICT
