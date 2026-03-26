"""
A module containing base utilities for Ansible modules in this collection.
"""
from ansible.module_utils.basic import AnsibleModule

from ansible_collections.pfrest.pfsense.plugins.module_utils.schema import NativeSchema
from ansible_collections.pfrest.pfsense.plugins.module_utils.rest import RestClient


INTERNAL_ARGS = ['api_host', 'api_port', 'api_username', 'api_password', 'api_key', 'validate_certs', 'lookup_fields', 'state']


class BaseModule:
    """
    A base class that contains all common utilities and logic for Ansible modules in this collection.

    Attributes:
        endpoint (str): The REST API endpoint URL for the module. Required to be set by subclass to lookup schema.
        endpoint_singular (str): The equivalent singular form of the endpoint. Auto-sets from schema.
        endpoint_plural (str): The equivalent plural form of the endpoint. Auto-sets from schema.
        full_schema (NativeSchema): An instance of the full NativeSchema for schema interactions.
        many (bool): Whether the endpoint interacts with multiple objects. Auto-sets from schema.
        model_schema (dict): The schema for the specific model this module interacts with. Auto-sets from schema.
        endpoint_schema (dict): The schema for the specific endpoint this module interacts with. Auto-sets from schema.
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
        self.endpoint_singular = self.full_schema.get_singular_endpoint_by_model(self.model_name)
        self.endpoint_plural = self.full_schema.get_plural_endpoint_by_model(self.model_name)

    def lookup_object(self, lookup_params: dict = None) -> dict:
        """
        Lookup an existing object based on the module's lookup fields.

        Returns:
            dict | None: The existing object if found, otherwise None.
        """
        # Variables
        lookup_params = lookup_params or {}

        # Determine the endpoint to query by the model's many attribute
        endpoint = self.endpoint_plural if self.model_schema["many"] else self.endpoint_singular

        # Query all objects of this model using the lookup fields
        resp_obj = self.rest_client.get(endpoint, params=lookup_params)
        resp = resp_obj.json()

        # Return an empty dict if no objects found
        if not resp.get("data", None):
            resp['data'] = {}

        # Do not proceed if the lookup fields matched multiple existing objects for 'many' models
        if self.model_schema["many"] and len(resp.get('data')) > 1:
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

    def delete_object(self, object_id: int|str) -> dict:
        """
        Delete an existing object based on the module's lookup fields.

        Args:
            object_id (int|str): The ID of the object to delete.
        """
        return self.rest_client.delete(self.endpoint_singular, params={"id": object_id}).json()

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

    def replace_objects(self, data: list[dict]) -> dict:
        """
        Replace all existing objects of the module's model with the provided list of objects.

        Args:
            data (list[dict]): The list of objects to replace existing objects with.

        Returns:
            dict: The full API response dictionary.
        """
        resp = self.rest_client.put(self.endpoint_plural, data=data)
        return resp.json()

    def execute_action(self, data: dict) -> tuple[bool, dict]:
        """
        Executes an action with the desired parameters.

        Args:
            data (dict): The action parameters to include in the action execution

        Returns:
            tuple[bool, dict]: First item indicates whether the object was changed, second item is the response data
        """
        resp = self.create_object(data)
        changed = True  # TODO: Determine if the action actually changed something
        return changed, resp

    def set_object_state(self, state: str, data: dict, lookup_fields: list[str]) -> tuple[bool, dict]:
        """
        Set the state of the object based on the desired state in module parameters.
        If the state is 'present', it will create or update the object as needed.
        If the state is 'absent', it will delete the object if it exists.

        Args:
            state (str): The desired state of the object ('present' or 'absent').
            data (dict): The data to create or update the object with.
            lookup_fields (list[str]): The fields to use for looking up the existing object.

        Returns:
            tuple[bool, dict]: First item indicates whether the object was changed, second item is the response data
        """
        # Construct the lookup query
        lookup_query = self.get_lookup_query(lookup_fields, data)

        # Lookup existing object
        lookup = self.lookup_object(lookup_query)
        existing_object = lookup.get("data", {})

        # Add the ID to the data if the object exists
        if existing_object and "id" in existing_object:
            data["id"] = existing_object.get("id")

        # Exclude internal args from our data
        data = self.exclude_internal_args(data)

        # When state is present and our lookup did not find an existing object, create it
        if state == 'present' and not existing_object:
            return True, self.create_object(data)

        # When state is present and our lookup found an existing object, update it if needs updating
        if state == 'present' and existing_object and self.object_needs_update(data, existing_object):
            return True, self.update_object(data)

        # When the state is absent, and the object exists, delete it
        if state == 'absent' and existing_object:
            return True, self.delete_object(existing_object.get("id"))

        # Otherwise, nothing needs doing.
        return False, lookup

    @staticmethod
    def object_needs_update(new_object: dict, existing_object: dict) -> bool:
        """
        Determine if the existing object needs to be updated based on the provided data.

        Args:
            new_object (dict): The new object's data to compare against the existing object.
            existing_object (dict): The existing object retrieved from the API.

        Returns:
            bool: True if the object needs to be updated, False otherwise.
        """
        for key, value in new_object.items():
            if existing_object.get(key) != value:
                return True
        return False

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
            del data[arg]
        return data


    def validate_lookup_fields(self) -> None:
        """
        Check if the lookup fields defined in the module parameters are valid.

        Raises:
            ValueError: If no lookup fields are defined.
            LookupError: If any lookup field does not exist in the model schema.
        """
        # Ensure at least one lookup field is defined
        if not self.module.params.get('lookup_fields', []):
            raise ValueError("At least one lookup field must be defined in 'lookup_fields' parameter.")

        # Ensure the lookup fields existing in the module schema
        for lookup_field in self.module.params.get('lookup_fields', []):
            # Always allow 'id'
            if lookup_field == 'id':
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
            # Skip internal args or 'id' (since it's not a schema defined field)
            if field in INTERNAL_ARGS or field == 'id':
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
            TypeError: If the type of the value does not match the expected type in the model schema.
        """
        # Ensure data types match the model schema
        expected_type = NativeSchema.from_schema_type(field_schema.get("type"))

        # For fields that are not many-enabled, wrap the expected type in a list
        if not field_schema.get("many"):
            value = [value]

        # Iterate over each value to validate its type
        for item in value:
            if not isinstance(item, expected_type):
                raise TypeError(
                    f"Field '{field_schema.get('name')}' expects type '{expected_type.__name__}', "
                    f"but got type '{type(item).__name__}'."
                )
