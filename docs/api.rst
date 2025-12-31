API Reference
=============

This section provides detailed API documentation for the key functions and classes in the Chilbolton Temperature RH Utils Software.

flag_purge_times Module
------------------------

.. py:module:: flag_purge_times

detect_flat
~~~~~~~~~~~

.. py:function:: detect_flat(data, window_size=240, std_threshold=0.07)

   Detect flat regions in time series data using a rolling standard deviation.

   :param data: xarray DataArray with time dimension
   :type data: xarray.DataArray
   :param window_size: Size of rolling window in number of records (default: 240)
   :type window_size: int
   :param std_threshold: Maximum standard deviation to consider "flat" (default: 0.07)
   :type std_threshold: float
   :return: Boolean mask where True indicates flat regions
   :rtype: numpy.ndarray

   **Example:**

   .. code-block:: python

      import xarray as xr
      from flag_purge_times import detect_flat

      ds = xr.open_dataset('data.nc')
      flat_mask = detect_flat(ds['air_temperature'], 
                               window_size=240, 
                               std_threshold=0.07)

exclude_high_rh
~~~~~~~~~~~~~~~

.. py:function:: exclude_high_rh(rh_data, threshold=99.8)

   Create a mask excluding high relative humidity values.

   :param rh_data: xarray DataArray containing relative humidity values
   :type rh_data: xarray.DataArray
   :param threshold: RH threshold above which to exclude (default: 99.8)
   :type threshold: float
   :return: Boolean mask where True indicates values to exclude
   :rtype: numpy.ndarray

detect_rh_dips
~~~~~~~~~~~~~~

.. py:function:: detect_rh_dips(ds, temp_flat_mask, date_cutoff='2018-03-13')

   Detect RH dip regions that occur during temperature flat periods.

   :param ds: xarray Dataset containing air_temperature and relative_humidity
   :type ds: xarray.Dataset
   :param temp_flat_mask: Boolean mask of temperature flat regions
   :type temp_flat_mask: numpy.ndarray
   :param date_cutoff: Date string (YYYY-MM-DD) dividing single vs two purge periods
   :type date_cutoff: str
   :return: Boolean mask where True indicates RH dip regions
   :rtype: numpy.ndarray

get_purge_intervals
~~~~~~~~~~~~~~~~~~~

.. py:function:: get_purge_intervals(ds, purge_mask)

   Convert a boolean purge mask into start/end time intervals.

   :param ds: xarray Dataset with time coordinate
   :type ds: xarray.Dataset
   :param purge_mask: Boolean mask where True indicates purge periods
   :type purge_mask: numpy.ndarray
   :return: List of tuples (start_time, end_time) for each purge interval
   :rtype: list of tuple

   **Example:**

   .. code-block:: python

      intervals = get_purge_intervals(ds, purge_mask)
      for start, end in intervals:
          print(f"Purge from {start} to {end}")

manual_flag_purge_times Module
-------------------------------

.. py:module:: manual_flag_purge_times

get_previous_day_purge_times
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: get_previous_day_purge_times(prev_file)

   Extract purge start/end times from previous day's NetCDF file.

   :param prev_file: Path to previous day's NetCDF file
   :type prev_file: str
   :return: List of tuples (start_time, end_time) for purge intervals
   :rtype: list of tuple

   **Example:**

   .. code-block:: python

      from manual_flag_purge_times import get_previous_day_purge_times

      intervals = get_previous_day_purge_times('yesterday.nc')

flag_based_on_time_of_day
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: flag_based_on_time_of_day(file_path, intervals, shift_seconds=0.0)

   Flag purge periods in a file based on time-of-day matching.

   :param file_path: Path to NetCDF file to modify
   :type file_path: str
   :param intervals: List of (start_time, end_time) tuples from previous day
   :type intervals: list of tuple
   :param shift_seconds: Time shift to apply in seconds (default: 0.0)
   :type shift_seconds: float

set_time_units_to_seconds_since_epoch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: set_time_units_to_seconds_since_epoch(file_path)

   Convert time variable units to "seconds since 1970-01-01 00:00:00".

   :param file_path: Path to NetCDF file to modify
   :type file_path: str

make_quicklooks Module
----------------------

.. py:module:: make_quicklooks

plot_day
~~~~~~~~

.. py:function:: plot_day(ds, output_dir, date_str)

   Generate quicklook plots for a single day.

   :param ds: xarray Dataset containing air_temperature, relative_humidity, and QC flags
   :type ds: xarray.Dataset
   :param output_dir: Directory to save PNG plots
   :type output_dir: str
   :param date_str: Date string in YYYYMMDD format
   :type date_str: str

   **Creates:**
   
   * Full day overview plot (2 panels: temperature and RH)
   * Zoomed plots for each purge period

   **Example:**

   .. code-block:: python

      import xarray as xr
      from make_quicklooks import plot_day

      ds = xr.open_dataset('data.nc')
      plot_day(ds, '/path/to/plots/', '20200115')

