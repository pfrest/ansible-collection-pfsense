"""Automatically generate Ansible modules from the REST API native schema.

This script reads the pfSense REST API schema and uses Jinja2 templates to
generate fully documented Ansible module ``.py`` files.  It is driven
entirely by the schema -- when the API evolves, re-running this script
brings every module up to date.

Usage::

    python tools/module_generator.py plugins/module_utils/assets/schema.json
"""
# pylint: disable=too-many-lines

import argparse
import json
import subprocess
from pathlib import Path

import jinja2
import yaml

from ansible_collections.pfrest.pfsense.plugins.module_utils.schema import NativeSchema

# Resolved directory paths used throughout the script.
TOOLS_DIR = Path(__file__).parent
TEMPLATES_DIR = TOOLS_DIR / "templates"
MODULES_DIR = TOOLS_DIR.parent / "plugins" / "modules"
SCHEMA_DICT_PATH = TOOLS_DIR.parent / "plugins" / "module_utils" / "embedded_schema.py"
GENERATOR_CONFIG_PATH = TOOLS_DIR.parent / "generator.yml"


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments.

    Returns:
        An ``argparse.Namespace`` containing the ``schema`` path.
    """
    parser = argparse.ArgumentParser(
        description="Generate Ansible modules based on a REST API native schema file.",
    )
    parser.add_argument(
        "schema",
        type=Path,
        help="Path to the REST API native schema JSON file.",
    )
    return parser.parse_args()


args = parse_args()
native_schema = NativeSchema()


def get_module_types(endpoint_url: str) -> list[str]:
    """
    Determines the module types a given endpoint supports based on its schema.

    Args:
        endpoint_url (str): The endpoint URL to analyze.

    Returns:
        list[str]: A list of module types the endpoint supports.
    """
    module_types = []
    endpoint_schema = native_schema.full_schema["endpoints"][endpoint_url]

    # Module supports 'resource' type if POST, PATCH, DELETE and is 'many' enabled
    if is_endpoint_resource_type(endpoint_schema):
        module_types.append("resource")
    # Module supports 'collection' type if a many endpoint and supports PUT requests
    if is_endpoint_collection_type(endpoint_schema):
        module_types.append("collection")
    # Module supports 'singleton' type if a non-many endpoint and supports PATCH
    if is_endpoint_singleton_type(endpoint_schema):
        module_types.append("singleton")
    # Module supports 'action' type if a many endpoint that supports POST without PATCH or DELETE
    if is_endpoint_action_type(endpoint_schema):
        module_types.append("action")
    # Module supports 'info' type if supports GET requests
    if "GET" in endpoint_schema.get("request_method_options", []):
        module_types.append("info")

    return module_types


def is_endpoint_resource_type(endpoint_schema: dict) -> bool:
    """
    Determine if the endpoint represents a resource type. Resource types
    are individual instances that can be created, read, updated, and deleted
    within a larger collection. (e.g. a firewall rule, a static route, etc.)

    Args:
        endpoint_schema (dict): The schema of the endpoint.

    Returns:
        bool: True if the endpoint is a resource type, False otherwise.
    """
    # Not a resource type if it is a 'many' enabled endpoint
    if endpoint_schema.get("many"):
        return False

    # This is a resource type endpoint if it supports GET, POST, PATCH, DELETE methods
    supported_methods = endpoint_schema.get("request_method_options", [])
    required_methods = {"GET", "POST", "PATCH", "DELETE"}
    return required_methods.issubset(set(supported_methods))


def is_endpoint_collection_type(endpoint_schema: dict) -> bool:
    """
    Determine if the endpoint represents a collection type. Collection types
    are groups of resources that can be listed or set as a whole. (e.g. a list
    of firewall rules, a list of static routes, etc.). Collection types allow
    Ansible to manage the entire state of the collection in a single module.

    Args:
        endpoint_schema (dict): The schema of the endpoint.

    Returns:
        bool: True if the endpoint is a collection type, False otherwise.
    """
    # A collection type endpoint is one that supports GET and POST methods and is 'many' enabled
    if not endpoint_schema.get("many"):
        return False

    supported_methods = endpoint_schema.get("request_method_options", [])
    required_methods = {"GET", "PUT"}
    return required_methods.issubset(set(supported_methods))


def is_endpoint_singleton_type(endpoint_schema: dict) -> bool:
    """
    Determine if the endpoint represents a singleton type. Singleton types
    are unique resources that do not have multiple instances. (e.g. system
    settings, global configuration, etc.). Singleton types allow Ansible to
    manage the configuration of a single resource.

    Args:
        endpoint_schema (dict): The schema of the endpoint.

    Returns:
        bool: True if the endpoint is a singleton type, False otherwise.
    """
    supported_methods = endpoint_schema.get("request_method_options", [])

    # A singleton type endpoint cannot be a 'many' enabled endpoint
    if endpoint_schema.get("many"):
        return False

    # A singleton type must be an endpoint that only supports PATCH method and not POST or DELETE
    if (
        "PATCH" in supported_methods
        and "POST" not in supported_methods
        and "DELETE" not in supported_methods
    ):
        return True

    return False


def is_endpoint_action_type(endpoint_schema: dict) -> bool:
    """
    Determine if the endpoint represents an action type. Action types
    are endpoints that perform specific actions rather than managing
    resources or collections. (e.g. triggering a backup, restarting a service, etc.)

    Args:
        endpoint_schema (dict): The schema of the endpoint.

    Returns:
        bool: True if the endpoint is an action type, False otherwise.
    """
    supported_methods = endpoint_schema.get("request_method_options", [])

    # Many-enabled endpoints cannot be action types
    if endpoint_schema.get("many"):
        return False

    # Endpoint is only action type if it supports POST but not PATCH or DELETE
    if (
        "POST" in supported_methods
        and "PATCH" not in supported_methods
        and "DELETE" not in supported_methods
    ):
        return True

    return False


def is_endpoint_action_info_type(endpoint_schema: dict) -> bool:
    """
    Determine if the endpoint represents an action-info type. Action-info types
    are endpoints that provide information about actions that can be performed.
    (e.g. retrieving the status of a backup, checking the state of a service, etc.)

    Args:
        endpoint_schema (dict): The schema of the endpoint.

    Returns:
        bool: True if the endpoint is an action-info type, False otherwise.
    """
    supported_methods = endpoint_schema.get("request_method_options", [])
    required_methods = {"GET"}
    return required_methods.issubset(set(supported_methods))


def schema_type_to_ansible_type(schema_type: str) -> str:
    """
    Converts a schema type string to an Ansible module type string.

    Args:
        schema_type (str): The schema type string.

    Returns:
        str: The corresponding Ansible module type string.
    """
    type_mapping = {
        "string": "str",
        "integer": "int",
        "float": "float",
        "boolean": "bool",
        "array": "list",
    }
    return type_mapping.get(schema_type, "str")


def get_module_name(endpoint_url: str, module_type: str) -> str:
    """
    Determines the module name for a given endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        str: The module name.
    """
    # Normalize the endpoint URL to create a valid module name
    base_name = endpoint_url.removeprefix("/api/v2")
    base_name = base_name.strip("/").replace("/", "_").replace("-", "_")

    # Append the info suffix for info modules
    if module_type == "info":
        return f"{base_name}_info"

    return base_name


def get_module_short_description(endpoint_url: str, module_type: str) -> str:
    """
    Generates a short description for the module based on the endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        str: The module short description.
    """
    model = native_schema.get_model_schema_by_endpoint(endpoint_url)
    endpoint = native_schema.get_endpoint_schema(endpoint_url)
    model_name = model["verbose_name"]
    model_name_plural = model["verbose_name_plural"]

    if module_type == "info" and endpoint["many"]:
        return f"Retrieve information about many {model_name_plural}."
    if module_type == "info" and not endpoint["many"] and model["many"]:
        return f"Retrieve information about a single {model_name}."
    if module_type == "info" and not endpoint["many"] and not model["many"]:
        return f"Retrieve information about the {model_name}."
    if module_type == "resource":
        return f"Manage individual {model_name_plural}."
    if module_type == "collection":
        return f"Manage all {model_name_plural}."
    if module_type == "singleton":
        return f"Manage {model_name_plural}."
    if module_type == "action":
        return f"Perform the {model_name} action."

    return f"Module for {endpoint_url}."


def get_module_options_for_info_module(endpoint_url: str) -> dict:
    """
    Generates the module options documentation for an info module based on the endpoint.

    Args:
        endpoint_url (str): The endpoint URL.

    Returns:
        dict: The module options for the info module.
    """
    endpoint_schema = native_schema.get_endpoint_schema(endpoint_url)
    opts = {}

    if endpoint_schema["many"]:
        opts["query_params"] = {
            "type": "dict",
            "description": "Optional query parameters for filtering the results.",
        }
        return opts

    opts["lookup_params"] = {
        "type": "dict",
        "description": "Parameters to lookup the specific resource to retrieve.",
    }
    return opts


def get_module_options_for_collection_module(endpoint_url: str) -> dict:
    """
    Generates the module options documentation for a collection module based on the endpoint.

    Args:
        endpoint_url (str): The endpoint URL.

    Returns:
        dict: The module options for the collection module.
    """
    return {
        "objects": {
            "type": "list",
            "elements": "dict",
            "required": True,
            "suboptions": get_module_options_from_fields(endpoint_url),
            "description": "The list of items to manage in the collection. Each item "
            "should be a dictionary representing the desired state of "
            "a single resource within the collection.",
        }
    }


def get_module_options_for_resource_module(endpoint_url: str) -> dict:
    """
    Generates the module options documentation for a resource module based on the endpoint.

    Args:
        endpoint_url (str): The endpoint URL.

    Returns:
        dict: The module options for the resource module.
    """
    return {
        "state": {
            "type": "str",
            "choices": ["present", "absent"],
            "default": "present",
            "description": "Whether the resource should be present or absent.",
        },
        "lookup_fields": {
            "type": "list",
            "elements": "str",
            "required": True,
            "description": "The list of fields to use when looking up existing resources. "
            "This should be a list of field names that uniquely identify a "
            "resource.",
        },
        **get_module_options_from_fields(endpoint_url),
    }


def get_module_options_from_fields(endpoint_url: str) -> dict:
    """
    Generates the module options documentation based on the endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.

    Returns:
        dict: The module options based on the fields defined in the model schema for the endpoint.
    """
    model_schema = native_schema.get_model_schema_by_endpoint(endpoint_url)
    return _build_field_options(model_schema, visited=set())


def _build_field_options(model_schema: dict, visited: set) -> dict:
    """
    Build the module options dict from a model schema's fields.

    This is the recursive workhorse behind :func:`get_module_options_from_fields`.
    When a field references a nested model (via ``nested_model_class``), the
    function recurses into that model to produce ``suboptions``.

    Args:
        model_schema: The model schema dict containing a ``fields`` mapping.
        visited: A set of model class names already processed (cycle guard).

    Returns:
        A dict mapping field names to their Ansible option metadata.
    """
    opts = {}
    for field_name, field_schema in model_schema.get("fields", {}).items():
        if field_schema.get("read_only", False):
            continue

        # Remove any excessive whitespace and newlines from the help text
        descr = field_schema.get("help_text", "")
        descr = " ".join(filter(None, descr.split())).replace("\n", " ")

        base_type = schema_type_to_ansible_type(field_schema.get("type", "str"))

        # Required fields are only truly required if they don't have conditions
        required = field_schema.get("required", False) and not field_schema.get(
            "conditions", []
        )

        opts[field_name] = {
            "required": required,
            "type": base_type,
            "default": field_schema.get("default", None),
            "choices": field_schema.get("choices", None),
            "no_log": field_schema.get("sensitive", False),
            "description": descr,
        }

        # If the field is 'many' enabled and not already a list type, wrap it as a list
        if field_schema.get("many", False) and base_type != "list":
            opts[field_name]["type"] = "list"
            opts[field_name]["elements"] = base_type

        # Recursively build suboptions for nested model fields
        nested_model_class = field_schema.get("nested_model_class")
        if nested_model_class and nested_model_class not in visited:
            try:
                nested_model_schema = native_schema.get_model_schema(nested_model_class)
                nested_opts = _build_field_options(
                    nested_model_schema, visited | {nested_model_class}
                )
                if nested_opts:
                    opts[field_name]["type"] = "list"
                    opts[field_name]["elements"] = "dict"
                    opts[field_name]["suboptions"] = nested_opts
            except LookupError:
                pass

    return opts


def get_module_options(endpoint_url: str, module_type: str) -> dict:
    """
    Generates the module options documentation based on the endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        dict: The module options based on the endpoint and module type.
    """
    standard_options = {
        "api_host": {
            "type": "str",
            "required": True,
            "description": "The hostname or IP address of the pfSense device.",
        },
        "api_port": {
            "type": "int",
            "default": 443,
            "description": "The port number of the pfSense API.",
        },
        "api_username": {
            "type": "str",
            "default": "admin",
            "description": "The username to authenticate with the pfSense API.",
        },
        "api_password": {
            "type": "str",
            "default": "pfsense",
            "no_log": True,
            "description": "The password to authenticate with the pfSense API.",
        },
        "api_key": {
            "type": "str",
            "no_log": True,
            "description": "An API key to use for authentication.",
        },
        "validate_certs": {
            "type": "bool",
            "default": True,
            "description": "Whether to validate SSL certificates when connecting to the API.",
        },
    }

    if module_type == "info":
        return {**standard_options, **get_module_options_for_info_module(endpoint_url)}
    if module_type == "collection":
        return {
            **standard_options,
            **get_module_options_for_collection_module(endpoint_url),
        }
    if module_type == "resource":
        return {
            **standard_options,
            **get_module_options_for_resource_module(endpoint_url),
        }

    return {**standard_options, **get_module_options_from_fields(endpoint_url)}


def schema_type_to_returns_type(schema_type: str) -> str:
    """
    Converts a schema type string to an Ansible RETURNS type string.

    Args:
        schema_type (str): The schema type string.

    Returns:
        str: The corresponding Ansible RETURNS type string.
    """
    type_mapping = {
        "string": "str",
        "integer": "int",
        "float": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }
    return type_mapping.get(schema_type, "str")


def get_returns_contains_for_model(model_class: str, visited: set = None) -> dict:
    """
    Recursively builds the 'contains' dict for a model's fields for use in RETURNS documentation.
    Uses a visited set to prevent infinite recursion on circular model references.

    Args:
        model_class (str): The model class name to build the contains dict for.
        visited (set): A set of already-visited model class names to avoid recursion.

    Returns:
        dict: A dict mapping field names to their RETURNS documentation entries.
    """
    if visited is None:
        visited = set()
    if model_class in visited:
        return {}
    visited = visited | {model_class}

    if model_class not in native_schema.full_schema.get("models", {}):
        return {}

    model_schema = native_schema.get_model_schema(model_class)
    contains = {}

    for field_name, field_schema in model_schema.get("fields", {}).items():
        # Skip write-only fields - they are not included in API responses
        if field_schema.get("write_only", False):
            continue

        # Clean up help text
        help_text = field_schema.get("help_text", "")
        help_text = " ".join(filter(None, help_text.split()))

        field_entry = {
            "description": help_text
            or f"The {field_name.replace('_', ' ')} of the object.",
            "type": schema_type_to_returns_type(field_schema.get("type", "string")),
            "returned": "always",
        }

        # If the field is 'many' enabled and not already a list type, wrap it as a list
        base_returns_type = schema_type_to_returns_type(
            field_schema.get("type", "string")
        )
        if field_schema.get("many", False) and base_returns_type != "list":
            field_entry["type"] = "list"
            field_entry["elements"] = base_returns_type

        # Recursively handle nested model fields
        nested_model = field_schema.get("nested_model_class")
        if nested_model:
            nested_contains = get_returns_contains_for_model(nested_model, visited)
            if nested_contains:
                field_entry["elements"] = "dict"
                field_entry["contains"] = nested_contains

        contains[field_name] = field_entry

    return contains


def get_example_value_for_field(field_schema: dict, visited: set | None = None):
    """
    Returns a realistic example value for a field based on its schema.

    Args:
        field_schema (dict): The schema dict for the field.
        visited (set | None): Model class names already visited (cycle guard).

    Returns:
        A representative example value for the field.
    """
    visited = visited or set()
    is_many = field_schema.get("many", False)

    # Handle nested model fields by building an example from the nested model's fields
    nested_model_class = field_schema.get("nested_model_class")
    if nested_model_class and nested_model_class not in visited:
        try:
            nested_schema = native_schema.get_model_schema(nested_model_class)
            child_visited = visited | {nested_model_class}
            writable = {
                n: s
                for n, s in nested_schema.get("fields", {}).items()
                if not s.get("read_only", False)
            }

            # Use required fields first; fall back to first 2 optional fields
            example_obj = {
                n: get_example_value_for_field(s, child_visited)
                for n, s in writable.items()
                if s.get("required", False)
            }
            if not example_obj:
                example_obj = {
                    n: get_example_value_for_field(s, child_visited)
                    for n, s in list(writable.items())[:2]
                }

            return [example_obj] if is_many else example_obj
        except LookupError:
            pass

    # Use first available choice for constrained fields
    choices = field_schema.get("choices") or []
    if choices:
        value = choices[0]
    # Use the default value if it is meaningful
    elif field_schema.get("default") not in (None, "", []):
        value = field_schema["default"]
    # Fall back to type-based placeholders
    else:
        plcholders = {
            "string": "string",
            "integer": 1,
            "float": 1.0,
            "boolean": False,
            "array": [],
        }
        value = plcholders.get(field_schema.get("type", "string"), "string")

    # Wrap in a list for many-enabled fields that aren't already a list type
    if is_many and not isinstance(value, list):
        return [value]

    return value


def generate_module_returns(endpoint_url: str, module_type: str) -> dict:
    """
    Generates the RETURNS documentation dict for a module based on its endpoint and type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        dict: The RETURNS documentation as a dictionary that can be serialized to YAML.
    """
    model_schema = native_schema.get_model_schema_by_endpoint(endpoint_url)
    endpoint_schema = native_schema.get_endpoint_schema(endpoint_url)

    # Build the 'contains' mapping from model fields (excluding write-only)
    contains = get_returns_contains_for_model(model_schema["class"])

    # For many-endpoint info/collection modules, the response data is a list
    if module_type in ("collection",) or (
        module_type == "info" and endpoint_schema.get("many")
    ):
        data_entry = {
            "description": f"A list of {model_schema['verbose_name_plural']} returned by the API.",
            "type": "list",
            "elements": "dict",
            "returned": "always",
        }
    else:
        data_entry = {
            "description": f"The {model_schema['verbose_name']} data returned by the API.",
            "type": "dict",
            "returned": "always",
        }

    if contains:
        data_entry["contains"] = contains

    return {
        "changed": {
            "description": "Whether any changes were made.",
            "type": "bool",
            "returned": "always",
        },
        "status": {
            "description": "The HTTP status code of the API response.",
            "type": "int",
            "returned": "always",
        },
        "response_id": {
            "description": "The unique response/error ID from the API.",
            "type": "str",
            "returned": "always",
        },
        "msg": {
            "description": "A status message from the API.",
            "type": "str",
            "returned": "always",
        },
        "data": data_entry,
    }


def generate_module_examples(endpoint_url: str, module_type: str) -> list:
    """
    Generates a list of example task dicts for a module based on its endpoint and type.
    Each task dict represents a single Ansible task playbook entry and can be serialized to YAML.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        list: A list of task dicts representing usage examples for the module.
    """
    # pylint: disable=too-many-locals,too-many-branches
    model_schema = native_schema.get_model_schema_by_endpoint(endpoint_url)
    endpoint_schema = native_schema.get_endpoint_schema(endpoint_url)
    module_name = get_module_name(endpoint_url, module_type)
    model_name = model_schema["verbose_name"]
    model_name_plural = model_schema["verbose_name_plural"]
    fqcn = f"pfrest.pfsense.{module_name}"

    # Standard connection parameters shared by all examples
    connection_params = {
        "api_host": "pfsense.example.com",
        "api_username": "admin",
        "api_password": "pfsense",
    }

    # Separate writable fields into required and optional
    required_fields = {}
    optional_fields = {}
    for field_name, field_schema in model_schema.get("fields", {}).items():
        if field_schema.get("read_only", False) or field_schema.get(
            "write_only", False
        ):
            continue
        value = get_example_value_for_field(field_schema)
        if field_schema.get("required", False):
            required_fields[field_name] = value
        else:
            optional_fields[field_name] = value

    examples = []

    if module_type == "resource":
        # Present example with all required fields
        examples.append(
            {
                "name": f"Create {model_name}",
                fqcn: {**connection_params, "state": "present", **required_fields},
            }
        )
        # Absent example showing how to delete the resource
        examples.append(
            {
                "name": f"Delete {model_name}",
                fqcn: {**connection_params, "state": "absent", **required_fields},
            }
        )

    elif module_type == "collection":
        # Show a representative object inside the objects list
        obj = dict(required_fields)
        for k, v in list(optional_fields.items())[:2]:
            obj[k] = v
        examples.append(
            {
                "name": f"Manage all {model_name_plural}",
                fqcn: {**connection_params, "objects": [obj] if obj else [{}]},
            }
        )

    elif module_type == "singleton":
        params = dict(connection_params)
        params.update(required_fields)
        # Include a few optional fields when there are no required fields to make the example useful
        if not required_fields:
            for k, v in list(optional_fields.items())[:3]:
                params[k] = v
        examples.append({"name": f"Manage {model_name}", fqcn: params})

    elif module_type == "action":
        params = dict(connection_params)
        params.update(required_fields)
        examples.append({"name": f"Perform {model_name} action", fqcn: params})

    elif module_type == "info":
        if endpoint_schema.get("many"):
            examples.append(
                {
                    "name": f"Retrieve all {model_name_plural}",
                    fqcn: dict(connection_params),
                }
            )
        else:
            examples.append(
                {
                    "name": f"Retrieve {model_name}",
                    fqcn: {**connection_params, "lookup_params": {}},
                }
            )

    return examples


def _strip_argspec_only_keys(options: dict) -> dict:
    """Return a deep copy of *options* with argument_spec-only keys removed.

    Keys like ``no_log`` are valid in the Python ``argument_spec`` but are
    **not** permitted in Ansible's ``DOCUMENTATION`` YAML schema.  This
    helper recursively walks the options tree and drops those keys so the
    generated ``DOCUMENTATION`` passes ``antsibull-docs`` validation.

    Args:
        options: The module options dict (may contain nested ``suboptions``).

    Returns:
        A new dict safe for use in the ``DOCUMENTATION`` string.
    """
    # Keys that belong in argument_spec but NOT in DOCUMENTATION options
    _argspec_only = {"no_log"}

    cleaned: dict = {}
    for name, spec in options.items():
        new_spec = {k: v for k, v in spec.items() if k not in _argspec_only}
        if "suboptions" in new_spec:
            new_spec["suboptions"] = _strip_argspec_only_keys(new_spec["suboptions"])
        cleaned[name] = new_spec
    return cleaned


def generate_module_documentation(endpoint_url: str, module_type: str) -> dict:
    """
    Generates the module documentation string based on the endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        dict: The module documentation as a dictionary that can be serialized t
            o YAML for the Ansible module DOCUMENTATION string.
    """
    return {
        "module": get_module_name(endpoint_url, module_type),
        "description": [get_module_short_description(endpoint_url, module_type)],
        "short_description": get_module_short_description(endpoint_url, module_type),
        "options": _strip_argspec_only_keys(
            get_module_options(endpoint_url, module_type)
        ),
        "author": ["Jared Hendrickson (@jaredhendrickson13)"],
    }


def schema_to_dict_file(schema_json: str, template: jinja2.Template) -> None:
    """Embed the native schema as a Python dict in ``schema_dict.py``.

    This allows modules to load the schema at runtime without reading a
    JSON file from the filesystem (which fails inside Ansible's zip
    payload).

    Args:
        schema_json (str): The native schema as a JSON-formatted string.
        template (jinja2.Template): The template to use for rendering.
    """
    try:
        data_dict = json.loads(schema_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON string provided: {exc}")
        return

    try:
        with open(SCHEMA_DICT_PATH, "w", encoding="utf-8") as fh:
            fh.write(template.render(schema_dict=data_dict))
    except OSError as exc:
        print(f"File writing error: {exc}")


def load_generator_config() -> dict:
    """Load the generator configuration from ``generator.yml``.

    The config file lives alongside this script and may contain an
    ``exclude_modules`` list of module names to skip during generation.

    Returns:
        The parsed YAML configuration as a dict, or an empty dict if the
        file does not exist or is empty.
    """
    if not GENERATOR_CONFIG_PATH.exists():
        return {}
    with GENERATOR_CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def create_jinja_env() -> jinja2.Environment:
    """Create and configure the Jinja2 template environment.

    The environment is pointed at the ``templates/`` directory next to
    this script and has a custom ``repr`` filter registered for use in
    the module-args template.

    Returns:
        A ready-to-use ``jinja2.Environment``.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(searchpath=TEMPLATES_DIR),
    )
    env.filters["repr"] = repr
    return env


