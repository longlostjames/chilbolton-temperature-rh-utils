# chilbolton-temperature-rh-utils

NCAS Temperature RH-1 Software - Processing utilities for Chilbolton temperature and relative humidity sensor data.

## Features

- **Data Processing**: Convert Campbell Scientific CR1000X data or legacy Format5 files to CF-compliant NetCDF
- **Format5 Support**: Full support for legacy binary Format5 data with channel database calibration
- **Quality Control**: Automated detection of purge cycles and manual flagging capabilities
- **Visualization**: Generate daily quicklook plots and statistical summaries
- **Batch Processing**: Shell scripts for processing entire years of data

## Installation

### From PyPI (when published)

```bash
pip install chilbolton-temperature-rh-utils
```

### From GitHub

Install directly from GitHub without cloning:

```bash
# Install the latest version from main branch
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git

# Install a specific branch
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@branch-name

# Install a specific tag/release
pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@v1.0.0

# Install with optional dependencies
pip install "chilbolton-temperature-rh-utils[dev,docs] @ git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git"
```

### From Source

```bash
# Clone the repository
git clone https://github.com/longlostjames/chilbolton-temperature-rh-utils.git
cd chilbolton-temperature-rh-utils

# Install in development mode
pip install -e .

# Or install with optional dependencies
pip install -e ".[dev,docs]"
```

### Requirements

- Python 3.11 or later
- NumPy
- Polars
- Pandas
- xarray
- netCDF4
- matplotlib
- cftime
- ncas-amof-netcdf-template

## Quick Start

### Command Line Tools

After installation, the following command-line tools are available:

```bash
# Process CR1000X data
process-hmp155 input_data.dat -m metadata.json -o output_dir/

# Process Format5 data
process-hmp155-f5 chan241231.000 -m metadata_f5.json -o output_dir/

# Split CR1000X files into daily files
split-cr1000x-data-daily -i /path/to/raw_data/ -o daily_files/ -v

# Flag purge cycles
flag-hmp155-purge-times -f data.nc -p previous_day.nc

# Manual purge flagging
flag-hmp155-purge-times-manual -f data.nc --prev-file yesterday.nc

# Flag low temperatures
flag-hmp155-low-temperature -f data.nc --threshold 245

# Extract purge cycle indices to CSV for manual review
extract-hmp155-purge-indices -i /path/to/netcdf/ -o purge_indices_2015.csv -y 2015

# Apply manually corrected purge indices from CSV
apply-hmp155-purge-indices -c purge_indices_2015.csv -i /path/to/netcdf/ -y 2015

# Generate quicklook plots
make-hmp155-quicklooks -y 2025 -i /path/to/netcdf/ -o /path/to/plots/
```

### Python API

```python
from chilbolton_temperature_rh_utils import (
    read_format5_header,
    read_format5_content,
    read_format5_chdb,
)

# Read Format5 file
header = read_format5_header('chan241231.000')
df = read_format5_content('chan241231.000', header)

# Load channel database
chdb = read_format5_chdb('f5channelDB.chdb')
```

## Data Formats

### Campbell Scientific CR1000X (Current)

Modern TOA5 ASCII format from CR1000X dataloggers with direct sensor readings.

### Format5 (Legacy)

Historical binary format used at CAO with:
- Channel-based data organization
- Calibration via channel database files (.chdb)
- Raw-to-physical unit conversion
- Binary file structure with embedded headers

## Documentation

Full documentation is available at: https://chilbolton-temperature-rh-utils.readthedocs.io

Or build locally:

```bash
cd docs
make html
```

## Batch Processing

Process an entire year of data:

```bash
# Standard CR1000X data
./proc_year.sh 2020

# Format5 data
./proc_year_f5.sh -y 2024

# With correction files
./proc_year.sh 2020 temp_corrections.txt rh_corrections.txt
```

## Manual Purge Cycle Correction Workflow

For cases where automatic purge detection needs manual refinement:

1. **Extract purge indices from processed files:**
   ```bash
   extract-hmp155-purge-indices \
       -i /path/to/netcdf/ \
       -o purge_indices_2015.csv \
       -y 2015
   ```

2. **Review and edit the CSV file:**
   The CSV contains columns: `date`, `purge1_start_idx`, `purge1_end_idx`, `recovery1_start_idx`, `recovery1_end_idx`, `purge2_start_idx`, `purge2_end_idx`, `recovery2_start_idx`, `recovery2_end_idx`.
   
   Edit the indices as needed for each day. Indices refer to array positions in the time coordinate.

3. **Apply corrected indices back to NetCDF files:**
   ```bash
   apply-hmp155-purge-indices \
       -c purge_indices_2015.csv \
       -i /path/to/netcdf/ \
       -y 2015
   ```

This workflow allows you to:
- Extract detected purge cycles to a spreadsheet format
- Manually review and correct timing issues
- Re-apply the corrected flags to the data files

## Development

To contribute to this project:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests (when available)
pytest

# Format code
black chilbolton_temperature_rh_utils/

# Type checking
mypy chilbolton_temperature_rh_utils/
```

## License

MIT License

## Contact

For issues and questions, please use the [GitHub issue tracker](https://github.com/longlostjames/chilbolton-temperature-rh-utils/issues).
