Chilbolton Temperature RH Utils Software Documentation
=======================================================

This software package processes data from Vaisala HMP155A temperature and humidity sensors at the Chilbolton Atmospheric Observatory (CAO). It supports both modern Campbell Scientific CR1000X datalogger formats and legacy Format5 binary data.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   scripts
   api
   contributing

Overview
--------

The Chilbolton Temperature RH Utils Software provides a suite of tools for:

* Processing raw sensor data to CF-compliant NetCDF files
* Quality control flagging (purge cycles, bad data intervals)
* Data visualization (quicklooks, boxplots)
* Daily file splitting and deduplication
* Legacy Format5 binary data conversion

Key Features
------------

* **Data Processing**: Convert Campbell Scientific CR1000X data or legacy Format5 files to standardized NetCDF format
* **File Splitting**: Split continuous datalogger files into daily files with automatic deduplication
* **Format5 Support**: Full support for legacy binary Format5 data with channel database calibration
* **Quality Control**: Automated detection of purge cycles and manual flagging capabilities
* **Visualization**: Generate daily quicklook plots and statistical summaries
* **Batch Processing**: Shell scripts for processing entire years of data

Data Formats
------------

**Campbell Scientific CR1000X (Current)**

Modern TOA5 ASCII format from CR1000X dataloggers with direct sensor readings.

**Format5 (Legacy)**

Historical binary format used at CAO with:

* Channel-based data organization
* Calibration via channel database files (.chdb)
* Raw-to-physical unit conversion
* Binary file structure with embedded headers

Quick Start
-----------

**Split Raw Data Files**

Split continuous CR1000X files into daily files:

.. code-block:: bash

   split-cr1000x-data-daily -i /path/to/raw_data/ -o daily_files/ -v

**Standard CR1000X Processing**

Process a single day of data:

.. code-block:: bash

   process-hmp155 input_data.dat -m metadata.json -o output_dir/

**Format5 Processing**

Process legacy Format5 data:

.. code-block:: bash

   process-hmp155-f5 chan241231.000 -m metadata_f5.json -o output_dir/

**Quality Control**

Flag purge cycles in processed NetCDF files:

.. code-block:: bash

   flag-hmp155-purge-times -f data.nc -p previous_day.nc

**Visualization**

Generate quicklook plots:

.. code-block:: bash

   python make_quicklooks.py -i /path/to/data/ -o /path/to/plots/ -y 2020 -d 20200115

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
