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
* ncas-amof-netcdf-template

Installation Methods
--------------------

The package can be installed using pip in several ways.

From PyPI (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~

Once published, install the latest stable version:

.. code-block:: bash

   pip install chilbolton-temperature-rh-utils

From GitHub
~~~~~~~~~~~

Install directly from GitHub without cloning the repository:

**Latest version from main branch:**

.. code-block:: bash

   pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git

**Specific branch:**

.. code-block:: bash

   pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@branch-name

**Specific tag or release:**

.. code-block:: bash

   pip install git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git@v1.0.0

**With optional dependencies:**

.. code-block:: bash

   pip install "chilbolton-temperature-rh-utils[dev,docs] @ git+https://github.com/longlostjames/chilbolton-temperature-rh-utils.git"

**Using SSH (if you have SSH keys configured):**

.. code-block:: bash

   pip install git+ssh://git@github.com/longlostjames/chilbolton-temperature-rh-utils.git

From Source (Development)
~~~~~~~~~~~~~~~~~~~~~~~~~~

For development or to use the latest version:

.. code-block:: bash

   git clone https://github.com/longlostjames/chilbolton-temperature-rh-utils.git
   cd chilbolton-temperature-rh-utils
   pip install -e .

The ``-e`` flag installs in "editable" mode, so changes to the code are immediately available.

With Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install with development tools:

.. code-block:: bash

   pip install -e ".[dev]"

Install with documentation tools:

.. code-block:: bash

   pip install -e ".[docs]"

Install with all optional dependencies:

.. code-block:: bash

   pip install -e ".[dev,docs]"

Setting Up the Environment
---------------------------

Using Conda (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Create and activate a new conda environment:

.. code-block:: bash

   conda create -n cao_3_11 python=3.11
   conda activate cao_3_11

Install the package:

.. code-block:: bash

   cd chilbolton-temperature-rh-utils
   pip install -e .

Using Virtual Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, use Python's built-in venv:

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .

Command-Line Tools
------------------

After installation, the following command-line tools are available:

.. code-block:: bash

   process-hmp155                  # Process CR1000X data
   process-hmp155-f5               # Process Format5 data
   process-hmp155-stfc             # Process STFC variant
   flag-hmp155-purge-times         # Automated purge flagging
   flag-hmp155-purge-times-manual  # Manual purge flagging
   flag-hmp155-low-temperature     # Flag low temperatures
   find-hmp155-purge-shift         # Calculate purge time shifts
   count-hmp155-purge-flags        # Count purge flags

Verify the installation:

.. code-block:: bash

   process-hmp155 --help
   process-hmp155-f5 --help
   flag-hmp155-purge-times --help

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
