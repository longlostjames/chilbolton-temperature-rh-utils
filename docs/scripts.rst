Scripts Reference
=================

This section provides detailed documentation for each script in the Chilbolton Temperature RH Utils Software package.

Data Processing Scripts
-----------------------

process_hmp155.py
~~~~~~~~~~~~~~~~~

Convert raw Campbell Scientific CR1000X data files to CF-compliant NetCDF format.

**Command Line Arguments:**

.. code-block:: text

   usage: process_hmp155.py [-h] [-m METADATA] [-o OUTPUT] input_file

   positional arguments:
     input_file            Input CR1000X DAT file

   optional arguments:
     -h, --help            Show help message and exit
     -m METADATA           Metadata JSON file (default: metadata.json)
     -o OUTPUT             Output directory (default: current directory)

**Features:**

* Reads Campbell Scientific TOA5 format files
* Applies variable scaling and offsets from metadata
* Initializes QC flags to 0 (not used)
* Writes CF-compliant NetCDF with proper time encoding
* Handles timezone conversion to UTC

**Example:**

.. code-block:: bash

   python process_hmp155.py CR1000X_Chilbolton_Rxcabinmet1_20200115.dat \
       -m metadata.json \
       -o /gws/pw/j07/ncas_obs_vol2/cao/2020/

process_hmp155_f5.py
~~~~~~~~~~~~~~~~~~~~

Convert legacy Format5 binary data files to CF-compliant NetCDF format.

**Command Line Arguments:**

.. code-block:: text

   usage: process_hmp155_f5.py [-h] [-m METADATA] [-o OUTPUT] input_file

   positional arguments:
     input_file            Input Format5 file (e.g., chan241231.000)

   optional arguments:
     -h, --help            Show help message and exit
     -m METADATA           Metadata JSON file (default: metadata.json)
     -o OUTPUT             Output directory (default: current directory)

**Features:**

* Reads Format5 binary format files
* Uses ``read_format5_header.py`` to parse file headers
* Uses ``read_format5_content.py`` to extract data records
* Loads sensor calibration from ``f5channelDB.chdb``
* Maps raw counts to physical units using rawrange/realrange
* Converts temperature from Celsius to Kelvin
* Handles year-crossing timestamps correctly
* Writes CF-compliant NetCDF with proper time encoding

**Format5 Processing Steps:**

1. Extract header metadata (channels, sample interval, timestamps)
2. Read channel database for calibration parameters
3. Parse binary data records into Polars DataFrame
4. Apply linear scaling: ``physical = (raw - raw_min) / (raw_max - raw_min) * (real_max - real_min) + real_min``
5. Convert temperature to Kelvin (add 273.15)
6. Create NetCDF file with time variables and data

**Example:**

.. code-block:: bash

   python process_hmp155_f5.py /gws/pw/j07/ncas_obs_vol2/cao/raw_data/legacy/chan241231.000 \
       -m metadata_f5.json \
       -o /gws/pw/j07/ncas_obs_vol2/cao/2024/

read_format5_header.py
~~~~~~~~~~~~~~~~~~~~~~

Extract header information from Format5 binary data files.

**Function:**

.. code-block:: python

   def read_format5_header(path_filename):
       """
       Reads the header information from a format5 data file.
       Returns a dictionary containing header metadata.
       """

**Extracted Information:**

* ``present``: File existence flag
* ``comment_size``: Byte size of comment section
* ``header_size``: Byte size of header section
* ``dataline_size``: Byte size of each data record
* ``descriptor``: File description
* ``database``: Associated database name
* ``sample_interval``: Data sampling interval
* ``chids``: List of channel identifiers
* ``chstat``: Channel status for each channel
* ``num_sensors``: Total number of sensors
* ``start_ts``: First timestamp in file
* ``finish_ts``: Last timestamp in file
* ``data_rows``: Number of data records

**Example:**

