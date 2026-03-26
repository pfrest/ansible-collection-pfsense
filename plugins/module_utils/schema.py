"""
Module containing schema-related utilities for Ansible modules.
"""
import json

from .schema_dict import SCHEMA_DICT


class NativeSchema:
    """
    A class for interacting with the native schema of the REST API.
    """
    def __init__(self):
        """
        Initialize the NativeSchema object and fetch the schema.
        """
        self.full_schema = SCHEMA_DICT
    
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