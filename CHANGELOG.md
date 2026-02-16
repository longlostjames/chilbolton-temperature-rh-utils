# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-16

### Added
- **Variable Purge Periods Support**: The system now dynamically handles any number of purge periods per day, not just the standard 2. This is particularly useful for days with maintenance activities or testing.
  - `apply_purge_indices.py` now automatically detects and processes CSV files with variable column counts
  - Processing iterates through all purge periods dynamically until no more are found
  - Column naming follows pattern: `purge1_*`, `purge2_*`, `purge3_*`, etc.

- **Bad Data Indices Management**: New workflow for manually flagging bad data periods
  - `extract_bad_data_indices.py`: Extract bad data flags from NetCDF files to CSV for review
  - `apply_bad_data_indices.py`: Apply manually edited bad data flags back to NetCDF files
  - Command-line tools: `extract-hmp155-bad-data-indices` and `apply-hmp155-bad-data-indices`
  - Support for multiple bad data periods per day

- **Test Infrastructure**: Added `test_variable_purge_periods.py` to verify handling of CSV files with variable numbers of purge periods

### Changed
- Updated all processing modules to support variable purge periods:
  - `process_hmp155.py`
  - `process_hmp155_f5.py`
  - `process_hmp155_stfc.py`
  - `flag_purge_times.py`
  - `manual_flag_purge_times.py`
  - `fix_isolated_recovery_flags.py`

- Enhanced `extract_purge_indices.py` to support variable purge periods in output CSV

### Fixed
- Purge period detection now correctly handles days with more than 2 purge cycles
- CSV reading handles variable column counts gracefully

## [0.1.0] - Previous Releases

Initial releases with core functionality:
- Campbell Scientific CR1000X data processing
- Legacy Format5 file support
- Automated purge cycle detection (2 periods per day)
- Quality control flagging
- Quicklook plot generation
- Batch processing scripts

---

[1.0.0]: https://github.com/longlostjames/chilbolton-temperature-rh-utils/compare/v0.1.0...v1.0.0
