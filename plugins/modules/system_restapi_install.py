#!/usr/bin/python
"""An Ansible module for installing pfSense-pkg-RESTAPI on a pfSense system."""

# pylint: disable=duplicate-code

import time

from ansible.module_utils.basic import AnsibleModule

try:
    from pfsense_vshell import PFClient, PFError

    HAS_VSHELL = True
except ImportError:
    HAS_VSHELL = False

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

DOCUMENTATION = r"""
module: system_restapi_install
description:
  - Ensure the pfSense REST API package (pfSense-pkg-RESTAPI) is installed on
    a pfSense system.
short_description: Install the pfSense REST API package on a pfSense system.
requirements:
  - L(pfsense_vshell,https://pypi.org/project/pfsense-vshell/)
  - L(requests,https://pypi.org/project/requests/)
notes:
  - The target pfSense system must have its web GUI accessible to the Ansible controller
    for the virtual shell connection to work.
  - The C(api_key) authentication option is intentionally not supported because
    API keys are not available until after the REST API package is installed.
  - The provided C(api_username) must be a user with access to the Diagnostics 
    > Command Prompt page in the pfSense web GUI for this module to work.
  - This module only ensures the REST API package is installed. It does not
    manage which version is installed. To update or roll back to a specific
    REST API version, use the M(pfrest.pfsense.system_restapi_version) module
    instead.
options:
  api_host:
    type: str
    required: true
    description: The hostname or IP address of the pfSense device.
  api_port:
    type: int
    default: 443
    description: The TCP port of the pfSense web GUI.
  api_protocol:
    type: str
    default: https
    choices:
      - http
      - https
    description: The protocol to use when connecting to the pfSense web GUI.
  api_username:
    type: str
    default: admin
    description: The pfSense web GUI username to authenticate with.
  api_password:
    type: str
    default: pfsense
    description: The pfSense web GUI password to authenticate with.
  validate_certs:
    type: bool
    default: true
    description: Whether to validate SSL certificates when connecting.
  url:
    type: str
    required: true
    description:
      - The full URL to the C(.pkg) file to install.
      - This is typically a URL to a release asset from the pfSense-pkg-RESTAPI
        GitHub repository, for example
        C(https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg).
  verify_timeout:
    type: int
    default: 120
    description:
      - The maximum number of seconds to wait for the REST API to become
        available after installation before declaring failure.
  verify_interval:
    type: int
    default: 10
    description:
      - The number of seconds to wait between verification attempts while
        waiting for the REST API to become available.
author:
  - Jared Hendrickson (@jaredhendrickson13)
"""

EXAMPLES = r"""
- name: Install pfSense REST API package
  pfrest.pfsense.system_restapi_install:
    api_host: pfsense.example.com
    api_username: admin
    api_password: pfsense
    url: https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg

- name: Install REST API package over HTTP with custom timeout
  pfrest.pfsense.system_restapi_install:
    api_host: 192.168.1.1
    api_port: 80
    api_protocol: http
    api_username: admin
    api_password: pfsense
    validate_certs: false
    url: https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg
    verify_timeout: 180
    verify_interval: 15
"""

