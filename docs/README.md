# Chilbolton Temperature RH Utils Software Documentation

This directory contains the Sphinx documentation for the Chilbolton Temperature RH Utils Software.

## Building the Documentation

### Prerequisites

Install Sphinx and the ReadTheDocs theme:

```bash
conda install -c conda-forge sphinx sphinx_rtd_theme
```

Or with pip:

```bash
pip install sphinx sphinx_rtd_theme
```

### Building HTML Documentation

From this directory, run:

```bash
make html
```

The generated HTML documentation will be in `_build/html/`. Open `_build/html/index.html` in a web browser to view.

### Other Build Formats

Build PDF documentation (requires LaTeX):

```bash
make latexpdf
```

Build EPUB documentation:

```bash
make epub
```

Clean build files:

```bash
make clean
```

## Documentation Structure

- `index.rst` - Main documentation page with table of contents
- `installation.rst` - Installation instructions
- `usage.rst` - Usage guide and workflows
- `scripts.rst` - Detailed script reference
- `api.rst` - API documentation
- `contributing.rst` - Contributing guidelines
- `conf.py` - Sphinx configuration

## ReadTheDocs Integration

This documentation is configured for hosting on ReadTheDocs. To set up:

1. Create a `.readthedocs.yaml` file in the repository root
2. Configure the build settings
3. Link the GitHub repository to ReadTheDocs
4. Documentation will automatically build on each commit

Example `.readthedocs.yaml`:

```yaml
version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.11"

sphinx:
  configuration: docs/conf.py

python:
  install:
    - requirements: docs/requirements.txt
```

Create `docs/requirements.txt`:

```
sphinx>=4.0
sphinx_rtd_theme>=1.0
```

## Updating Documentation

When making changes to the code:

1. Update relevant RST files in this directory
2. Rebuild the documentation with `make html`
3. Review changes in `_build/html/`
4. Commit the updated RST files (not the _build directory)

## Contributing

See `contributing.rst` for guidelines on contributing to the documentation.