.. code-block:: python

   from read_format5_header import read_format5_header
   
   header = read_format5_header('chan241231.000')
   print(f"Channels: {header['chids']}")
   print(f"Start time: {header['start_ts']}")
   print(f"Records: {header['data_rows']}")

read_format5_content.py
~~~~~~~~~~~~~~~~~~~~~~~

Parse Format5 binary data records and create a Polars DataFrame.

**Function:**

.. code-block:: python

   def read_format5_content(path_file, header):
       """
       Reads the content of a format5 data file and stores it in a Polars DataFrame.
       Returns DataFrame with TIMESTAMP and channel columns.
       """

**Processing Steps:**

1. Skip to data section using header offset information
2. Parse each line as comma-separated timestamp + space-separated data
3. Convert first 5 values (month, day, hour, minute, second) to timestamps
4. Extract year from filename (YY format + 2000)
5. Create DataFrame with timestamp and all channel columns
6. Cast timestamp to Datetime format
7. Cast data columns to Float64

**Output Columns:**

* ``TIMESTAMP``: Datetime column in format YYYY-MM-DD HH:MM:SS
* Channel columns: One column per channel from header (e.g., ``oatnew_ch``, ``rhnew_ch``)

**Example:**

.. code-block:: python

   from read_format5_header import read_format5_header
   from read_format5_content import read_format5_content
   
   header = read_format5_header('chan241231.000')
   df = read_format5_content('chan241231.000', header)
   print(df)

read_format5_chdb.py
~~~~~~~~~~~~~~~~~~~~

Load and parse Format5 channel database (.chdb) files.

**Function:**

.. code-block:: python

   def read_format5_chdb(path_file):
       """
       Reads the format5 channel database (.chdb) file.
       Returns a dictionary where each channel is a key with calibration properties.
       """

**Channel Properties:**

* ``title``: Channel description
* ``location``: Sensor location
* ``rawrange``: Raw sensor output range (dict with ``lower``, ``upper``)
* ``rawunits``: Units of raw values (e.g., "counts")
* ``realrange``: Calibrated physical value range (dict with ``lower``, ``upper``)
* ``realunits``: Units of physical values (e.g., "deg_C")
* ``interval``: Sampling interval in seconds

**Database Format:**

.. code-block:: text

   channel oatnew_ch
   title Outside Air Temperature (New)
   location Chilbolton
   rawrange -32768 32767
   rawunits counts
   realrange -40.0 60.0
   realunits deg_C
   interval 60.0

**Example:**

.. code-block:: python

   from read_format5_chdb import read_format5_chdb
   
   chdb = read_format5_chdb('f5channelDB.chdb')
   oat_config = chdb['oatnew_ch']
   print(f"Temperature range: {oat_config['realrange']['lower']} to {oat_config['realrange']['upper']} {oat_config['realunits']}")

split_cr1000x_data_daily.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Split continuous CR1000X datalogger files into daily files organized by year and month.

**Command Line Arguments:**

.. code-block:: text

   usage: split_cr1000x_data_daily.py [-h] -i INPUT_DIR -o OUTPUT_DIR [-v]

   optional arguments:
     -h, --help            Show help message and exit
     -i INPUT_DIR          Input directory containing CR1000X files
     -o OUTPUT_DIR         Output directory for daily files
     -v                    Verbose output

**Features:**

* Processes all CR1000X_Chilbolton_Rxcabinmet1*.dat files in input directory
* Creates YYYY/YYYYMM directory structure
* Shifts midnight records to previous day
* Deduplicates identical files for the same date
* Preserves TOA5 4-line header format
* Quotes timestamp column

**Example:**

.. code-block:: bash

   python split_cr1000x_data_daily.py \
       -i /path/to/continuous/files \
       -o /gws/pw/j07/ncas_obs_vol2/cao/ \
       -v

Quality Control Scripts
-----------------------

