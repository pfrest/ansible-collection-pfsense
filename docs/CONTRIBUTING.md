# Contributing to pfREST Ansible Collection

Thank you for your interest in contributing! This guide covers everything you need to know about the project's
architecture, development workflow, and how to submit changes.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Schema-Driven Module Generation](#schema-driven-module-generation)
- [Customizing Modules](#customizing-modules)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)

## Architecture Overview

This collection is **schema-driven**. The [pfSense REST API](https://github.com/pfrest/pfSense-pkg-RESTAPI)
publishes a native schema (`native.json`) that describes every endpoint, model, field, type, and constraint.
A code generator (`tools/module_generator.py`) reads this schema and produces fully documented Ansible modules
automatically via Jinja2 templates.

This means:

- **Modules are not written by hand.** They are generated from the schema and the templates in `tools/templates/`.
- **When the API changes, modules stay in sync.** A new schema produces updated modules with zero manual effort.
- **Contributions to module behavior belong in the shared base classes**, not in individual module files.

The runtime module logic lives in `plugins/module_utils/`:

| File                 | Purpose                                                                                          |
|----------------------|--------------------------------------------------------------------------------------------------|
| `base.py`            | `BaseModule` — shared logic for all module types (resource, collection, singleton, action, info) |
| `rest.py`            | `RestClient` — HTTP client for the pfSense REST API                                              |
| `schema.py`          | `NativeSchema` — schema lookup utilities used at runtime for field validation and type coercion  |
| `embedded_schema.py` | The full API schema embedded as a Python dict (auto-generated, do not edit)                      |

## Development Setup

### Prerequisites

- Python 3.12+
- Docker (for Molecule integration tests)
- Git

### Getting started

```bash
git clone https://github.com/pfrest/ansible-collection-pfsense.git
cd ansible-collection-pfsense

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all development dependencies
pip install -r requirements-dev.txt

# Install the collection into Ansible's search path
ansible-galaxy collection install .
```

## Project Structure

```
├── galaxy.yml                      # Collection metadata and version
├── generator.yml                   # Generator configuration (exclusion lists)
├── plugins/
│   ├── modules/                    # Auto-generated Ansible modules (do not edit directly)
│   └── module_utils/
│       ├── base.py                 # Shared BaseModule logic
│       ├── rest.py                 # REST API HTTP client
│       ├── schema.py               # Schema lookup utilities
│       └── embedded_schema.py      # Auto-generated schema dict (do not edit directly)
├── tools/
│   ├── module_generator.py         # Module code generator
│   ├── build_docs.sh               # Documentation build script
│   └── templates/                  # Jinja2 templates for module generation
│       ├── module.py.j2            # Main module template
│       ├── module_args.j2          # Argument spec partial
│       └── embedded_schema.py.j2   # Embedded schema template
├── tests/
│   └── unit/                       # Pytest unit tests for module_utils
├── extensions/
│   └── molecule/                   # Molecule integration test scenarios
├── docs/                           # Sphinx documentation source
└── .github/
    └── workflows/                  # CI/CD workflows
        ├── quality.yml             # PR quality checks (lint, test, molecule, docs)
        ├── generate.yml            # Auto-generate modules on upstream API release
        └── release.yml             # Release-please, Galaxy publish, docs deploy
```

## Schema-Driven Module Generation

### How it works

1. The REST API publishes a `native.json` schema describing every endpoint and model.
2. `tools/module_generator.py` reads this schema and generates one `.py` file per module in `plugins/modules/`.
3. The schema is also embedded as a Python dict in `plugins/module_utils/embedded_schema.py` so modules can
   perform field validation at runtime.
4. Jinja2 templates in `tools/templates/` control the structure of the generated code.

### Running the generator manually

```bash
python3 tools/module_generator.py native.json
```

This regenerates all modules and the embedded schema. The generator determines the module type for each
endpoint automatically:

| Module Type    | Description                                             | Example                      |
|----------------|---------------------------------------------------------|------------------------------|
| **resource**   | CRUD operations on individual items within a collection | `firewall_alias`             |
| **collection** | Manage an entire group of resources as a whole          | `firewall_aliases`           |
| **singleton**  | Manage a single configuration object                    | `firewall_advanced_settings` |
| **action**     | Trigger an operational action (non-idempotent)          | `diagnostics_reboot`         |
| **info**       | Read-only query for one or many resources               | `firewall_alias_info`        |

### Automated generation

The `generate.yml` GitHub Actions workflow is triggered automatically when a new version of
[pfSense-pkg-RESTAPI](https://github.com/pfrest/pfSense-pkg-RESTAPI) is released. It downloads the latest
schema, runs the generator, and opens a pull request with the changes.

### What NOT to edit directly

The following files are auto-generated and will be **overwritten** by the generator:

- `plugins/modules/*.py` — All module files
- `plugins/module_utils/embedded_schema.py` — The embedded schema dict

If you need to change module behavior, see [Customizing Modules](#customizing-modules) below.

## Customizing Modules

### Modifying shared behavior

Most module logic lives in `plugins/module_utils/base.py`. Changes here affect **all** modules. This is the
right place to fix bugs or add features related to:

- How resources are created, updated, or deleted
- How idempotency checks work (desired vs. current state comparison)
- How API responses are parsed and returned to Ansible
- Authentication and connection handling (`rest.py`)
- Schema validation and type coercion (`schema.py`)

### Modifying the generated code structure

If you need to change the structure of generated modules (e.g. adding a new field to `DOCUMENTATION`,
changing how argument specs are built), edit the Jinja2 templates in `tools/templates/` and re-run
the generator.

### Excluding modules from generation

If a specific module requires custom logic that cannot live in the shared base classes or templates, you can
**exclude it from auto-generation** to prevent your changes from being overwritten.

Add the module name to the `exclude_modules` list in `generator.yml`:

```yaml
exclude_modules:
  - firewall_alias
  - firewall_alias_info
```

Once excluded, the generator will skip these modules entirely, and you are free to maintain them by hand.

> **Important:** Excluded modules will not receive automatic updates when the API schema changes. You are
> responsible for keeping them in sync with any upstream API changes.

## Testing

### Unit tests

Unit tests cover the shared `module_utils` code (`base.py`, `rest.py`, `schema.py`) and live in
`tests/unit/`. They use pytest with mocked API responses — no real pfSense device is needed.

```bash
# Run all unit tests with coverage
python3 -m pytest tests/unit/ --cov --cov-report=term-missing

# Run with a coverage threshold (CI enforces 100%)
python3 -m pytest tests/unit/ --cov --cov-report=term-missing --cov-fail-under=100
```

### Molecule integration tests

Molecule tests verify that each module can execute successfully against a mock API. They use the Docker
driver with the `ghcr.io/pfrest/mock-api` image.

```bash
# Run all scenarios
molecule test

# Run scenarios matching a pattern
molecule test -s 'pfrest.pfsense.firewall*'

# Run a specific scenario
molecule test -s pfrest.pfsense.firewall_alias
```

Each scenario lives in `extensions/molecule/pfrest.pfsense.<module_name>/` and contains:

- `molecule.yml` — Docker instance configuration with a unique port
- `converge.yml` — Playbook that exercises the module against the mock API

### Writing new tests

**Unit tests:** Add test files to `tests/unit/`. Use the fixtures in `tests/conftest.py` (e.g. `base_module`,
`mock_rest_client`) to avoid coupling to the real embedded schema.

**Molecule tests:** Each module should have its own scenario. If you add a new module, create a matching
scenario directory following the existing naming convention.

## Code Quality

All checks run automatically on pull requests via the Quality workflow. You can run them locally:

### Formatting (Black)

```bash
# Check formatting
black --check .

# Auto-format
black .
```

### Linting (Pylint)

```bash
pylint $(git ls-files '*.py')
```

### Documentation lint

```bash
antsibull-docs lint-collection-docs --plugin-docs .
```

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/) to drive automated
versioning and changelog generation via [release-please](https://github.com/googleapis/release-please).

### Format

```
<type>(<optional scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type       | Version Bump | When to Use                                |
|------------|--------------|--------------------------------------------|
| `feat`     | minor        | A new feature or capability                |
| `fix`      | patch        | A bug fix                                  |
| `docs`     | —            | Documentation-only changes                 |
| `test`     | —            | Adding or updating tests                   |
| `chore`    | —            | Maintenance tasks, CI changes              |
| `refactor` | —            | Code restructuring without behavior change |
| `feat!`    | **major**    | A breaking change (append `!` to any type) |

### Examples

```
feat: add support for WireGuard peer module
fix: correct idempotency check for empty lists
docs: update installation instructions
feat!: remove deprecated api_token parameter
```

## Pull Request Process

1. **Fork the repository** and create a feature branch from `main`.
2. **Make your changes.** Keep commits focused and use conventional commit messages.
3. **Run all checks locally** before pushing:
   ```bash
   black --check .
   pylint $(git ls-files '*.py')
   python3 -m pytest tests/unit/ --cov --cov-fail-under=100
   ```
4. **Open a pull request** against `main`. The Quality workflow will run automatically.
5. **All CI checks must pass** before a PR can be merged:
   - Code style (Black)
   - Linting (Pylint) across Python 3.12, 3.13, and 3.14
   - Unit tests with 100% coverage across Python 3.12, 3.13, and 3.14
   - Molecule integration tests across Python 3.12, 3.13, and 3.14
   - Documentation lint (antsibull-docs)
6. **A maintainer will review and merge** the PR. Once merged, release-please will automatically
   include the change in the next release based on the commit type.

## Questions?

If you have questions or need help, please [open an issue](https://github.com/pfrest/ansible-collection-pfsense/issues).

