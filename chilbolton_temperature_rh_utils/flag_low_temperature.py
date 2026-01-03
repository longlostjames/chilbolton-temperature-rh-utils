#!/usr/bin/env python

import argparse
import numpy as np
from netCDF4 import Dataset

# Define QC flag values (consistent with manual_flag_purge_times.py)
FLAG_GOOD = 1
FLAG_BAD = 2
FLAG_PURGE = 3
FLAG_RH_RECOVERY = 4

def flag_low_temperature(nc_file, temp_threshold=245):
    """
    Flag data points where air_temperature is below the specified threshold as bad data (qc_flag = 2).
    Also flag the corresponding points in relative_humidity as bad data (qc_flag = 2).

    Parameters:
        nc_file (str): Path to the NetCDF file.
        temp_threshold (float): The temperature threshold below which data is flagged as bad.
    """
    with Dataset(nc_file, mode="r+") as ds:
        # Ensure QC flags exist for air_temperature and relative_humidity
        if "qc_flag_air_temperature" not in ds.variables:
            qc_flag_air_temp = ds.createVariable("qc_flag_air_temperature", "i1", ds.variables["air_temperature"].dimensions)
            qc_flag_air_temp[:] = FLAG_GOOD
            qc_flag_air_temp.units = "1"
            qc_flag_air_temp.long_name = "Data Quality flag: Air Temperature"
            qc_flag_air_temp.standard_name = "quality_flag"
            qc_flag_air_temp.flag_values = np.array([0, 1, 2, 3], dtype=np.int8)
            qc_flag_air_temp.flag_meanings = "not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge"
        else:
            qc_flag_air_temp = ds.variables["qc_flag_air_temperature"]

        if "qc_flag_relative_humidity" not in ds.variables:
            qc_flag_rh = ds.createVariable("qc_flag_relative_humidity", "i1", ds.variables["relative_humidity"].dimensions)
            qc_flag_rh[:] = FLAG_GOOD
            qc_flag_rh.units = "1"
            qc_flag_rh.long_name = "Data Quality flag: Relative Humidity"
            qc_flag_rh.standard_name = "quality_flag"
            qc_flag_rh.flag_values = np.array([0, 1, 2, 3, 4], dtype=np.int8)
            qc_flag_rh.flag_meanings = "not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge recovery_in_rh_after_purge"
        else:
            qc_flag_rh = ds.variables["qc_flag_relative_humidity"]

        # Identify points where air_temperature is below the threshold
        air_temperature = ds.variables["air_temperature"][:]
        low_temp_mask = air_temperature < temp_threshold

        # Apply QC flag 2 to air_temperature and relative_humidity for those points
        # This will override any existing flags (good, purge, recovery, etc.)
        qc_flag_air_temp[low_temp_mask] = FLAG_BAD
        qc_flag_rh[low_temp_mask] = FLAG_BAD

        print(f"Flagged {np.sum(low_temp_mask)} points where air_temperature < {temp_threshold}K as bad data (qc_flag = 2).")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Flag air_temperature below a threshold as bad data (qc_flag = 2).")
    parser.add_argument("-f", "--file", required=True, help="Path to the NetCDF file")
    parser.add_argument("--threshold", type=float, default=245.0, help="Temperature threshold below which data is flagged as bad (default: 245K)")
    args = parser.parse_args()

    # Flag low temperatures
    flag_low_temperature(args.file, temp_threshold=args.threshold)

if __name__ == "__main__":
    main()