flag_purge_times.py
~~~~~~~~~~~~~~~~~~~

Automatically detect and flag purge cycles and recovery periods in NetCDF files.

**Command Line Arguments:**

.. code-block:: text

   usage: flag_purge_times.py [-h] -f FILE [-p PREV_FILE]
                              [--corr_file_temperature CORR_FILE_TEMPERATURE]
                              [--corr_file_rh CORR_FILE_RH]

   optional arguments:
     -h, --help            Show help message and exit
     -f FILE               NetCDF file to process
     -p PREV_FILE          Previous day's NetCDF file for continuity
     --corr_file_temperature CORR_FILE_TEMPERATURE
                           Text file with temperature correction intervals
     --corr_file_rh CORR_FILE_RH
                           Text file with RH correction intervals

**Detection Parameters:**

* Window size: 8 minutes (240 seconds)
* Temperature flat threshold: 0.07 K standard deviation
* RH flat threshold: 0.03 % standard deviation
* RH exclusion: Values ≥ 99.8%
* Recovery period: 6 minutes after purge end

**QC Flag Values:**

* 1: Good data
* 2: Bad data (from correction files)
* 3: Purge cycle
* 4: Recovery period (RH only)

**Example:**

.. code-block:: bash

   python flag_purge_times.py \
       -f ncas-temperature-rh-1_cao_20200115_surface-met_v1.0.nc \
       -p ncas-temperature-rh-1_cao_20200114_surface-met_v1.0.nc \
       --corr_file_temperature temp_bad_intervals.txt

manual_flag_purge_times.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Manually flag purge cycles based on previous day's purge times or explicit intervals.

**Command Line Arguments:**

.. code-block:: text

   usage: manual_flag_purge_times.py [-h] -f FILE [--prev-file PREV_FILE]
                                     [--shift-seconds SHIFT_SECONDS]
                                     [-s START] [-e END]
                                     [--clear-purge-flags]

   optional arguments:
     -h, --help            Show help message and exit
     -f FILE               NetCDF file to process
     --prev-file PREV_FILE Previous day's file to copy purge times from
     --shift-seconds SHIFT_SECONDS
                           Time shift to apply to purge times (default: 0.0)
     -s START              Start time of purge interval (can be repeated)
     -e END                End time of purge interval (can be repeated)
     --clear-purge-flags   Clear existing purge flags before applying new ones

**Features:**

* Copies purge times from previous day's file
* Applies time-of-day matching (ignores date)
* Supports time shift adjustment
* Allows explicit purge interval specification
* Flags both temperature and RH QC flags as 3

**Example:**

.. code-block:: bash

   # Use previous day's purge times
   python manual_flag_purge_times.py \
       -f today.nc \
       --prev-file yesterday.nc \
       --shift-seconds 0.0

   # Specify explicit intervals
   python manual_flag_purge_times.py \
       -f today.nc \
       -s "2020-01-15 12:00:00" -e "2020-01-15 12:08:00" \
       -s "2020-01-15 18:00:00" -e "2020-01-15 18:08:00"

flag_low_temperature.py
~~~~~~~~~~~~~~~~~~~~~~~~

Flag temperature values below a threshold as bad data.

**Command Line Arguments:**

.. code-block:: text

   usage: flag_low_temperature.py [-h] -f FILE [--threshold THRESHOLD]

   optional arguments:
     -h, --help            Show help message and exit
     -f FILE               NetCDF file to process
     --threshold THRESHOLD Temperature threshold in Kelvin (default: 245)

**Features:**

* Flags both air_temperature and relative_humidity QC flags
* Default threshold: 245 K (-28.15 °C)
* Sets QC flag value to 2 (bad data)

**Example:**

.. code-block:: bash

   python flag_low_temperature.py -f data.nc --threshold 240

Visualization Scripts
---------------------

make_quicklooks.py
~~~~~~~~~~~~~~~~~~

