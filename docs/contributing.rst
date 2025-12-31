Contributing
============

Thank you for your interest in contributing to the Chilbolton Temperature RH Utils Software!

Development Setup
-----------------

Fork and Clone
~~~~~~~~~~~~~~

1. Fork the repository on GitHub
2. Clone your fork locally:

.. code-block:: bash

   git clone https://github.com/YOUR_USERNAME/chilbolton-temperature-rh-utils.git
   cd chilbolton-temperature-rh-utils

3. Add the upstream repository:

.. code-block:: bash

   git remote add upstream https://github.com/longlostjames/chilbolton-temperature-rh-utils.git

Development Environment
~~~~~~~~~~~~~~~~~~~~~~~

Create a development environment with all dependencies:

.. code-block:: bash

   conda create -n cao_dev python=3.11
   conda activate cao_dev
   conda install -c conda-forge xarray netCDF4 polars pandas matplotlib numpy cftime

Code Style
----------

Python Style Guide
~~~~~~~~~~~~~~~~~~

* Follow PEP 8 style guidelines
* Use 4 spaces for indentation (no tabs)
* Maximum line length: 100 characters
* Use descriptive variable names

Documentation Strings
~~~~~~~~~~~~~~~~~~~~~

Use NumPy-style docstrings for all functions:

.. code-block:: python

   def detect_flat(data, window_size=240, std_threshold=0.07):
       """
       Detect flat regions in time series data.

       Parameters
       ----------
       data : xarray.DataArray
           Time series data with time dimension
       window_size : int, optional
           Rolling window size in records (default: 240)
       std_threshold : float, optional
           Maximum standard deviation for "flat" (default: 0.07)

       Returns
       -------
       numpy.ndarray
           Boolean mask where True indicates flat regions
       """
       pass

Testing
-------

Manual Testing
~~~~~~~~~~~~~~

Before submitting changes:

1. Test with sample data files
2. Verify NetCDF output structure
3. Check QC flag values
4. Generate quicklook plots
5. Run batch processing script

Testing Checklist
~~~~~~~~~~~~~~~~~

- [ ] Code runs without errors
- [ ] NetCDF files have correct dimensions and variables
- [ ] QC flags are correctly applied
- [ ] Plots display correctly
- [ ] Documentation updated
- [ ] No breaking changes to existing functionality

Submitting Changes
------------------

Workflow
~~~~~~~~

1. Create a new branch for your changes:

.. code-block:: bash

   git checkout -b feature/your-feature-name

2. Make your changes and commit:

.. code-block:: bash

   git add .
   git commit -m "Add feature: brief description"

3. Push to your fork:

.. code-block:: bash

   git push origin feature/your-feature-name

4. Open a pull request on GitHub

Pull Request Guidelines
~~~~~~~~~~~~~~~~~~~~~~~

* Provide a clear description of changes
* Reference any related issues
* Include example usage if adding new features
* Update documentation as needed
* Ensure all tests pass

Commit Messages
~~~~~~~~~~~~~~~

Use clear, descriptive commit messages:

* **Good:** "Add support for multiple purge periods per day"
* **Good:** "Fix temperature conversion error in plotting"
* **Bad:** "Fixed stuff"
* **Bad:** "Update file.py"

Reporting Issues
----------------

Bug Reports
~~~~~~~~~~~

When reporting bugs, please include:

* Python version and dependency versions
* Operating system
* Minimal code example to reproduce
* Error messages and traceback
* Expected vs actual behavior

Feature Requests
~~~~~~~~~~~~~~~~

For feature requests, describe:

* Use case and motivation
* Proposed solution
* Potential impact on existing code
* Example usage

Areas for Contribution
----------------------

High Priority
~~~~~~~~~~~~~

* Automated testing framework
* Support for additional sensor types
* Performance optimization for large datasets
* Improved error handling and validation

Documentation
~~~~~~~~~~~~~

* Tutorial examples
* Best practices guide
* Video demonstrations
* Translation to other languages

Code Improvements
~~~~~~~~~~~~~~~~~

* Refactor repeated code into reusable functions
* Add type hints
* Improve logging and debugging output
* Optimize memory usage

Contact
-------

For questions or discussions:

* Open an issue on GitHub
* Contact the maintainers at: [email@example.com]

License
-------

By contributing, you agree that your contributions will be licensed under the same license as the project.
