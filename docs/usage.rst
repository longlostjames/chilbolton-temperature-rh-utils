Usage Guide
===========

This guide covers common workflows for processing meteorological sensor data using the Chilbolton Temperature RH Utils Software.

Data Processing Workflow
-------------------------

The typical workflow consists of four main steps:

1. Split continuous datalogger files into daily files
2. Convert daily files to CF-compliant NetCDF
3. Apply quality control flags
4. Generate visualization products

Step 1: Split Raw Data Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have continuous CR1000X datalogger files, split them into daily files:

.. code-block:: bash

   python split_cr1000x_data_daily.py -i /path/to/raw/data -o /path/to/daily/output -v

This creates daily files organized in a ``YYYY/YYYYMM/`` directory structure.

Step 2: Process to NetCDF
~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert daily raw data files to CF-compliant NetCDF format:

.. code-block:: bash

   python process_hmp155.py input_20200115.dat \
       -m metadata.json \
       -o /gws/pw/j07/ncas_obs_vol2/cao/2020/

Key arguments:

* Input file: Daily data file from CR1000X datalogger
* ``-m``: Metadata JSON file with instrument configuration
* ``-o``: Output directory for NetCDF files

Step 3: Quality Control Flagging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Automated Purge Detection
^^^^^^^^^^^^^^^^^^^^^^^^^

Automatically detect and flag purge cycles:

.. code-block:: bash

   python flag_purge_times.py \
       -f /gws/pw/j07/ncas_obs_vol2/cao/2020/ncas-temperature-rh-1_cao_20200115_surface-met_v1.0.nc \
       -p /gws/pw/j07/ncas_obs_vol2/cao/2020/ncas-temperature-rh-1_cao_20200114_surface-met_v1.0.nc

The ``-p`` argument provides the previous day's file for continuity in purge detection.

With Correction Files
^^^^^^^^^^^^^^^^^^^^^

Flag specific time intervals as bad data using correction files:

.. code-block:: bash

   python flag_purge_times.py \
       -f data.nc \
       -p previous_day.nc \
       --corr_file_temperature temp_corrections.txt \
       --corr_file_rh rh_corrections.txt

Manual Purge Flagging
^^^^^^^^^^^^^^^^^^^^^^

When automated detection fails, manually flag purges based on previous day:

.. code-block:: bash

   python manual_flag_purge_times.py \
       -f data.nc \
       --prev-file previous_day.nc \
       --shift-seconds 0.0

Or specify exact purge times:

.. code-block:: bash

   python manual_flag_purge_times.py \
       -f data.nc \
       -s "2020-01-15 12:00:00" -e "2020-01-15 12:08:00" \
       -s "2020-01-15 18:00:00" -e "2020-01-15 18:08:00"

Step 4: Visualization
~~~~~~~~~~~~~~~~~~~~~~

Generate Quicklook Plots
^^^^^^^^^^^^^^^^^^^^^^^^

Create daily quicklook plots showing temperature, humidity, and QC flags:

.. code-block:: bash

   python make_quicklooks.py \
       -i /gws/pw/j07/ncas_obs_vol2/cao/ \
       -o /path/to/output/plots/ \
       -y 2020 \
       -d 20200115

Generate Boxplots
^^^^^^^^^^^^^^^^^

Create statistical summaries:

.. code-block:: bash

   # Daily boxplots
   python boxplot_temperature.py -y 2020 -f daily

   # Weekly boxplots
   python boxplot_temperature.py -y 2020 -f weekly

Processing Legacy Format5 Data
-------------------------------

For processing historical data stored in Format5 binary format, use the Format5-specific scripts.

Format5 Overview
~~~~~~~~~~~~~~~~

Format5 is a legacy binary data format used for meteorological data acquisition at the Chilbolton Atmospheric Observatory. Format5 files contain:

* Header with channel metadata and configuration
* Binary data organized by channels (sensors)
* Timestamp information embedded in each data record
* Channel database (`.chdb`) file defining sensor properties

Format5 Workflow
~~~~~~~~~~~~~~~~

The Format5 processing workflow is similar to the standard workflow but uses specialized scripts:

1. Read Format5 header and channel database
2. Convert Format5 data to NetCDF using ``process_hmp155_f5.py``
3. Apply quality control flags (same as standard workflow)
4. Generate visualizations (same as standard workflow)