Generate daily quicklook plots showing temperature, humidity, and QC flags.

**Command Line Arguments:**

.. code-block:: text

   usage: make_quicklooks.py [-h] -i INPUT_DIR -o OUTPUT_DIR -y YEAR -d DAY

   optional arguments:
     -h, --help            Show help message and exit
     -i INPUT_DIR          Input directory containing NetCDF files
     -o OUTPUT_DIR         Output directory for PNG plots
     -y YEAR               Year (YYYY)
     -d DAY                Day (YYYYMMDD)

**Plot Features:**

* Temperature displayed in degrees Celsius
* Full-day overview plot
* Zoomed plots for each purge period
* Color-coded QC flag visualization:
  
  * Red dots/shading: Purge cycles (flag 3)
  * Blue dots/peachpuff shading: RH recovery (flag 4)
  * Grey shading: Bad data (flag 2)

* No duplicate legend entries
* Overlapping flag intervals combined

**Example:**

.. code-block:: bash

   python make_quicklooks.py \
       -i /gws/pw/j07/ncas_obs_vol2/cao/ \
       -o /path/to/plots/ \
       -y 2020 \
       -d 20200115

boxplot_temperature.py
~~~~~~~~~~~~~~~~~~~~~~

Generate daily or weekly temperature boxplot summaries for a year.

**Command Line Arguments:**

.. code-block:: text

   usage: boxplot_temperature.py [-h] -y YEAR [-f {daily,weekly}]

   optional arguments:
     -h, --help            Show help message and exit
     -y YEAR               Year (YYYY)
     -f {daily,weekly}     Frequency: daily or weekly (default: daily)

**Features:**

* Reads from YYYY subdirectory structure
* Filters out bad data (QC flag 2)
* Converts temperature to Celsius
* Default input directory: /gws/pw/j07/ncas_obs_vol2/cao/

**Example:**

.. code-block:: bash

   # Daily boxplots
   python boxplot_temperature.py -y 2020 -f daily

   # Weekly boxplots
   python boxplot_temperature.py -y 2020 -f weekly

Utility Scripts
---------------

find_purge_shift.py
~~~~~~~~~~~~~~~~~~~

Calculate the time-of-day shift between purge cycles in two NetCDF files.

**Command Line Arguments:**

.. code-block:: text

   usage: find_purge_shift.py file1 file2

   positional arguments:
     file1                 First NetCDF file
     file2                 Second NetCDF file

**Features:**

* Reports shift in seconds with microsecond precision
* Compares only time-of-day (ignores date)
* Uses first purge period from each file

**Example:**

.. code-block:: bash

   python find_purge_shift.py yesterday.nc today.nc

count_purge_flags.py
~~~~~~~~~~~~~~~~~~~~

Count the number of purge flag occurrences in a NetCDF file.

**Example:**

.. code-block:: bash

   python count_purge_flags.py data.nc

Batch Processing
----------------

proc_year.sh
~~~~~~~~~~~~

Shell script to process an entire year of data sequentially.

**Usage:**

.. code-block:: text

   ./proc_year.sh YEAR [CORR_FILE_TEMP] [CORR_FILE_RH]

**Arguments:**

* YEAR: Four-digit year to process
* CORR_FILE_TEMP: Optional temperature correction file
* CORR_FILE_RH: Optional RH correction file

**Workflow:**

1. Loops through all dates in the specified year
2. Processes each day with process_hmp155.py
3. Applies QC flags with flag_purge_times.py
4. Uses previous day's file for continuity
5. Skips processing if output file already exists

**Example:**

.. code-block:: bash

   # Process without corrections
   ./proc_year.sh 2020

   # Process with correction files
   ./proc_year.sh 2020 temp_corrections.txt rh_corrections.txt

proc_year_f5.sh
~~~~~~~~~~~~~~~

Shell script to process an entire year of legacy Format5 data sequentially.