def render_module(
    endpoint_url: str,
    module_type: str,
    template: jinja2.Template,
) -> str:
    """Render a single Ansible module source file from the Jinja2 template.

    Generates the DOCUMENTATION, EXAMPLES, and RETURNS YAML blocks from
    the schema then feeds them, along with the runtime module-args dict,
    into the template.

    Args:
        endpoint_url: The REST API endpoint URL to generate a module for.
        module_type: The module type string (e.g. ``"resource"``).
        template: The pre-loaded Jinja2 ``module.py.j2`` template.

    Returns:
        The fully rendered Python source code for the module.
    """
    doc = generate_module_documentation(endpoint_url, module_type)
    # module_args needs the full options (including no_log); doc["options"]
    # has already been stripped of argument_spec-only keys for DOCUMENTATION.
    module_args = get_module_options(endpoint_url, module_type)
    return template.render(
        module_args=module_args,
        module_type=module_type,
        endpoint_schema=native_schema.get_endpoint_schema(endpoint_url),
        documentation=yaml.dump(doc, sort_keys=False, indent=2),
        returns=yaml.dump(
            generate_module_returns(endpoint_url, module_type),
            sort_keys=False,
            indent=2,
        ),
        examples=yaml.dump(
            generate_module_examples(endpoint_url, module_type),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ),
    )


