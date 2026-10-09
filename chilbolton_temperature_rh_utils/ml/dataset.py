"""PyTorch Dataset & DataLoader builder for HMP155 purge and recovery detection.

Pairs 10-second netCDF time series (air_temperature, relative_humidity) with
sample-level ground-truth flags extracted from the .corr files.
"""

import glob
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import xarray as xr

from chilbolton_temperature_rh_utils.qc_corrections import (
    FLAG_BAD,
    FLAG_GOOD,
    FLAG_NOT_USED,
    FLAG_PURGE,
    FLAG_RECOVERY,
    load_corr_intervals,
    qc_from_intervals,
)

# Default standardization stats (derived from multi-year Chilbolton HMP155 data)
DEFAULT_TEMP_MEAN = 10.0  # deg C
DEFAULT_TEMP_STD = 7.0
DEFAULT_RH_MEAN = 80.0    # %
DEFAULT_RH_STD = 15.0

# Default sequence target size (24 hours at 10-second sampling = 8640 points)
TARGET_SEQUENCE_LENGTH = 8640

# Class mapping: map raw QC flags to 0-indexed segmentation classes
# 0: Good/Normal data, 1: Purge (flag 3), 2: Recovery (flag 4)
# Flag 2 (Bad Data) is mapped to ignore_index (-100) so loss functions ignore it.
FLAG_TO_CLASS = {
    FLAG_NOT_USED: 0,
    FLAG_GOOD: 0,
    FLAG_BAD: -100,
    FLAG_PURGE: 1,
    FLAG_RECOVERY: 2,
}


def extract_date_from_filename(path: Union[str, Path]) -> Optional[datetime]:
    """Extract datetime date from a netCDF filename matching *YYYYMMDD*.nc."""
    match = re.search(r"_(\d{8})_", os.path.basename(path))
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None
    return None


