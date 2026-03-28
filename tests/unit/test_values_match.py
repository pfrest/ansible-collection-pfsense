"""Tests for BaseModule._values_match and BaseModule.object_needs_update."""

# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

from ansible_collections.pfrest.pfsense.plugins.module_utils.base import BaseModule


class TestValuesMatchScalar:
    def test_equal_strings(self):
        assert BaseModule._values_match("a", "a") is True

    def test_unequal_strings(self):
        assert BaseModule._values_match("a", "b") is False

    def test_equal_ints(self):
        assert BaseModule._values_match(1, 1) is True

    def test_unequal_ints(self):
        assert BaseModule._values_match(1, 2) is False

    def test_equal_bools(self):
        assert BaseModule._values_match(True, True) is True

    def test_none_does_not_match_scalars(self):
        """None only matches None, [], and {} — NOT arbitrary scalars."""
        assert BaseModule._values_match(None, "anything") is False
        assert BaseModule._values_match(None, 42) is False
        assert BaseModule._values_match(None, True) is False

    def test_none_desired_matches_empty_list(self):
        assert BaseModule._values_match(None, []) is True

    def test_none_desired_matches_empty_dict(self):
        assert BaseModule._values_match(None, {}) is True

    def test_none_vs_none(self):
        assert BaseModule._values_match(None, None) is True

    def test_empty_list_vs_none(self):
        assert BaseModule._values_match([], None) is True

    def test_empty_dict_vs_none(self):
        assert BaseModule._values_match({}, None) is True


class TestValuesMatchDict:
    def test_exact_match(self):
        assert BaseModule._values_match({"a": 1}, {"a": 1}) is True

    def test_subset_match_extra_keys_ignored(self):
        assert (
            BaseModule._values_match({"a": 1}, {"a": 1, "id": 99, "parent_id": 0})
            is True
        )

    def test_value_differs(self):
        assert BaseModule._values_match({"a": 1}, {"a": 2}) is False

    def test_missing_key_in_existing(self):
        assert BaseModule._values_match({"a": 1, "b": 2}, {"a": 1}) is False

    def test_none_value_for_missing_key(self):
        assert BaseModule._values_match({"a": 1, "b": None}, {"a": 1}) is True

    def test_nested_dict(self):
        desired = {"config": {"host": "fw1"}}
        existing = {"config": {"host": "fw1", "id": 0}, "id": 5}
        assert BaseModule._values_match(desired, existing) is True

    def test_nested_dict_difference(self):
        desired = {"config": {"host": "fw1"}}
        existing = {"config": {"host": "fw2", "id": 0}, "id": 5}
        assert BaseModule._values_match(desired, existing) is False


class TestValuesMatchList:
    def test_equal_lists(self):
        assert BaseModule._values_match([1, 2, 3], [1, 2, 3]) is True

    def test_different_values(self):
        assert BaseModule._values_match([1, 2], [1, 3]) is False

    def test_different_lengths(self):
        assert BaseModule._values_match([1], [1, 2]) is False

    def test_empty_lists(self):
        assert BaseModule._values_match([], []) is True

    def test_list_of_dicts_subset(self):
        desired = [{"host": "a"}, {"host": "b"}]
        existing = [
            {"host": "a", "id": 0, "parent_id": 0},
            {"host": "b", "id": 1, "parent_id": 0},
        ]
        assert BaseModule._values_match(desired, existing) is True

    def test_list_of_dicts_difference(self):
        desired = [{"host": "a"}]
        existing = [{"host": "z", "id": 0}]
        assert BaseModule._values_match(desired, existing) is False

    def test_desired_has_items_existing_empty(self):
        assert BaseModule._values_match([{"host": "a"}], []) is False

    def test_desired_empty_existing_has_items(self):
        assert BaseModule._values_match([], [{"host": "a"}]) is False


class TestObjectNeedsUpdate:
    def test_no_update_when_identical(self):
        assert (
            BaseModule.object_needs_update({"name": "test"}, {"name": "test", "id": 0})
            is False
        )

    def test_update_when_value_differs(self):
        assert (
            BaseModule.object_needs_update({"name": "new"}, {"name": "old", "id": 0})
            is True
        )

    def test_update_when_none_vs_scalar(self):
        """None for a key that has a non-empty scalar value is a mismatch."""
        assert (
            BaseModule.object_needs_update(
                {"name": "test", "descr": None},
                {"name": "test", "descr": "hello", "id": 0},
            )
            is True
        )

    def test_no_update_when_none_vs_missing_key(self):
        """None for a key absent in existing is 'not specified'."""
        assert (
            BaseModule.object_needs_update(
                {"name": "test", "descr": None},
                {"name": "test", "id": 0},
            )
            is False
        )

    def test_no_update_nested_match(self):
        new = {"name": "test", "aliases": [{"host": "a"}]}
        existing = {"name": "test", "aliases": [{"host": "a", "id": 0}], "id": 0}
        assert BaseModule.object_needs_update(new, existing) is False

    def test_update_nested_difference(self):
        new = {"name": "test", "aliases": [{"host": "a"}]}
        existing = {"name": "test", "aliases": [{"host": "b", "id": 0}], "id": 0}
        assert BaseModule.object_needs_update(new, existing) is True

    def test_no_update_none_vs_empty_list(self):
        assert (
            BaseModule.object_needs_update(
                {"name": "test", "aliases": None},
                {"name": "test", "aliases": [], "id": 0},
            )
            is False
        )


class TestCollectionsMatch:
    def test_matching_collections(self):
        desired = [{"name": "a"}, {"name": "b"}]
        existing = [{"name": "a", "id": 0}, {"name": "b", "id": 1}]
        assert BaseModule._collections_match(desired, existing) is True

    def test_different_lengths(self):
        assert BaseModule._collections_match([{"name": "a"}], []) is False

    def test_different_values(self):
        desired = [{"name": "a"}]
        existing = [{"name": "z", "id": 0}]
        assert BaseModule._collections_match(desired, existing) is False

    def test_empty_both(self):
        assert BaseModule._collections_match([], []) is True
