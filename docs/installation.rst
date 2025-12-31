Installation
============

Requirements
------------

This software requires Python 3.11 or later. The following Python packages are required:

* xarray
* netCDF4
* polars
* pandas
* matplotlib
* numpy
* cftime

Setting Up the Environment
---------------------------

Using Conda (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Create and activate a new conda environment:

.. code-block:: bash

   conda create -n cao_3_11 python=3.11
   conda activate cao_3_11

Install required packages:

.. code-block:: bash

   conda install -c conda-forge xarray netCDF4 polars pandas matplotlib numpy cftime

Installing the Software
------------------------

Clone the repository:

.. code-block:: bash

   git clone https://github.com/longlostjames/chilbolton-temperature-rh-utils.git
   cd chilbolton-temperature-rh-utils

The software is currently a collection of Python scripts rather than an installable package. Simply ensure the required dependencies are installed and run the scripts directly.

File System Setup
-----------------

The software expects data to be organized in a specific directory structure:

.. code-block:: text

   /gws/pw/j07/ncas_obs_vol2/cao/
   ├── 2020/
   │   ├── 202001/
   │   │   ├── CR1000X_Chilbolton_Rxcabinmet1_20200101.dat
   │   │   └── ...
   │   └── ncas-temperature-rh-1_cao_20200101_surface-met_v1.0.nc
   └── ...

Configuration Files
-------------------

Metadata Files
~~~~~~~~~~~~~~

The processing scripts require metadata JSON files that define instrument characteristics, processing parameters, and CF-compliant attributes.

Example metadata file (``metadata.json``):

.. code-block:: json

   {
     "platform": "cao",
     "instrument": "ncas-temperature-rh-1",
     "variables": {
       "air_temperature": {
         "scale": 0.02,
         "offset": 233.15,
         "units": "K"
       }
     }
   }

Correction Files
~~~~~~~~~~~~~~~~

Optional text files can be provided to flag specific time intervals as bad data:

.. code-block:: text

   2020-01-15 12:30:00, 2020-01-15 13:45:00
   2020-01-20 08:00:00, 2020-01-20 09:00:00

Verification
------------

Verify the installation by running:

.. code-block:: bash

   python process_hmp155.py --help
   python flag_purge_times.py --help
   python make_quicklooks.py --help

If you see the help messages, the installation is successful.
