# Installation Guide

## Package Installation

This package can be installed using pip in several ways:

### 1. Development Installation (Recommended for Contributors)

Install in editable mode so changes to the code are immediately available:

```bash
cd /path/to/chilbolton-temperature-rh-utils
pip install -e .
```

This will:
- Install all required dependencies
- Create command-line entry points
- Allow you to modify the code and see changes immediately

### 2. Install with Optional Dependencies

```bash
# Install with development tools
pip install -e ".[dev]"

# Install with documentation tools
pip install -e ".[docs]"

# Install with all optional dependencies
pip install -e ".[dev,docs]"
```

### 3. Standard Installation

```bash
pip install .
```

### 4. Install Directly from GitHub

You can install directly from GitHub without cloning the repository:

#### Install from Main Branch

```bash
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git
```

#### Install from a Specific Branch

```bash
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@develop
```

#### Install from a Specific Tag or Release

```bash
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@v1.0.0
```

#### Install from a Specific Commit

```bash
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@abc123def
```

#### Install with Optional Dependencies from GitHub

```bash
# With development dependencies
pip install "chilbolton-temperature-rh-utils[dev] @ git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git"

# With documentation dependencies
pip install "chilbolton-temperature-rh-utils[docs] @ git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git"

# With all optional dependencies
pip install "chilbolton-temperature-rh-utils[dev,docs] @ git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git"
```

#### Using SSH Instead of HTTPS

If you have SSH keys configured:

```bash
pip install git+ssh://git@github.com/longlostjames/chilbolton-temperature-rh-utils.git
```

## Building Distribution Packages

To build distribution packages (wheel and source):

```bash
# Install build tools
pip install build

# Build the package
python -m build

# This creates:
# - dist/chilbolton_temperature_rh_utils-1.0.0-py3-none-any.whl
# - dist/chilbolton-temperature-rh-utils-1.0.0.tar.gz
```

## Uploading to PyPI (Maintainers Only)

```bash
# Install twine
pip install twine

# Upload to Test PyPI first
python -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ chilbolton-temperature-rh-utils

# Upload to PyPI
python -m twine upload dist/*
```

## Verification

After installation, verify the package is installed correctly:

```bash
# Check package version
pip show chilbolton-temperature-rh-utils

# Test command-line tools
process-hmp155 --help
process-hmp155-f5 --help
flag-hmp155-purge-times --help

# Test Python imports
python -c "import chilbolton_temperature_rh_utils; print(chilbolton_temperature_rh_utils.__version__)"
```

## Uninstallation

```bash
pip uninstall chilbolton-temperature-rh-utils
```

## Conda Environment

For a clean environment:

```bash
# Create new conda environment
conda create -n cao_utils python=3.11
conda activate cao_utils

# Install package
cd /path/to/chilbolton-temperature-rh-utils
pip install -e .
```

## Dependencies

The package will automatically install:

- numpy>=1.24.0
- polars>=0.19.0
- pandas>=2.0.0
- xarray>=2023.1.0
- netCDF4>=1.6.0
- matplotlib>=3.7.0
- cftime>=1.6.0
- ncas-amof-netcdf-template>=2.0.0

## Troubleshooting

### Import Errors

If you get import errors after installation:

```bash
# Reinstall in editable mode
pip install -e . --force-reinstall --no-deps
```

### Command Not Found

If command-line tools are not found:

```bash
# Check if scripts are in PATH
which process-hmp155

# If not found, add to PATH or use full path
python -m chilbolton_temperature_rh_utils.process_hmp155 --help

# Other commands
which flag-hmp155-purge-times
```

### Dependency Conflicts

If you have dependency conflicts:

```bash
# Create a fresh virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```
