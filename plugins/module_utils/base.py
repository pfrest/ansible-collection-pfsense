"""
A module containing base utilities for Ansible modules in this collection.
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.pfrest.pfsense.plugins.module_utils.schema import NativeSchema
from ansible_collections.pfrest.pfsense.plugins.module_utils.rest import RestClient

INTERNAL_ARGS = [
    "api_host",
    "api_port",
    "api_protocol",
    "api_username",
    "api_password",
    "api_key",
    "validate_certs",
    "lookup_fields",
    "parent_lookup_query",
    "state",
]


class BaseModule:
    """
    A base class that contains all common utilities and logic for Ansible modules
    in this collection.

    Attributes:
        endpoint (str): The REST API endpoint URL for the module.
        endpoint_singular (str): The equivalent singular form of the endpoint.
        endpoint_plural (str): The equivalent plural form of the endpoint.
        full_schema (NativeSchema): An instance of the full NativeSchema for schema interactions.
        many (bool): Whether the endpoint interacts with multiple objects.
        model_schema (dict): The schema for the specific model this module interacts with.
        endpoint_schema (dict): The schema for the specific endpoint this module interacts with.
        rest_client (RestClient): An instance of RestClient for REST API communications.
    """

    module: AnsibleModule
    endpoint: str
    endpoint_singular: str
    endpoint_plural: str
    full_schema: NativeSchema
    many: bool
    model_schema: dict
    endpoint_schema: dict
    rest_client: RestClient

    def __init__(self, endpoint: str, rest_client: RestClient):
        """
        Initialize the BaseModule with connection parameters.

        Args:
            endpoint (str): The URL this module interacts with.
            rest_client (RestClient): An instance of RestClient for REST API communications.
        """
        self.rest_client = rest_client
        self.full_schema = NativeSchema()
        self.endpoint = endpoint
        self.model_schema = self.full_schema.get_model_schema_by_endpoint(self.endpoint)
        self.endpoint_schema = self.full_schema.get_endpoint_schema(self.endpoint)
        self.many = self.endpoint_schema.get("many")
        self.model_name = self.model_schema.get("class")
        self.endpoint_singular = self.full_schema.get_singular_endpoint_by_model(
            self.model_name
        )
        self.endpoint_plural = self.full_schema.get_plural_endpoint_by_model(
            self.model_name
        )

    def lookup_object(self, lookup_params: dict = None) -> dict:
        """
        Lookup an existing object based on the module's lookup fields.

        Returns:
            dict | None: The existing object if found, otherwise None.
        """
        # Variables
        lookup_params = lookup_params or {}

        # Determine the endpoint to query by the model's many attribute
        endpoint = (
            self.endpoint_plural
            if self.model_schema["many"]
            else self.endpoint_singular
        )

        # Query all objects of this model using the lookup fields
        resp_obj = self.rest_client.get(endpoint, params=lookup_params)
        resp = resp_obj.json()

        # Return an empty dict if no objects found
        if not resp.get("data", None):
            resp["data"] = {}

        # Do not proceed if the lookup fields matched multiple existing objects for 'many' models
        if self.model_schema["many"] and len(resp.get("data")) > 1:
            raise LookupError(
                f"Lookup fields matched multiple existing objects for model '{self.model_name}'."
            )

        # Always ensure 'data' is a dict, not list
        if isinstance(resp.get("data"), list):
            resp["data"] = resp["data"][0]

        # Otherwise, for non 'many' models, return the single object found
        return resp

    def create_object(self, data: dict) -> dict:
        """
        Create a new object for the module's model.

        Returns:
            dict: The full API response dictionary.
        """
        self.validate_data_fields(data)
        resp = self.rest_client.post(self.endpoint_singular, data=data)
        return resp.json()

    def update_object(self, data: dict) -> dict:
        """
        Update an existing object for the module's model.

        Args:
            data (dict): The data to update the object with.

        Returns:
            dict: The full API response dictionary.
        """
        self.validate_data_fields(data)
        resp = self.rest_client.patch(self.endpoint_singular, data=data)
        return resp.json()

    def delete_object(self, object_id: int | str) -> dict:
        """
        Delete an existing object based on the module's lookup fields.

        Args:
            object_id (int|str): The ID of the object to delete.
        """
        return self.rest_client.delete(
            self.endpoint_singular, params={"id": object_id}
        ).json()

    def lookup_objects(self, lookup_params: dict = None) -> dict:
        """
        Lookup existing objects based on the module's lookup fields.

        Args:
            lookup_params (dict): A dictionary of query parameters to filter the lookup.

        Returns:
            dict: The full API response dictionary.
        """
        # Variables
        lookup_params = lookup_params or {}

        # Query all objects of this model using the lookup fields
        resp = self.rest_client.get(self.endpoint_plural, params=lookup_params)
        return resp.json()

    def replace_objects(self, data: list[dict]) -> tuple[bool, dict]:
        """
        Replace all existing objects of the module's model with the provided list of objects.

        Before issuing the PUT request the method fetches the current objects
        from the API and performs a deep comparison.  If the desired list
        already matches what exists (ignoring read-only fields like `id`
        and `parent_id`), the PUT is skipped and `changed` is `False`.

        Args:
            data (list[dict]): The list of objects to replace existing objects with.

        Returns:
            tuple[bool, dict]: First item indicates whether any change was made,
                second item is the API response dictionary.
        """
        # Fetch current state
        existing_resp = self.rest_client.get(self.endpoint_plural).json()
        existing_objects = existing_resp.get("data", [])

        # Compare desired list against existing list
        if self._collections_match(data, existing_objects):
            return False, existing_resp

        resp = self.rest_client.put(self.endpoint_plural, data=data)
        return True, resp.json()

    @staticmethod
    def _collections_match(desired: list[dict], existing: list[dict]) -> bool:
        """
        Compare a desired list of objects against an existing list.

        Returns `True` when every desired object has a positional match in
        the existing list (using the same deep-subset logic as
        :meth:`_values_match`) *and* the lists are the same length.

        Args:
            desired: The list of objects the user wants.
            existing: The list of objects currently on the device.

        Returns:
            True if the collections are equivalent, False otherwise.
        """
        if len(desired) != len(existing):
            return False
        return all(BaseModule._values_match(d, e) for d, e in zip(desired, existing))

    def execute_action(self, data: dict) -> tuple[bool, dict]:
        """
        Executes an action with the desired parameters.

        Args:
            data (dict): The action parameters to include in the action execution

        Returns:
            tuple[bool, dict]: First item indicates whether the object was changed,
                second item is the response data
        """
        resp = self.create_object(data)
        changed = True  # We assume actions always change something
        return changed, resp

    def update_singleton(self, data: dict) -> tuple[bool, dict]:
        """
        Update a singleton endpoint with the provided data.

        Args:
            data (dict): The data to update the singleton with.

        Returns:
            tuple[bool, dict]: First item indicates whether the object was changed,
                second item is the response data
        """
        # Validate the provided data fields against the model schema
        self.validate_data_fields(data)

        # Get the existing singleton object
        existing_resp = self.rest_client.get(self.endpoint_singular).json()
        existing_object = existing_resp.get("data", {})

        # If the existing object matches the desired state, return without making an API call
        if self._values_match(data, existing_object):
            return False, existing_resp

        # Otherwise, update the singleton with a PATCH request
        resp = self.rest_client.patch(self.endpoint_singular, data=data)
        return True, resp.json()

    def resolve_parent_id(self, parent_lookup_query: dict) -> int | str:
        """
        Resolve the parent object's ID using the provided parent lookup query.

        This queries the parent model's plural endpoint using the parent lookup
        query as query parameters and returns the parent's `id`.

        Args:
            parent_lookup_query (dict): A dictionary of query parameters used to
                look up the parent object.

        Returns:
            int | str: The parent object's ID.

        Raises:
            LookupError: If the parent object cannot be found or multiple parents match.
        """
        parent_model_class = self.model_schema.get("parent_model_class", "")
        if not parent_model_class:
            raise LookupError(
                f"Model '{self.model_name}' does not have a parent model class."
            )

        # Determine the parent model's plural endpoint
        parent_plural_endpoint = self.full_schema.get_plural_endpoint_by_model(
            parent_model_class
        )

        # Query the parent endpoint
        resp = self.rest_client.get(
            parent_plural_endpoint, params=parent_lookup_query
        ).json()
        parents = resp.get("data", [])

        if not parents:
            raise LookupError(
                f"Parent lookup fields matched no existing objects for "
                f"parent model '{parent_model_class}'."
            )

        if len(parents) > 1:
            raise LookupError(
                f"Parent lookup fields matched multiple existing objects for "
                f"parent model '{parent_model_class}'."
            )

        parent = parents[0] if isinstance(parents, list) else parents
        parent_id = parent.get("id")
        if parent_id is None:
            raise LookupError(
                f"Parent object for model '{parent_model_class}' has no 'id' field."
            )

        return parent_id

    def set_object_state(
        self,
        state: str,
        data: dict,
        lookup_fields: list[str],
        parent_lookup_query: dict | None = None,
    ) -> tuple[bool, dict]:
        """
        Set the state of the object based on the desired state in module parameters.
        If the state is 'present', it will create or update the object as needed.
        If the state is 'absent', it will delete the object if it exists.

        Args:
            state (str): The desired state of the object ('present' or 'absent').
            data (dict): The data to create or update the object with.
            lookup_fields (list[str]): The fields to use for looking up the existing object.
            parent_lookup_query (dict | None): A dictionary of query parameters to use
                for looking up the parent object when the model has a parent model class.

        Returns:
            tuple[bool, dict]: First item indicates whether the object was changed,
                second item is the response data
        """
        # If parent lookup query is provided, resolve the parent ID
        if parent_lookup_query:
            parent_id = self.resolve_parent_id(parent_lookup_query)
            data["parent_id"] = parent_id

        # Construct the lookup query
        lookup_query = self.get_lookup_query(lookup_fields, data)

        # Lookup existing object
        lookup = self.lookup_object(lookup_query)
        existing_obj = lookup.get("data", {})

        # Add the ID to the data if the object exists
        if existing_obj and "id" in existing_obj:
            data["id"] = existing_obj.get("id")

        # Exclude internal args from our data
        data = self.exclude_internal_args(data)

        # When state is present and our lookup did not find an existing object, create it
        if state == "present" and not existing_obj:
            return True, self.create_object(data)

        # When state is present and our lookup found an existing object, update it if needs updating
        if (
            state == "present"
            and existing_obj
            and self.object_needs_update(data, existing_obj)
        ):
            return True, self.update_object(data)

        # When the state is absent, and the object exists, delete it
        if state == "absent" and existing_obj:
            return True, self.delete_object(existing_obj.get("id"))

        # Otherwise, nothing needs doing.
        return False, lookup

    @staticmethod
    def object_needs_update(new_object: dict, existing_object: dict) -> bool:
        """
        Determine if the existing object needs to be updated based on the provided data.

        The comparison is a *deep subset check*: for every key the caller
        supplies in `new_object`, the corresponding value in
        `existing_object` must match.  Extra keys present in the existing
        object (e.g. `id`, `parent_id`, read-only fields returned by the
        API) are ignored so that idempotent runs do not falsely report
        changes.

        Nested dicts are compared recursively.  Lists are compared
        element-by-element; when both elements are dicts the same recursive
        subset logic applies.

        Args:
            new_object (dict): The new object's data to compare against the existing object.
            existing_object (dict): The existing object retrieved from the API.

        Returns:
            bool: True if the object needs to be updated, False otherwise.
        """
        return not BaseModule._values_match(new_object, existing_object)

    @staticmethod
    def _values_match(desired, existing) -> bool:
        """
        Recursively check whether *desired* is satisfied by *existing*.

        Args:
            desired: The value the user wants.
            existing: The value currently on the device.

        Returns:
            bool: True if the values match, False otherwise.
        """
        if (
            desired is None
            and existing in [[], {}]
            or existing is None
            and desired in [[], {}]
        ):
            return True

        if isinstance(desired, dict) and isinstance(existing, dict):
            for key, desired_value in desired.items():
                if key not in existing:
                    # A None value for a missing key is still "not specified".
                    if desired_value is None:
                        continue
                    return False
                if not BaseModule._values_match(desired_value, existing[key]):
                    return False
            return True

        if isinstance(desired, list) and isinstance(existing, list):
            if len(desired) != len(existing):
                return False
            return all(
                BaseModule._values_match(d, e) for d, e in zip(desired, existing)
            )

        return desired == existing

    @staticmethod
    def get_lookup_query(lookup_fields: list, data: dict) -> dict:
        """
        Construct a query dictionary based on the module's lookup fields.

        Args:
            lookup_fields (list): A list of fields to use for the lookup query.
            data (dict): The data dictionary containing potential lookup field values.

        Returns:
            dict: A dictionary representing the lookup query.
        """
        query = {}
        for lookup_field in lookup_fields:
            query[lookup_field] = data.get(lookup_field)
        return query

    @staticmethod
    def exclude_internal_args(data: dict) -> dict:
        """
        Exclude internal arguments from the provided data dictionary.

        Args:
            data (dict): The original data dictionary containing potential internal arguments.

        Returns:
            dict: A dictionary with the internal arguments removed.
        """
        for arg in INTERNAL_ARGS:
            data.pop(arg, None)
        return data

    def validate_lookup_fields(self) -> None:
        """
        Check if the lookup fields defined in the module parameters are valid.

        Raises:
            ValueError: If no lookup fields are defined.
            LookupError: If any lookup field does not exist in the model schema.
        """
        # Ensure at least one lookup field is defined
        if not self.module.params.get("lookup_fields", []):
            raise ValueError(
                "At least one lookup field must be defined in 'lookup_fields' parameter."
            )

        # Ensure the lookup fields existing in the module schema
        for lookup_field in self.module.params.get("lookup_fields", []):
            # Always allow 'id'
            if lookup_field == "id":
                continue

            if lookup_field not in self.model_schema.get("fields", {}):
                raise LookupError(
                    f"Lookup field '{lookup_field}' does not exist for model '{self.model_name}'."
                )

    def validate_data_fields(self, data: dict) -> None:
        """
        Validate that the fields in the provided data exist in the model schema.

        Args:
            data (dict): The data dictionary to validate.

        Raises:
            LookupError: If any field in the data does not exist in the model schema.
        """
        for field in data.keys():
            # Skip internal args, 'id', and 'parent_id' (not schema-defined fields)
            if field in INTERNAL_ARGS or field in ("id", "parent_id"):
                continue

            # Ensure this field exists in the model schema
            if field not in self.model_schema.get("fields", {}):
                raise LookupError(
                    f"Field '{field}' does not exist for model '{self.model_name}'."
                )

            # Get the field schema
            field_schema = self.model_schema["fields"][field]

            # Ensure read-only fields are not being set
            if field_schema.get("read_only", False):
                raise ValueError(
                    f"Field '{field}' is read-only and cannot be set for model '{self.model_name}'."
                )

            # Validate the field type
            self.validate_field_type(field_schema, data[field])

    @staticmethod
    def validate_field_type(field_schema: dict, value) -> None:
        """
        Validate that the type of the provided value matches the expected type in the model schema.

        Args:
            field_schema (dict): The schema of the field to validate.
            value: The value to validate.

        Raises:
            TypeError: If the type of the value does not match the expected
                type in the model schema.
        """
        # Nested model fields are represented as dicts (or a list of dicts
        # when many-enabled).
        if field_schema.get("nested_model_class"):
            if field_schema.get("many"):
                # Expect a list of dicts
                if not isinstance(value, list):
                    raise TypeError(
                        f"Field '{field_schema.get('name')}' expects type 'list', "
                        f"but got type '{type(value).__name__}'."
                    )
                for item in value:
                    if not isinstance(item, dict):
                        raise TypeError(
                            f"Field '{field_schema.get('name')}' expects elements of type 'dict', "
                            f"but got type '{type(item).__name__}'."
                        )
            else:
                # Single nested object — expect a dict
                if not isinstance(value, dict):
                    raise TypeError(
                        f"Field '{field_schema.get('name')}' expects type 'dict', "
                        f"but got type '{type(value).__name__}'."
                    )
            return

        # Ensure data types match the model schema
        expected_type = NativeSchema.from_schema_type(field_schema.get("type"))

        # Required fields are only truly required if they don't have conditions
        reqd = field_schema.get("required", False) and not field_schema.get(
            "conditions", []
        )

        # Allow None values for non-required fields
        if value is None and not reqd:
            return

        # For fields that are not many-enabled, wrap the value in a list so
        # the loop below works uniformly.
        if not field_schema.get("many"):
            value = [value]

        # Iterate over each value to validate its type
        for item in value:
            if not isinstance(item, expected_type):
                raise TypeError(
                    f"Field '{field_schema.get('name')}' expects type '{expected_type.__name__}', "
                    f"but got type '{type(item).__name__}'."
                )