class HMP155Dataset(Dataset):
    """PyTorch Dataset for daily HMP155 temperature & relative humidity sequences.

    Returns:
        x: Tensor of shape (2, N) - [normalized_temp, normalized_rh]
        y: Tensor of shape (N,) - Class labels (0: Good, 1: Purge, 2: Recovery, -100: Bad/Ignore)
        meta: Dict containing filename, date, sample count
    """

    def __init__(
        self,
        nc_files: List[Union[str, Path]],
        corr_dir: Union[str, Path],
        temp_mean: float = DEFAULT_TEMP_MEAN,
        temp_std: float = DEFAULT_TEMP_STD,
        rh_mean: float = DEFAULT_RH_MEAN,
        rh_std: float = DEFAULT_RH_STD,
        ignore_bad_data: bool = True,
        ignore_index: int = -100,
    ):
        """
        Args:
            nc_files: List of paths to level1d NetCDF files.
            corr_dir: Path to base of .corr corrections directory.
            temp_mean, temp_std: Normalization stats for air temperature (degC).
            rh_mean, rh_std: Normalization stats for relative humidity (%).
            ignore_bad_data: If True, maps bad data (flag=2) to ignore_index for loss.
            ignore_index: Class label used for ignored samples (default: -100).
        """
        self.nc_files = [Path(f) for f in nc_files]
        self.corr_dir = Path(corr_dir)
        self.temp_mean = temp_mean
        self.temp_std = temp_std
        self.rh_mean = rh_mean
        self.rh_std = rh_std
        self.ignore_bad_data = ignore_bad_data
        self.ignore_index = ignore_index

    def __len__(self) -> int:
        return len(self.nc_files)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, Dict]:
        nc_path = self.nc_files[idx]
        
        # Load NetCDF dataset
        with xr.open_dataset(nc_path) as ds:
            num_points = ds.sizes.get("time", 0)
            if num_points == 0:
                raise ValueError(f"File {nc_path} has 0 time samples.")
                
            date = extract_date_from_filename(nc_path)
            if date is None and "time" in ds:
                date = pd.to_datetime(ds["time"].values[0]).date()

            # Extract air temperature (°C)
            temp = ds["air_temperature"].values.copy()
            if ds["air_temperature"].attrs.get("units", "").upper() in ("K", "KELVIN") or np.mean(temp) > 200:
                temp -= 273.15

            # Extract relative humidity (%)
            rh = ds["relative_humidity"].values.copy()

        # Load ground truth from .corr files
        temp_intervals = load_corr_intervals(self.corr_dir, "temperature", date)
        rh_intervals = load_corr_intervals(self.corr_dir, "rh", date)

        qc_temp = qc_from_intervals(num_points, temp_intervals)
        qc_rh = qc_from_intervals(num_points, rh_intervals)

        # Merge variable flags into a single target sequence:
        # Purge (3) takes precedence, then Recovery (4), then Bad Data (2), then Good (1)
        merged_target = np.zeros(num_points, dtype=np.int64)
        
        # Set normal/good
        merged_target[:] = FLAG_TO_CLASS[FLAG_GOOD]

        # Apply flags with priority: Purge > Recovery > Bad Data
        for sample_i in range(num_points):
            t_flag = qc_temp[sample_i]
            r_flag = qc_rh[sample_i]

            if t_flag == FLAG_PURGE or r_flag == FLAG_PURGE:
                merged_target[sample_i] = FLAG_TO_CLASS[FLAG_PURGE]
            elif r_flag == FLAG_RECOVERY:
                merged_target[sample_i] = FLAG_TO_CLASS[FLAG_RECOVERY]
            elif t_flag == FLAG_BAD or r_flag == FLAG_BAD:
                merged_target[sample_i] = self.ignore_index if self.ignore_bad_data else 0

        # Normalize basic features
        temp_norm = (temp - self.temp_mean) / self.temp_std
        rh_norm = (rh - self.rh_mean) / self.rh_std

        # Compute derivative and rolling variability features
        rh_diff = np.diff(rh, prepend=rh[0])
        rh_series = pd.Series(rh)
        rh_rstd = rh_series.rolling(30, center=True, min_periods=1).std().fillna(0).to_numpy() / 2.0

        # Construct 4-channel feature tensor: shape (4, N)
        # Channels: [temp_norm, rh_norm, rh_diff, rh_rstd]
        x_tensor = torch.tensor(
            np.stack([temp_norm, rh_norm, rh_diff, rh_rstd], axis=0),
            dtype=torch.float32,
        )
        
        # Construct target tensor: shape (N,)
        y_tensor = torch.tensor(merged_target, dtype=torch.long)

        # Resample to fixed target sequence length if needed (to ensure batch collation)
        if num_points != TARGET_SEQUENCE_LENGTH:
            # Resample X via 1D linear interpolation: shape (1, 4, N) -> (4, TARGET_SEQUENCE_LENGTH)
            x_tensor = F.interpolate(
                x_tensor.unsqueeze(0), size=TARGET_SEQUENCE_LENGTH, mode="linear", align_corners=False
            ).squeeze(0)
            
            # Resample Y via nearest neighbor interpolation: shape (1, 1, N) -> (TARGET_SEQUENCE_LENGTH,)
            y_tensor = F.interpolate(
                y_tensor.unsqueeze(0).unsqueeze(0).float(), size=TARGET_SEQUENCE_LENGTH, mode="nearest"
            ).squeeze(0).squeeze(0).long()

        meta = {
            "nc_file": str(nc_path),
            "date": date.strftime("%Y-%m-%d") if date else "",
            "num_points": num_points,
        }

        return x_tensor, y_tensor, meta


def discover_nc_files(
    roots: List[Union[str, Path]],
    years: Optional[List[int]] = None,
) -> List[Path]:
    """Find all daily NetCDF files matching year filters across data roots."""
    found_files = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        
        target_years = years if years else [
            int(d.name) for d in root_path.iterdir() if d.is_dir() and d.name.isdigit() and len(d.name) == 4
        ]
        
        for yr in sorted(target_years):
            yr_dir = root_path / str(yr)
            if yr_dir.exists():
                found_files.extend(sorted(yr_dir.glob("*.nc")))

    return found_files


def create_data_loaders(
    nc_roots: List[Union[str, Path]],
    corr_dir: Union[str, Path],
    train_years: List[int],
    val_years: List[int],
    batch_size: int = 4,
    num_workers: int = 0,
) -> Tuple[DataLoader, DataLoader]:
    """Helper to create training and validation PyTorch DataLoaders."""
    train_files = discover_nc_files(nc_roots, years=train_years)
    val_files = discover_nc_files(nc_roots, years=val_years)

    train_ds = HMP155Dataset(train_files, corr_dir=corr_dir)
    val_ds = HMP155Dataset(val_files, corr_dir=corr_dir)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    return train_loader, val_loader
