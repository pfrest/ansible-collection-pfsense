pfREST Ansible Documentation
============================

An Ansible collection for managing `pfSense <https://www.pfsense.org/>`_ firewalls through the unofficial
`pfSense REST API <https://github.com/pfrest/pfSense-pkg-RESTAPI>`_ package. This collection provides over
400 fully documented, idempotent modules covering firewall rules, NAT, VPN, services, system configuration,
and more.

Key Features
------------

- **Schema-driven development** — Every module is auto-generated from the REST API's native schema. As the
  API evolves, a single re-generation keeps the entire collection in sync.
- **Idempotent by design** — Resource modules compare the desired state against the current API state before
  making changes. Runs are safe to repeat; Ansible only applies what is actually different.
- **Comprehensive coverage** — Modules are organized by category and include info modules for read-only
  queries, resource modules for managing single resources, collection modules for managing entire sets of
  resources, singleton modules for one-off settings, and action modules for operational tasks.

Installation
------------

Install from `Ansible Galaxy <https://galaxy.ansible.com/ui/repo/published/pfrest/pfsense/>`_:

.. code-block:: bash

   ansible-galaxy collection install pfrest.pfsense

To install a specific version:

.. code-block:: bash

   ansible-galaxy collection install pfrest.pfsense:==0.0.0

Or add it to your ``requirements.yml`` file:

.. code-block:: yaml

   collections:
     - name: pfrest.pfsense
       version: ">=0.0.0"

Then install with:

.. code-block:: bash

   ansible-galaxy collection install -r requirements.yml

Connection Options
------------------

All modules share a common set of connection parameters:

.. list-table::
   :header-rows: 1
   :widths: 20 10 15 55

   * - Parameter
     - Type
     - Default
     - Description
   * - ``api_host``
     - str
     - *(required)*
     - Hostname or IP of the pfSense device
   * - ``api_port``
     - int
     - ``443``
     - API port number
   * - ``api_protocol``
     - str
     - ``https``
     - Protocol (``http`` or ``https``)
   * - ``api_username``
     - str
     - ``admin``
     - Username for authentication
   * - ``api_password``
     - str
     - ``pfsense``
     - Password for authentication
   * - ``api_key``
     - str
     - —
     - API key (alternative to username/password)
   * - ``validate_certs``
     - bool
     - ``true``
     - Whether to validate SSL certificates

.. toctree::
   :maxdepth: 2
   :caption: Collections:

   collections/index


.. toctree::
   :maxdepth: 1
   :caption: Plugin indexes:
   :glob:

   collections/index_*