**Usage:**

.. code-block:: text

   ./proc_year_f5.sh -y YEAR

**Arguments:**

* ``-y YEAR``: Four-digit year to process (required)

**Data Locations:**

* Input: ``/gws/pw/j07/ncas_obs_vol2/cao/raw_data/legacy/cao-analog-format5_chilbolton/data/long-term/format5/``
* Output: ``/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1_f5/YYYY/``
* Metadata: ``metadata_f5.json``

**Processing Range:**

* Default date range: August 25 to December 31
* Format5 files named: ``chanYYMMDD.000`` (e.g., ``chan241231.000``)

**Workflow:**

1. Activates conda environment ``cao_3_11``
2. Loops through each day in the date range
3. Processes Format5 file with ``process_hmp155_f5.py``
4. Applies QC flags with ``flag_purge_times.py``
5. Uses previous day's NetCDF file for continuity
6. Handles correction files if specified
7. Outputs to year-specific directory

**Features:**

* Automatic directory creation
* Previous day file lookup
* Optional temperature and RH correction files
* Handles missing input files gracefully
* Uses Format5-specific metadata

**Example:**

.. code-block:: bash

   # Process 2024 Format5 data
   ./proc_year_f5.sh -y 2024

   # With correction files
   ./proc_year_f5.sh -y 2024 \
       --corr_file_temperature temp_corrections_2024.txt \
       --corr_file_rh rh_corrections_2024.txt

proc_year_stfc.sh
~~~~~~~~~~~~~~~~~

Shell script to process an entire year of STFC data (alternative processing variant).

**Usage:**

.. code-block:: text

   ./proc_year_stfc.sh YEAR [CORR_FILE_TEMP] [CORR_FILE_RH]

**Features:**

* Similar workflow to ``proc_year.sh``
* Uses ``process_hmp155_stfc.py`` for processing
* Uses ``metadata_stfc.json`` for instrument configuration
* Outputs to STFC-specific directory structure

**Example:**

.. code-block:: bash

   ./proc_year_stfc.sh 2020

Utility Scripts
---------------

split_cr1000x_data_daily.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Split CR1000X data files into daily files organized in YYYY/YYYYMM subdirectories.

**Command Line Arguments:**

.. code-block:: text

   usage: split-cr1000x-data-daily [-h] -i INPUT_DIR [-o OUTPUT_DIR] 
                                    [-d DELIMITER] [-t TIMESTAMP_COLUMN] [-v]

   optional arguments:
     -h, --help            Show help message and exit
     -i INPUT_DIR          Directory containing CR1000XSeries_Chilbolton_Rxcabinmet1*.dat files
     -o OUTPUT_DIR         Directory to write daily files (default: daily_files)
     -d DELIMITER          Delimiter for input file (default: ',')
     -t TIMESTAMP_COLUMN   Name of timestamp column (default: TIMESTAMP)
     -v, --verbose         Enable verbose output

**Features:**

* Preserves TOA5 header format in output files
* Assigns midnight (00:00:00) records to the previous day
* Creates YYYY/YYYYMM directory structure automatically
* Automatically deduplicates identical daily files
* Handles multiple input files in batch

**Example:**

.. code-block:: bash

   # Split all CR1000X files in toproc/ directory
   split-cr1000x-data-daily -i /path/to/toproc/ -o daily_files/ -v

   # Custom timestamp column
   split-cr1000x-data-daily -i raw_data/ -o output/ -t TIMESTAMP -v

**Output Structure:**

.. code-block:: text

   daily_files/
   ├── 2024/
   │   ├── 202401/
   │   │   ├── CR1000XSeries_Chilbolton_Rxcabinmet1_20240101.dat
   │   │   ├── CR1000XSeries_Chilbolton_Rxcabinmet1_20240102.dat
   │   │   └── ...
   │   └── 202402/
   │       └── ...
   └── 2025/
       └── ...