RETURN = r"""
changed:
  description: Whether the REST API package was installed.
  type: bool
  returned: always
msg:
  description: A human-readable status message.
  type: str
  returned: always
version:
  description: The REST API version string reported after installation.
  type: str
  returned: on success
"""


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _verify_api(
    scheme: str, host: str, port: int, validate_certs: bool, timeout: int, interval: int
) -> str:
    """Poll the REST API native schema endpoint until it responds with the version.

    Args:
        scheme: HTTP scheme (http or https).
        host: The pfSense hostname or IP.
        port: The TCP port the API listens on.
        validate_certs: Whether to verify TLS certificates.
        timeout: Maximum total seconds to wait.
        interval: Seconds between retries.

    Returns:
        The version string from the API schema.

    Raises:
        RuntimeError: If the API does not become available within the timeout.
    """
    url = f"{scheme}://{host}:{port}/api/v2/schema/native"
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            resp = requests.get(url, verify=validate_certs, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version")
                if version:
                    return version
                last_error = "API responded but 'version' key is missing from schema."
            else:
                last_error = f"API returned HTTP {resp.status_code}."
        except requests.RequestException as exc:
            last_error = str(exc)

        time.sleep(interval)

    raise RuntimeError(
        f"REST API did not become available within {timeout}s. Last error: {last_error}"
    )


def run_module():
    """Run the system_restapi_install module."""
    # pylint: disable=too-many-locals
    module_args = {
        "api_host": {
            "type": "str",
            "required": True,
        },
        "api_port": {
            "type": "int",
            "required": False,
            "default": 443,
        },
        "api_protocol": {
            "type": "str",
            "required": False,
            "default": "https",
            "choices": ["http", "https"],
        },
        "api_username": {
            "type": "str",
            "required": False,
            "default": "admin",
        },
        "api_password": {
            "type": "str",
            "required": False,
            "no_log": True,
            "default": "pfsense",
        },
        "validate_certs": {
            "type": "bool",
            "required": False,
            "default": True,
        },
        "url": {
            "type": "str",
            "required": True,
        },
        "verify_timeout": {
            "type": "int",
            "required": False,
            "default": 120,
        },
        "verify_interval": {
            "type": "int",
            "required": False,
            "default": 10,
        },
    }

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    # Validate dependencies
    if not HAS_VSHELL:
        module.fail_json(
            msg="Missing required Python library: pfsense_vshell. "
            "Install it with: pip install pfsense-vshell"
        )
    if not HAS_REQUESTS:
        module.fail_json(
            msg="Missing required Python library: requests. "
            "Install it with: pip install requests"
        )

    host = module.params["api_host"]
    port = module.params["api_port"]
    scheme = module.params["api_protocol"]
    username = module.params["api_username"]
    password = module.params["api_password"]
    validate_certs = module.params["validate_certs"]
    pkg_url = module.params["url"]
    verify_timeout = module.params["verify_timeout"]
    verify_interval = module.params["verify_interval"]

    # Check if the REST API is already installed by probing the schema endpoint
    schema_url = f"{scheme}://{host}:{port}/api/v2/schema/native"
    api_already_installed = False
    existing_version = None
    try:
        probe = requests.get(schema_url, verify=validate_certs, timeout=15)
        if probe.status_code == 200:
            probe_data = probe.json()
            existing_version = probe_data.get("version")
            if existing_version:
                api_already_installed = True
    except requests.RequestException:
        pass

    # If the API is already present, nothing to do
    if api_already_installed:
        module.exit_json(
            changed=False,
            msg="REST API package is already installed.",
            version=existing_version,
        )

    # In check mode, report what would happen without doing anything
    if module.check_mode:
        module.exit_json(
            changed=True,
            msg=f"Would install REST API package from {pkg_url}.",
        )

    # Build the shell command to fetch and install the package
    install_cmd = f"pkg -C /dev/null add {pkg_url}"

    # Create the vshell client and execute the install command
    client = PFClient(
        host=host,
        username=username,
        password=password,
        port=port,
        scheme=scheme,
        timeout=120,
        verify=validate_certs,
    )

    try:
        client.run_command(install_cmd)
    except (PFError, Exception):  # pylint: disable=broad-except
        # The installation restarts the web GUI which is expected to
        # interrupt the vshell HTTP connection.  We swallow the error
        # and fall through to the verification step.
        pass

    # Wait for the REST API to come online and verify installation
    try:
        version = _verify_api(
            scheme=scheme,
            host=host,
            port=port,
            validate_certs=validate_certs,
            timeout=verify_timeout,
            interval=verify_interval,
        )
    except RuntimeError as exc:
        module.fail_json(
            changed=True,
            msg=f"Package install command was sent but the REST API failed "
            f"verification: {exc}",
        )

    module.exit_json(
        changed=True,
        msg="Successfully installed the pfSense REST API package.",
        version=version,
    )


if __name__ == "__main__":
    run_module()
