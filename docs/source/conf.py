# Configuration file for the Sphinx documentation builder.
import os
# -- Project information

project = u'SimplyFire'
copyright = u'2023, Andrew Rosko'
author = u'Megumi Mori, Andrew Rosko'

release = '0.5'
version = '0.5.1'

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.inheritance_diagram',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']
master_doc = 'index'
exclude_patterns = ['_build']
pygments_style = 'sphinx'
# -- Options for HTML output
# on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
#
# if not on_rtd:  # only import and set the theme if we're building docs locally
import sphinx_rtd_theme
html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_static_path = ['_static']
html_logo = '_static/img/logo_rtd.png'
html_theme_options = {
    'logo_only': True,
    'display_version': True,
}

# -- Options for EPUB output
epub_show_urls = 'footnote'