process_hmp155 Module
---------------------

.. py:module:: process_hmp155

preprocess_data
~~~~~~~~~~~~~~~

.. py:function:: preprocess_data(input_file)

   Read and preprocess CR1000X data file using polars.

   :param input_file: Path to CR1000X DAT file
   :type input_file: str
   :return: Polars DataFrame with parsed timestamps and cleaned data
   :rtype: polars.DataFrame

   **Features:**
   
   * Skips 4-line TOA5 header
   * Parses TIMESTAMP column to datetime
   * Handles quoted fields
   * Ignores parsing errors

split_cr1000x_data_daily Module
--------------------------------

.. py:module:: split_cr1000x_data_daily

split_file
~~~~~~~~~~

.. py:function:: split_file(input_file, output_dir, verbose=False)

   Split a continuous CR1000X file into daily files.

   :param input_file: Path to input CR1000X file
   :type input_file: str
   :param output_dir: Root output directory
   :type output_dir: str
   :param verbose: Print verbose output (default: False)
   :type verbose: bool

   **Creates:**
   
   * Daily files in YYYY/YYYYMM/ directory structure
   * Files named: CR1000X_Chilbolton_Rxcabinmet1_YYYYMMDD.dat
   * Midnight records shifted to previous day

deduplicate_daily_files
~~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: deduplicate_daily_files(output_dir, verbose=False)

   Remove duplicate daily files with identical content.

   :param output_dir: Root directory containing YYYY/YYYYMM/ structure
   :type output_dir: str
   :param verbose: Print verbose output (default: False)
   :type verbose: bool

boxplot_temperature Module
---------------------------

.. py:module:: boxplot_temperature

get_daily_temperatures
~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: get_daily_temperatures(year, input_dir)

   Extract daily temperature data for boxplot generation.

   :param year: Year to process (YYYY)
   :type year: str
   :param input_dir: Root directory containing NetCDF files
   :type input_dir: str
   :return: Dictionary mapping dates to temperature arrays (in Celsius)
   :rtype: dict

get_weekly_temperatures
~~~~~~~~~~~~~~~~~~~~~~~

.. py:function:: get_weekly_temperatures(year, input_dir)

   Extract weekly temperature data for boxplot generation.

   :param year: Year to process (YYYY)
   :type year: str
   :param input_dir: Root directory containing NetCDF files
   :type input_dir: str
   :return: Dictionary mapping week numbers to temperature arrays (in Celsius)
   :rtype: dict

plot_boxplot
~~~~~~~~~~~~

.. py:function:: plot_boxplot(data_dict, title, xlabel, output_file)

   Create and save a boxplot figure.

   :param data_dict: Dictionary mapping labels to data arrays
   :type data_dict: dict
   :param title: Plot title
   :type title: str
   :param xlabel: X-axis label
   :type xlabel: str
   :param output_file: Output PNG file path
   :type output_file: str

Data Structures
---------------

QC Flag Values
~~~~~~~~~~~~~~

The software uses a standardized QC flag scheme:

.. code-block:: python

   QC_FLAGS = {
       0: 'not_used',        # Uninitialized or no QC applied
       1: 'good_data',       # Data passed all QC checks
       2: 'bad_data',        # Known bad data (instrument error, etc.)
       3: 'purge_cycle',     # Sensor purge in progress
       4: 'recovery'         # Data recovery period after purge (RH only)
   }

NetCDF File Structure
~~~~~~~~~~~~~~~~~~~~~

Processed NetCDF files follow CF-1.8 conventions:

.. code-block:: text

   Dimensions:
     time: unlimited
   
   Variables:
     time(time): int64
       units: "seconds since 1970-01-01 00:00:00"
       calendar: "gregorian"
     
     air_temperature(time): float32
       units: "K"
       standard_name: "air_temperature"
       ancillary_variables: "qc_flag_air_temperature"
     
     qc_flag_air_temperature(time): int8
       units: "1"
       flag_values: [0, 1, 2, 3, 4]
       flag_meanings: "not_used good_data bad_data purge_cycle recovery"
     
     relative_humidity(time): float32
       units: "%"
       standard_name: "relative_humidity"
       ancillary_variables: "qc_flag_relative_humidity"
     
     qc_flag_relative_humidity(time): int8
       units: "1"
       flag_values: [0, 1, 2, 3, 4]
       flag_meanings: "not_used good_data bad_data purge_cycle recovery"