Convert Format5 to NetCDF
^^^^^^^^^^^^^^^^^^^^^^^^^^

Process Format5 data files (typically named ``chanYYMMDD.000``):

.. code-block:: bash

   python process_hmp155_f5.py /path/to/chan241231.000 \
       -m metadata_f5.json \
       -o /gws/pw/j07/ncas_obs_vol2/cao/2024/

The script automatically:

* Reads the Format5 header using ``read_format5_header.py``
* Parses channel data using ``read_format5_content.py``
* Loads channel calibration from ``f5channelDB.chdb``
* Maps raw sensor values to physical units
* Converts temperature to Kelvin (adds 273.15)

Format5 Channel Database
^^^^^^^^^^^^^^^^^^^^^^^^^

The ``f5channelDB.chdb`` file defines sensor properties for each channel:

.. code-block:: text

   channel oatnew_ch
   title Outside Air Temperature (New)
   location Chilbolton
   rawrange -32768 32767
   rawunits counts
   realrange -40.0 60.0
   realunits deg_C
   interval 60.0

The processing script uses ``rawrange`` and ``realrange`` to convert raw sensor counts to calibrated physical values.

Batch Processing Format5 Data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Process an entire year of Format5 data:

.. code-block:: bash

   ./proc_year_f5.sh -y 2024

This script:

* Locates Format5 files in the legacy data archive
* Processes each day with ``process_hmp155_f5.py``
* Applies QC flags with ``flag_purge_times.py``
* Uses the correct metadata file (``metadata_f5.json``)
* Outputs to the Format5 processing directory

Format5 vs Standard Processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Key differences between Format5 and standard CR1000X processing:

* **Input format**: Binary Format5 vs. ASCII TOA5
* **Metadata**: Channel database (.chdb) vs. JSON metadata only
* **Calibration**: Raw-to-real range mapping vs. direct scaling factors
* **Scripts**: ``process_hmp155_f5.py`` vs. ``process_hmp155.py``
* **Batch script**: ``proc_year_f5.sh`` vs. ``proc_year.sh``

The output NetCDF files and QC flagging procedures are identical for both processing paths.

Batch Processing
----------------

Process an Entire Year
~~~~~~~~~~~~~~~~~~~~~~

Use the provided shell script to process all days in a year:

.. code-block:: bash

   ./proc_year.sh 2020

This script automatically:

* Processes each day sequentially
* Uses the previous day's file for purge detection continuity
* Handles missing files gracefully

With Correction Files
^^^^^^^^^^^^^^^^^^^^^

Include correction files for specific variables:

.. code-block:: bash

   ./proc_year.sh 2020 temp_corrections.txt rh_corrections.txt

Utility Scripts
---------------

Flag Low Temperatures
~~~~~~~~~~~~~~~~~~~~~

Flag temperatures below a threshold as bad data:

.. code-block:: bash

   python flag_low_temperature.py -f data.nc --threshold 245

Calculate Purge Shift
~~~~~~~~~~~~~~~~~~~~~

Determine the time-of-day shift between purge cycles in two files:

.. code-block:: bash

   python find_purge_shift.py file1.nc file2.nc

QC Flag Values
--------------

The software uses the following QC flag scheme:

* **0**: Not used (uninitialized)
* **1**: Good data
* **2**: Bad data (instrument malfunction, known errors)
* **3**: Purge cycle (sensor purge in progress)
* **4**: Recovery period (data potentially affected after purge)

Troubleshooting
---------------

Missing Data
~~~~~~~~~~~~

If processing fails due to missing files, check:

1. File naming conventions match expected format
2. Directory structure follows ``YYYY/YYYYMM/`` pattern
3. Metadata file paths are correct

Incorrect Flag Detection
~~~~~~~~~~~~~~~~~~~~~~~~~

If automated purge detection fails:

1. Use ``manual_flag_purge_times.py`` with previous day's file
2. Adjust ``--shift-seconds`` if purge times drift
3. Manually specify purge intervals with ``-s`` and ``-e``

Plot Issues
~~~~~~~~~~~

If quicklook plots are empty or incorrect:

1. Verify NetCDF file contains data for the specified date
2. Check that QC flags are properly set
3. Ensure output directory is writable
