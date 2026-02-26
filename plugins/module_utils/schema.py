"""
Module containing schema-related utilities for Ansible modules.
"""
from ansible_collections.pfrest.pfsense.plugins.module_utils.rest import RestClient

import requests


class NativeSchema:
    """
    A class for interacting with the native schema of the REST API.

    Attributes:
        URL (str): The REST API endpoint URL for fetching the native schema.
        module (AnsibleModule): The Ansible module instance.
    """
    URL: str = "/api/v2/schema/native"

    rest_client: RestClient

    def __init__(self, rest_client: RestClient = None, full_schema: dict = None):
        """
        Initialize the NativeSchema object and fetch the schema.

        Args:
            rest_client (RestClient): An instance of RestClient for REST API communications. Required if an explicit
                schema is not provided.
            schema (dict): An optional pre-fetched schema dictionary. If provided, the schema will not be fetched
                from the REST API.
        """
        # Require a RestClient or a pre-fetched schema, but not both
        if rest_client is None and full_schema is None:
            raise ValueError("Either rest_client or full_schema must be provided.")
        if rest_client and full_schema:
            raise ValueError("Either a rest_client or full_schema should be provided, but not both.")

        # Initialize attributes
        self.rest_client = rest_client
        self.full_schema = full_schema if full_schema else {}

        # Fetch the schema if not provided
        if self.rest_client:
            self.fetch()

    def fetch(self) -> dict:
        """
        Fetch the full native schema from the REST API.

        Returns:
            dict: The native schema as a dictionary.
        """
        self.full_schema = self.rest_client.get(self.URL).json()
        return self.full_schema
    
    def get_endpoint_schema(self, endpoint: str) -> dict:
        """
        Get the schema for a specific endpoint by its endpoint URL

        Args:
            endpoint (str): The endpoint URL to get the schema for.

        Returns:
            dict: The endpoint schema as a dictionary.
        """
        if endpoint not in self.full_schema.get('endpoints', {}):
            raise LookupError(
                f"Could not find schema for endpoint with URL {endpoint}. This likely means the version "
                f"of pfSense-pkg-RESTAPI running on the target host does not support this endpoint."
            )
        
        return self.full_schema['endpoints'][endpoint]
    
    def get_model_schema(self, model_class: str) -> dict:
        """
        Gets the schema for a specific REST API model class by it's class name.

        Returns:
            dict: The model schema as a dictionary.
        """
        if model_class not in self.full_schema.get('models', {}):
            raise LookupError(
                f"Could not find schema for model {model_class}. This likely means the version of "
                f"pfSense-pkg-RESTAPI running on the target host does not support this model."
            )
        
        return self.full_schema['models'][model_class]

    def get_model_schema_by_endpoint(self, endpoint: str) -> dict:
        """
        Gets the schema for the model associated with a specific endpoint.

        Args:
            endpoint (str): The endpoint URL to get the model schema for.

        Returns:
            dict: The model schema as a dictionary.
        """
        endpoint_schema = self.get_endpoint_schema(endpoint)
        model_class = endpoint_schema.get('model_class', None)

        if not model_class:
            raise LookupError(
                f"Could not find a model assigned to the endpoint with URL {endpoint}."
            )
        
        return self.get_model_schema(model_class)
    
    def get_plural_endpoint_by_model(self, model_class: str) -> str:
        """
        Gets the plural endpoint URL for a given model class.

        Args:
            model_class (str): The model class name.

        Returns:
            str: The plural endpoint URL for the given model class if it exists, 
            otherwise an empty string.
        """
        for endpoint, schema in self.full_schema.get('endpoints', {}).items():
            endpoint_model_class = schema.get('model_class', None)
            endpoint_is_plural = schema.get('many', False)
            if endpoint_model_class == model_class and endpoint_is_plural:
                return endpoint
        
        return ""
    
    def get_singular_endpoint_by_model(self, model_class: str) -> str:
        """
        Gets the singular endpoint URL for a given model class.

        Args:
            model_class (str): The model class name.

        Returns:
            str: The singular endpoint URL for the given model class if it exists, 
            otherwise an empty string.
        """
        for endpoint, schema in self.full_schema.get('endpoints', {}).items():
            endpoint_model_class = schema.get('model_class', None)
            endpoint_is_plural = schema.get('many', False)
            if endpoint_model_class == model_class and not endpoint_is_plural:
                return endpoint
        
        return ""
    
    def is_endpoint_plural(self, endpoint: str) -> bool:
        """
        Determines if a given endpoint is plural (i.e., represents a collection of resources).

        Args:
            endpoint (str): The endpoint URL to check.

        Returns:
            bool: True if the endpoint is plural, False otherwise.
        """
        endpoint_schema = self.get_endpoint_schema(endpoint)
        return endpoint_schema.get('many', False)

    @staticmethod
    def from_schema_type(schema_type: str):
        """
        Converts a schema type string to a native Python type.

        Args:
            schema_type (str): The schema type to convert.

        Returns:
            type: The corresponding native Python type.
        """
        type_mapping = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "double": float,
        }
        return type_mapping.get(schema_type, str)