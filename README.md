# pfREST Ansible Collection for pfSense

[![Quality](https://github.com/pfrest/ansible-collection-pfsense/actions/workflows/quality.yml/badge.svg)](https://github.com/pfrest/ansible-collection-pfsense/actions/workflows/quality.yml)
[![Release](https://github.com/pfrest/ansible-collection-pfsense/actions/workflows/release.yml/badge.svg)](https://github.com/pfrest/ansible-collection-pfsense/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An Ansible collection for managing [pfSense](https://www.pfsense.org/) firewalls through the unofficial
[pfSense REST API](https://github.com/pfrest/pfSense-pkg-RESTAPI) package. This collection provides over
400 fully documented, idempotent modules covering firewall rules, NAT, VPN, services, system configuration,
and more.

## Key Features

- **Schema-driven development**: Every module is auto-generated from the REST API's native schema. As the
  API evolves, a single re-generation keeps the entire collection in sync. No handwritten boilerplate to
  maintain, no modules falling out of date.
- **Idempotent by design**: Resource modules compare the desired state against the current API state before
  making changes. Runs are safe to repeat; Ansible only applies what is actually different.
- **Comprehensive coverage**: Modules are organized by category and include info modules for read-only
  queries, resource modules for managing single resources, collection modules for managing entire sets of resources as a
  whole, singleton modules for one-off settings, and action modules for operational tasks.

## Installation

Install from [Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/pfrest/pfsense/):

```bash
ansible-galaxy collection install pfrest.pfsense
```

To install a specific version:

```bash
ansible-galaxy collection install pfrest.pfsense:==0.0.0
```

Or add it to your `requirements.yml` file:

```yaml
collections:
  - name: pfrest.pfsense
    version: ">=0.0.0"
```

Then install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Connection Options

All modules share a common set of connection parameters:

| Parameter        | Type | Default      | Description                                |
|------------------|------|--------------|--------------------------------------------|
| `api_host`       | str  | *(required)* | Hostname or IP of the pfSense device       |
| `api_port`       | int  | `443`        | API port number                            |
| `api_protocol`   | str  | `https`      | Protocol (`http` or `https`)               |
| `api_username`   | str  | `admin`      | Username for authentication                |
| `api_password`   | str  | `pfsense`    | Password for authentication                |
| `api_key`        | str  | —            | API key (alternative to username/password) |
| `validate_certs` | bool | `true`       | Whether to validate SSL certificates       |

## Contributing

Contributions are welcome! Please refer to the [contributing guidelines](docs/CONTRIBUTING.md) for details.

## License

This project is licensed under the [MIT License](LICENSE).
