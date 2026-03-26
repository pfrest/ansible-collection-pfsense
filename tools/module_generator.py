"""
A helper script o automatically generate Ansible modules based on the REST API schema.
"""
import json
import yaml
import argparse
import jinja2
from pathlib import Path

from ansible_collections.pfrest.pfsense.plugins.module_utils.schema import NativeSchema

# Set up argument parsing
argparse = argparse.ArgumentParser(
    description="Generate Ansible modules based on a REST API native schema file."
)
argparse.add_argument(
    "schema",
    type=Path,
    help="Path to the REST API native schema JSON file.",
)
args = argparse.parse_args()

# Load the schema file into a NativeSchema object
with args.schema.open("r", encoding="utf-8") as schema_file:
    native_schema_json = json.load(schema_file)
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
    endpoint_schema = native_schema.full_schema['endpoints'][endpoint_url]

    # Module supports 'resource' type if it supports POST, PATCH, DELETE and is 'many' enabled
    if is_endpoint_resource_type(endpoint_schema):
        module_types.append('resource')
    # Module supports 'collection' type if it is a many endpoint and supports PUT requests
    if is_endpoint_collection_type(endpoint_schema):
        module_types.append('collection')
    # Module supports 'singleton' type if it is a non-many endpoint and supports PATCH
    if is_endpoint_singleton_type(endpoint_schema):
        module_types.append('singleton')
    # Module supports 'action' type if it is a many endpoint that supports POST without PATCH or DELETE
    if is_endpoint_action_type(endpoint_schema):
        module_types.append('action')
    # Module supports 'info' type if it supports GET requests
    if "GET" in endpoint_schema.get("request_method_options", []):
        module_types.append('info')

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
    if "PATCH" in supported_methods and "POST" not in supported_methods and "DELETE" not in supported_methods:
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
    if "POST" in supported_methods and "PATCH" not in supported_methods and "DELETE" not in supported_methods:
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
        "array": "list"
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
    elif module_type == "info" and not endpoint["many"] and model["many"]:
        return f"Retrieve information about a single {model_name}."
    elif module_type == "info" and not endpoint["many"] and not model["many"]:
        return f"Retrieve information about the {model_name}."
    elif module_type == "resource":
        return f"Manage individual {model_name_plural}."
    elif module_type == "collection":
        return f"Manage all {model_name_plural}."
    elif module_type == "singleton":
        return f"Manage {model_name_plural}."
    elif module_type == "action":
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
        opts["query_params"] = {"type": "dict", "description": "Optional query parameters for filtering the results."}
        return opts

    opts["lookup_params"] = {"type": "dict", "description": "Parameters to lookup the specific resource to retrieve."}
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
            "description": "The list of items to manage in the collection. Each item should be a dictionary "
                           "representing the desired state of a single resource within the collection."
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
            "description": "Whether the resource should be present or absent."
        },
        "lookup_fields": {
            "type": "list",
            "elements": "str",
            "required": True,
            "description": "The list of fields to use when looking up existing resources. This should be a list of "
                           "field names that uniquely identify a resource."
        },
        **get_module_options_from_fields(endpoint_url)
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
    opts = {}
    for field_name, field_schema in model_schema.get("fields", {}).items():
        if field_schema.get("read_only", False):
            continue

        # Remove any excessive whitespace and newlines from the help text
        descr = field_schema.get("help_text", "")
        descr = " ".join(filter(None, descr.split())).replace("\n", " ")

        base_type = schema_type_to_ansible_type(field_schema.get("type", "str"))

        opts[field_name] = {
            "required": field_schema.get("required", False),
            "type": base_type,
            "default": field_schema.get("default", None),
            "choices": field_schema.get("choices", None),
            "description": descr
        }

        # If the field is 'many' enabled and not already a list type, wrap it as a list
        if field_schema.get("many", False) and base_type != "list":
            opts[field_name]["type"] = "list"
            opts[field_name]["elements"] = base_type

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
        "api_host":
            {
                "type": "str",
                "required": True,
                "description": "The hostname or IP address of the pfSense device."
            },
        "api_port":
            {
                "type": "int",
                "default": 443,
                "description": "The port number of the pfSense API."
            },
        "api_username":
            {
                "type": "str",
                "default": "admin",
                "description": "The username to authenticate with the pfSense API."
            },
        "api_password":
            {
                "type": "str",
                "default": "pfsense",
                "no_log": True,
                "description": "The password to authenticate with the pfSense API."
            },
        "api_key":
            {
                "type": "str",
                "no_log": True,
                "description": "An optional API key for authentication instead of username/password."
            },
        "validate_certs":
            {
                "type": "bool",
                "default": True,
                "description": "Whether to validate SSL certificates when connecting to the API."
            },
    }

    if module_type == "info":
        return {**standard_options, **get_module_options_for_info_module(endpoint_url)}
    elif module_type == "collection":
        return {**standard_options, **get_module_options_for_collection_module(endpoint_url)}
    elif module_type == "resource":
        return {**standard_options, **get_module_options_for_resource_module(endpoint_url)}
    else:
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
            "description": help_text or f"The {field_name.replace('_', ' ')} of the object.",
            "type": schema_type_to_returns_type(field_schema.get("type", "string")),
            "returned": "always",
        }

        # If the field is 'many' enabled and not already a list type, wrap it as a list
        base_returns_type = schema_type_to_returns_type(field_schema.get("type", "string"))
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


