import numpy as np
import polars as pl
from datetime import datetime
from .read_format5_header import read_format5_header

def read_format5_content(path_file, header):
    """
    Reads the content of a format5 data file and stores it in a Polars DataFrame.
    Extracts only the 'ws_ch' and 'wd_ch' columns.
    """
    # Open the format5 file
    with open(path_file, "r") as fid:
        # Skip to the start of the content
        fid.seek(header["comment_size"] + header["header_size"], 0)

        # Prepare to read the content line by line
        content = []
        for line in fid:
            # Split the line into the first 5 comma-separated values and the rest space-separated
            parts = line.strip().split(" ", 1)
            timestamp_part = parts[0].split(",")  # First 5 values are comma-separated
            data_part = parts[1].split() if len(parts) > 1 else []  # Remaining values are space-separated

            # Combine the timestamp and data parts
            content.append([*map(float, timestamp_part), *map(float, data_part)])

    # Convert the content to a NumPy array
    content = np.array(content, dtype=float)  # Use dtype=object to handle mixed types

    # Prepare timestamping of the data
    # Extract the year from the file name
    year = int(path_file[-10:-8]) + 2000

    # Convert the first 5 columns (time columns) into datetime strings
    timestamps = [
        f"{year:04d}-{int(row[0]):02d}-{int(row[1]):02d} {int(row[2]):02d}:{int(row[3]):02d}:{int(row[4]):02d}"
        for row in content
    ]

    # Replace the first 5 columns with the timestamps
    data = np.column_stack((timestamps, content[:, 5:]))

    # Create column labels
    column_labels = ["timestamp"] + header["chids"]

    # Create a Polars DataFrame
    df = pl.DataFrame(data, schema=column_labels)

    # Rename columns in the DataFrame
    df = df.rename({
        "timestamp": "TIMESTAMP",
        "ws_ch": "WS_Avg",
        "wd_ch": "WD_Avg"
    })

    # Explicitly cast columns to the correct types
    df = df.with_columns(
        # Cast TIMESTAMP to Datetime
        pl.col("TIMESTAMP").str.strptime(pl.Datetime, format="%Y-%m-%d %H:%M:%S").alias("TIMESTAMP"),
        
        # Cast WS_Avg and WD_Avg to Float64
        pl.col("WS_Avg").cast(pl.Float64).alias("WS_Avg"),
        pl.col("WD_Avg").cast(pl.Float64).alias("WD_Avg")
    )

    return df