def main() -> None:
    """Entry-point: embed the schema dict, then generate all modules."""
    global native_schema  # pylint: disable=global-statement

    # Load generator config (contains the exclude list).
    config = load_generator_config()
    exclude_modules: list[str] = config.get("exclude_modules") or []

    # Prepare the Jinja2 environment and template once (not per-module).
    env = create_jinja_env()
    template = env.get_template("module.py.j2")

    # Embed the schema as a Python dict for runtime use by modules.
    # below also uses the fresh data.
    with args.schema.open("r", encoding="utf-8") as fh:
        print("Embedding native schema from JSON file... ", end="")
        schema_to_dict_file(
            fh.read(), template=env.get_template("embedded_schema.py.j2")
        )
        print("done.")
    native_schema = NativeSchema()

    # Walk every endpoint and generate the appropriate module(s).
    generated_files: list[Path] = []
    for endpoint_url in native_schema.full_schema.get("endpoints", {}).keys():
        for module_type in get_module_types(endpoint_url):
            module_name = get_module_name(endpoint_url, module_type)

            # Honour the exclude list from generator.yml.
            if module_name in exclude_modules:
                print(f"Skipping excluded module '{module_name}'... done.")
                continue

            # Render the module source and write it to disk.
            print(f"Generating module '{module_name}'... ", end="")
            source = render_module(endpoint_url, module_type, template)
            output_path = MODULES_DIR / f"{module_name}.py"
            output_path.write_text(source, encoding="utf-8")
            generated_files.append(output_path)
            print("done.")

    # Auto-format all generated files in a single black invocation.
    if generated_files:
        print(
            f"Formatting {len(generated_files)} generated file(s) with black... ",
            end="",
        )
        try:
            subprocess.run(
                ["black", "--quiet", *(str(p) for p in generated_files)],
                check=True,
            )
            print("done.")
        except subprocess.CalledProcessError as exc:
            print(f"failed (exit {exc.returncode}).")


if __name__ == "__main__":
    main()
