"""Inference and post-processing script for 1D U-Net HMP155 purge & recovery detection.

Loads a trained UNet1D model checkpoint, runs predictions on unflagged NetCDF files,
cleans predicted sample labels using domain post-processing rules, and writes
the detected intervals to .corr files.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
import xarray as xr

from chilbolton_temperature_rh_utils.apply_corr_files import apply_corr_to_file
from chilbolton_temperature_rh_utils.ml.dataset import (
    DEFAULT_RH_MEAN,
    DEFAULT_RH_STD,
    DEFAULT_TEMP_MEAN,
    DEFAULT_TEMP_STD,
    TARGET_SEQUENCE_LENGTH,
    extract_date_from_filename,
)
from chilbolton_temperature_rh_utils.ml.model import UNet1D
from chilbolton_temperature_rh_utils.qc_corrections import (
    FLAG_PURGE,
    FLAG_RECOVERY,
    load_corr_intervals,
    save_corr_intervals,
)


def extract_contiguous_runs(mask: np.ndarray) -> List[Tuple[int, int]]:
    """Return list of (start_idx, end_idx) tuples for contiguous True regions in a boolean array."""
    if not np.any(mask):
        return []
    
    indices = np.flatnonzero(mask)
    runs = []
    start = previous = int(indices[0])
    
    for idx in indices[1:]:
        idx = int(idx)
        if idx != previous + 1:
            runs.append((start, previous))
            start = idx
        previous = idx
    runs.append((start, previous))
    return runs


def postprocess_predictions(
    probs: np.ndarray,
    rh_values: np.ndarray,
    min_purge_samples: int = 30,      # ~5 mins at 10-sec sampling
    max_purge_samples: int = 90,      # ~15 mins at 10-sec sampling
    recovery_samples: int = 36,       # ~6 mins at 10-sec sampling
    purge_thresh: float = 0.35,
    max_rh_std: float = 0.25,         # %RH standard deviation ceiling inside a purge
    max_purges_per_day: int = 2,
) -> Tuple[List[Tuple[int, int, int]], List[Tuple[int, int, int]]]:
    """Convert class probabilities and RH flatness into domain-constrained interval lists.

    Enforces physical HMP155 domain constraints:
      1. Purge events last between 5 and 15 minutes (30 to 90 samples at 10s sampling).
      2. Relative humidity during a purge must be nearly flat (low standard deviation).
      3. At most max_purges_per_day (default 2) events are selected per day.
      4. Recovery (flag 4) is fixed for ~6 minutes (36 samples) immediately following each valid purge.
    """
    num_points = probs.shape[1]
    
    # Identify sample regions with elevated purge probability
    purge_prob = probs[1]
    purge_mask = purge_prob >= purge_thresh

    raw_runs = extract_contiguous_runs(purge_mask)
    candidates = []

    for start, end in raw_runs:
        run_len = end - start + 1
        
        # If run is too long (e.g. over 15 mins), search for the flattest sub-window of ~9 minutes
        if run_len > max_purge_samples:
            target_len = 54  # 9 minutes
            best_sub_start = start
            min_std = float("inf")
            for sub_s in range(start, end - target_len + 1):
                sub_e = sub_s + target_len
                sub_std = np.std(rh_values[sub_s:sub_e])
                if sub_std < min_std:
                    min_std = sub_std
                    best_sub_start = sub_s
            start, end = best_sub_start, best_sub_start + target_len - 1
            run_len = end - start + 1

        if run_len < min_purge_samples:
            continue

        # Evaluate RH standard deviation in the candidate window
        rh_window_std = np.std(rh_values[start:end+1])
        if rh_window_std > max_rh_std:
            continue  # Reject non-flat diurnal variations

        mean_prob = float(np.mean(purge_prob[start:end+1]))
        score = mean_prob / (rh_window_std + 1e-3)
        candidates.append((start, end, score))

    # Sort candidates by score descending and take top non-overlapping max_purges_per_day
    candidates.sort(key=lambda x: x[2], reverse=True)
    selected_purges = []

    for c_start, c_end, _ in candidates:
        if len(selected_purges) >= max_purges_per_day:
            break
        # Ensure no overlap with previously selected purges
        overlap = False
        for s_start, s_end in selected_purges:
            if not (c_end < s_start or c_start > s_end):
                overlap = True
                break
        if not overlap:
            selected_purges.append((c_start, c_end))

    selected_purges.sort(key=lambda x: x[0])

    temp_intervals = []
    rh_intervals = []

    for p_start, p_end in selected_purges:
        # Purge (flag 3) for both variables
        temp_intervals.append((p_start, p_end, FLAG_PURGE))
        rh_intervals.append((p_start, p_end, FLAG_PURGE))

        # Recovery (flag 4) for RH immediately following purge
        r_start = p_end + 1
        r_end = min(num_points - 1, r_start + recovery_samples - 1)
        if r_start < num_points and r_end >= r_start:
            rh_intervals.append((r_start, r_end, FLAG_RECOVERY))

    return temp_intervals, rh_intervals


def predict_file(
    models: Union[torch.nn.Module, List[torch.nn.Module]],
    nc_path: Path,
    device: torch.device,
    temp_mean: float = DEFAULT_TEMP_MEAN,
    temp_std: float = DEFAULT_TEMP_STD,
    rh_mean: float = DEFAULT_RH_MEAN,
    rh_std: float = DEFAULT_RH_STD,
    min_purge_samples: int = 30,
    max_purge_samples: int = 90,
    max_purges_per_day: int = 2,
) -> Tuple[datetime, List[Tuple[int, int, int]], List[Tuple[int, int, int]]]:
    """Run single model or ensemble of UNet1D models on a NetCDF file and return predicted intervals."""
    if not isinstance(models, list):
        models = [models]

    with xr.open_dataset(nc_path) as ds:
        num_points = ds.sizes.get("time", 0)
        if num_points == 0:
            raise ValueError(f"{nc_path} has 0 time samples.")

        date = extract_date_from_filename(nc_path)
        if date is None and "time" in ds:
            date = pd.to_datetime(ds["time"].values[0]).date()

        temp = ds["air_temperature"].values.copy()
        if ds["air_temperature"].attrs.get("units", "").upper() in ("K", "KELVIN") or np.mean(temp) > 200:
            temp -= 273.15

        rh = ds["relative_humidity"].values.copy()

    # Normalize basic features
    temp_norm = (temp - temp_mean) / temp_std
    rh_norm = (rh - rh_mean) / rh_std

    # Compute derivative and rolling variability features
    rh_diff = np.diff(rh, prepend=rh[0])
    rh_series = pd.Series(rh)
    rh_rstd = rh_series.rolling(30, center=True, min_periods=1).std().fillna(0).to_numpy() / 2.0

    # Prepare 4-channel input tensor: (1, 4, N)
    x = torch.tensor(
        np.stack([temp_norm, rh_norm, rh_diff, rh_rstd], axis=0),
        dtype=torch.float32,
    ).unsqueeze(0)
    
    if num_points != TARGET_SEQUENCE_LENGTH:
        x = F.interpolate(x, size=TARGET_SEQUENCE_LENGTH, mode="linear", align_corners=False)

    x = x.to(device)

    # Forward pass across ensemble models
    all_probs = []
    with torch.no_grad():
        for model in models:
            logits = model(x)  # (1, 3, TARGET_SEQUENCE_LENGTH)
            probs_k = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()  # (3, TARGET_SEQUENCE_LENGTH)
            all_probs.append(probs_k)

    # Soft voting: average predicted probabilities across ensemble
    probs = np.mean(all_probs, axis=0)

    # Post-process probabilities into intervals
    temp_intervals, rh_intervals = postprocess_predictions(
        probs,
        rh_values=rh,
        min_purge_samples=min_purge_samples,
        max_purge_samples=max_purge_samples,
        max_purges_per_day=max_purges_per_day,
    )

    # If sequence was resampled, map index ranges back to original num_points scale
    if num_points != TARGET_SEQUENCE_LENGTH:
        scale = num_points / float(TARGET_SEQUENCE_LENGTH)
        def _remap(intervals):
            return [
                (min(num_points - 1, int(round(start * scale))),
                 min(num_points - 1, int(round(end * scale))),
                 flag)
                for start, end, flag in intervals
            ]
        temp_intervals = _remap(temp_intervals)
        rh_intervals = _remap(rh_intervals)

    return date, temp_intervals, rh_intervals


def run_inference(
    checkpoint_path: Union[str, Path, List[Union[str, Path]]],
    nc_files: List[Path],
    corr_dir: str,
    apply_to_nc: bool = False,
    min_purge_samples: int = 30,
    max_purge_samples: int = 90,
    max_purges_per_day: int = 2,
    device_name: str = "auto",
):
    """Run inference across a list of NetCDF files, write .corr files, and optionally apply to NetCDF."""
    if isinstance(checkpoint_path, (str, Path)):
        ckpt_paths = [Path(checkpoint_path)]
    else:
        ckpt_paths = [Path(p) for p in checkpoint_path]

    device = torch.device("cuda" if (device_name == "auto" and torch.cuda.is_available()) else ("cpu" if device_name == "auto" else device_name))
    
    models = []
    for ckpt_p in ckpt_paths:
        if not ckpt_p.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {ckpt_p}")
        print(f"Loading checkpoint {ckpt_p} on device {device}...")
        checkpoint = torch.load(ckpt_p, map_location=device)
        model = UNet1D(in_channels=4, num_classes=3, base_filters=32).to(device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        models.append(model)

    print(f"Running ensemble of {len(models)} model(s) across {len(nc_files)} NetCDF file(s)...")

    saved_corr_files = set()
    for nc_file in nc_files:
        try:
            date, temp_intervals, rh_intervals = predict_file(
                models=models,
                nc_path=nc_file,
                device=device,
                min_purge_samples=min_purge_samples,
                max_purge_samples=max_purge_samples,
                max_purges_per_day=max_purges_per_day,
            )

            # Preserve existing bad data intervals (flag 2) from existing .corr file if present
            existing_temp = load_corr_intervals(corr_dir, "temperature", date)
            existing_rh = load_corr_intervals(corr_dir, "rh", date)
            bad_temp = [i for i in existing_temp if i[2] == 2]
            bad_rh = [i for i in existing_rh if i[2] == 2]

            final_temp = sorted(set(bad_temp + temp_intervals))
            final_rh = sorted(set(bad_rh + rh_intervals))

            # Save to monthly .corr files
            temp_corr = save_corr_intervals(corr_dir, "temperature", date, final_temp)
            rh_corr = save_corr_intervals(corr_dir, "rh", date, final_rh)

            saved_corr_files.add(temp_corr)
            saved_corr_files.add(rh_corr)

            print(f"  {date.isoformat()}: Detected {len(temp_intervals)} temp interval(s), {len(rh_intervals)} RH interval(s)")

            if apply_to_nc:
                apply_corr_to_file(nc_file, corr_dir, date)
                print(f"    --> Applied flags directly to {nc_file.name}")

        except Exception as e:
            print(f"Error processing {nc_file}: {e}", file=sys.stderr)

    print(f"\nInference complete. Updated {len(saved_corr_files)} .corr file(s).")


def main():
    parser = argparse.ArgumentParser(description="Run 1D U-Net inference for HMP155 purge & recovery detection.")
    parser.add_argument("--checkpoint", nargs="+", default=["checkpoints/unet1d_best.pt"],
                        help="Path(s) to trained model checkpoint(s) (default: checkpoints/unet1d_best.pt)")
    parser.add_argument("-i", "--input", nargs="+", required=True,
                        help="NetCDF input files or directories")
    parser.add_argument("-c", "--corr-dir", default="corrections",
                        help="Base directory to save .corr files (default: corrections)")
    parser.add_argument("--apply-to-nc", action="store_true",
                        help="Apply predicted .corr flags directly to NetCDF files")
    parser.add_argument("--min-purge-samples", type=int, default=30,
                        help="Minimum contiguous samples for Purge interval (default: 30)")
    parser.add_argument("--max-purge-samples", type=int, default=90,
                        help="Maximum contiguous samples for Purge interval (default: 90)")
    parser.add_argument("--max-purges-per-day", type=int, default=2,
                        help="Maximum purge periods permitted per day (default: 2)")
    parser.add_argument("--device", default="auto", help="Device: 'auto', 'cpu', or 'cuda'")

    args = parser.parse_args()

    # Expand inputs into list of .nc file paths
    nc_files = []
    for inp in args.input:
        p = Path(inp)
        if p.is_file() and p.suffix == ".nc":
            nc_files.append(p)
        elif p.is_dir():
            nc_files.extend(sorted(p.glob("**/*.nc")))

    nc_files = sorted(set(nc_files))
    if not nc_files:
        print("No NetCDF files found for input.", file=sys.stderr)
        sys.exit(1)

    run_inference(
        checkpoint_path=args.checkpoint,
        nc_files=nc_files,
        corr_dir=args.corr_dir,
        apply_to_nc=args.apply_to_nc,
        min_purge_samples=args.min_purge_samples,
        max_purge_samples=args.max_purge_samples,
        max_purges_per_day=args.max_purges_per_day,
        device_name=args.device,
    )


if __name__ == "__main__":
    main()
