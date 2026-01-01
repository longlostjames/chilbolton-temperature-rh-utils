"""
Chilbolton Temperature RH Utils
================================

Processing utilities for Chilbolton temperature and relative humidity sensor data.

This package provides tools for:
- Processing Campbell Scientific CR1000X data to CF-compliant NetCDF
- Processing legacy Format5 binary data to NetCDF
- Quality control flagging (purge cycles, bad data intervals)
- Data visualization (quicklooks, boxplots)
- Batch processing workflows
"""

__version__ = "1.0.0"
__author__ = "Chris Walden"

# Import main processing functions
from .process_hmp155 import main as process_hmp155_main
from .process_hmp155_f5 import main as process_hmp155_f5_main
from .process_hmp155_stfc import main as process_hmp155_stfc_main

# Import QC functions
from .flag_purge_times import main as flag_purge_times_main
from .manual_flag_purge_times import main as manual_flag_purge_times_main
from .flag_low_temperature import main as flag_low_temperature_main

# Import utility functions
from .read_format5_header import read_format5_header
from .read_format5_content import read_format5_content
from .split_cr1000x_data_daily import main as split_cr1000x_data_daily_main
from .make_quicklooks import main as make_quicklooks_main
from .read_format5_chdb import read_format5_chdb

__all__ = [
    "__version__",
    "__author__",
    "process_hmp155_main",
    "process_hmp155_f5_main",
    "process_hmp155_stfc_main",
    "flag_purge_times_main",
    "manual_flag_purge_times_main",
    "flag_low_temperature_main",
    "read_format5_header",
    "read_format5_content",
    "read_format5_chdb",
]
