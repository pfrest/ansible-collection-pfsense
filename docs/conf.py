# Sphinx configuration for pfrest.pfsense collection docs
# Created with antsibull-docs 2.24.0

project = "pfREST Ansible Documentation"
copyright = "2026, Jared Hendrickson"
author = "Jared Hendrickson"

title = "pfREST Ansible Documentation"
html_short_title = "pfREST Ansible Documentation"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.intersphinx", "sphinx_antsibull_ext"]

pygments_style = "ansible"

highlight_language = "YAML+Jinja"

html_theme = "sphinx_ansible_theme"
html_show_sphinx = False
html_show_sourcelink = False

display_version = False

html_use_smartypants = True
html_use_modindex = False
html_use_index = False
html_copy_source = False

# See https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", (None,)),
    "ansible_devel": ("https://docs.ansible.com/projects/ansible/devel/", (None,)),
}

default_role = "any"

suppress_warnings = ["ref.any"]

nitpicky = False

smartquotes = False