def get_example_value_for_field(field_name: str, field_schema: dict):
    """
    Returns a realistic example value for a field based on its schema.

    Args:
        field_name (str): The name of the field.
        field_schema (dict): The schema dict for the field.

    Returns:
        A representative example value for the field.
    """
    is_many = field_schema.get("many", False)

    # Use first available choice for constrained fields
    choices = field_schema.get("choices") or []
    if choices:
        return [choices[0]] if is_many else choices[0]

    # Use the default value if it is meaningful
    default = field_schema.get("default")
    if default is not None and default != "" and default != []:
        return default

    # Fall back to type-based placeholders
    field_type = field_schema.get("type", "string")
    placeholders = {
        "string": "example",
        "integer": 1,
        "float": 1.0,
        "boolean": False,
        "array": [],
    }
    value = placeholders.get(field_type, "example")

    # Wrap in a list for many-enabled fields that aren't already a list type
    if is_many and field_type != "array":
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
    if module_type in ("collection",) or (module_type == "info" and endpoint_schema.get("many")):
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
        if field_schema.get("read_only", False) or field_schema.get("write_only", False):
            continue
        value = get_example_value_for_field(field_name, field_schema)
        if field_schema.get("required", False):
            required_fields[field_name] = value
        else:
            optional_fields[field_name] = value

    examples = []

    if module_type == "resource":
        # Present example with all required fields
        examples.append({
            "name": f"Create {model_name}",
            fqcn: {**connection_params, "state": "present", **required_fields},
        })
        # Absent example showing how to delete the resource
        examples.append({
            "name": f"Delete {model_name}",
            fqcn: {**connection_params, "state": "absent", **required_fields},
        })

    elif module_type == "collection":
        # Show a representative object inside the objects list
        obj = dict(required_fields)
        for k, v in list(optional_fields.items())[:2]:
            obj[k] = v
        examples.append({
            "name": f"Manage all {model_name_plural}",
            fqcn: {**connection_params, "objects": [obj] if obj else [{}]},
        })

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
            examples.append({
                "name": f"Retrieve all {model_name_plural}",
                fqcn: dict(connection_params),
            })
        else:
            examples.append({
                "name": f"Retrieve {model_name}",
                fqcn: {**connection_params, "lookup_params": {}},
            })

    return examples


def generate_module_documentation(endpoint_url: str, module_type: str) -> dict:
    """
    Generates the module documentation string based on the endpoint and module type.

    Args:
        endpoint_url (str): The endpoint URL.
        module_type (str): The module type.

    Returns:
        dict: The module documentation as a dictionary that can be serialized to YAML for the Ansible
        module DOCUMENTATION string.
    """
    return {
        "module": get_module_name(endpoint_url, module_type),
        "description": [get_module_short_description(endpoint_url, module_type)],
        "short_description": get_module_short_description(endpoint_url, module_type),
        "options": get_module_options(endpoint_url, module_type),
        "author": [
            "Jared Hendrickson (@jaredhendrickson13)"
        ]
    }

def schema_to_dict_file(schema_json: str) -> dict:
    """
    Converts the REST API's native schema from a JSON string intto a Python dictionary
    and embeds it into module_utils/schema.py as variable to be consumed by modules.

    Args:
        schema_json (str): The native schema as a JSON formatted string

    Returns:
        dict: The native schema as a Python dictionary
    """
    try:
        data_dict = json.loads(schema_json)
        formatted_dict = repr(data_dict)

        # 3. Write to the target Python file
        with open("plugins/module_utils/schema_dict.py", 'w+') as f:
            f.write(f'# Generated file - do not edit manually\n')
            f.write(f'SCHEMA_DICT = {formatted_dict}\n')
    except json.JSONDecodeError as e:
        print(f"Invalid JSON string provided: {e}")
    except IOError as e:
        print(f"File writing error: {e}")



if __name__ == "__main__":
    # Convert the schema file to a dict
    with open(args.schema, "r", encoding="utf-8") as schema_json_file:
        schema_to_dict_file(schema_json_file.read())

    # Load the generator configuration file
    generator_config = {}
    generator_config_path = Path(__file__).parent / "generator.yml"
    if generator_config_path.exists():
        with generator_config_path.open("r", encoding="utf-8") as config_file:
            generator_config = yaml.safe_load(config_file) or {}

    exclude_modules = generator_config.get("exclude_modules") or []

    # Iterate over all endpoints in the schema and determine their module types
    for endpoint in native_schema.full_schema.get("endpoints").keys():
        mod_types = get_module_types(endpoint)
        for mod_type in mod_types:
            doc = generate_module_documentation(endpoint, mod_type)
            module_name = doc.get("module")

            # Skip modules that are excluded in the generator config
            if module_name in exclude_modules:
                print(f"Skipping module: {module_name} (excluded in generator.yml)")
                continue

            print(f"Generating module: {module_name}... ", end="")

            # Load the Jinja2 template
            template_loader = jinja2.FileSystemLoader(searchpath=Path(__file__).parent / "templates")
            template_env = jinja2.Environment(loader=template_loader)
            template_env.filters['repr'] = repr
            template = template_env.get_template("module.py.j2")

            # Render the template with the module details
            rendered_module = template.render(
                module_args=doc.get("options", {}),
                module_type=mod_type,
                endpoint_schema=native_schema.get_endpoint_schema(endpoint),
                documentation=yaml.dump(doc, sort_keys=False, indent=2),
                returns=yaml.dump(
                    generate_module_returns(endpoint, mod_type),
                    sort_keys=False,
                    indent=2,
                ),
                examples=yaml.dump(
                    generate_module_examples(endpoint, mod_type),
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                ),
            )

            # Write the rendered module to a .py file
            output_path = Path(__file__).parent.parent / "plugins" / "modules" / f"{module_name}.py"
            with output_path.open("w", encoding="utf-8") as output_file:
                output_file.write(rendered_module)
            print("done.")
