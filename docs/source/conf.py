import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "GRID"
author = "Fabio Giordana"
copyright = "2026, Fabio Giordana, Zeynep Kiziltan, Ryo Kuroiwa"
release = "0.0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
typehints_fully_qualified = False

napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_include_init_with_doc = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "didppy": ("https://didppy.readthedocs.io/en/stable/", None),
    "networkx": ("https://networkx.org/documentation/stable/", None),
}
