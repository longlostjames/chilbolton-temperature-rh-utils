"""Training script for 1D U-Net sequence segmentation on HMP155 NetCDF data.

Trains the UNet1D model using weighted Cross-Entropy Loss to handle class imbalance
(Normal=0, Purge=1, Recovery=2, Ignored/Bad=-100).
"""

import argparse
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau

from chilbolton_temperature_rh_utils.ml.dataset import create_data_loaders
from chilbolton_temperature_rh_utils.ml.model import UNet1D


def calculate_class_weights(
    train_loader: torch.utils.data.DataLoader,
    num_classes: int = 3,
    ignore_index: int = -100,
) -> torch.Tensor:
    """Compute inverse class frequency weights from training data."""
    counts = torch.zeros(num_classes, dtype=torch.long)
    for _, y, _ in train_loader:
        for c in range(num_classes):
            counts[c] += (y == c).sum()

    total = counts.sum().float()
    if total == 0:
        return torch.ones(num_classes)

    # Inverse frequency weighting with smoothing
    weights = total / (num_classes * counts.float() + 1e-5)
    # Normalize weights so mean weight is 1.0
    weights = weights / weights.mean()
    return weights


def train_one_epoch(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> float:
    """Train for one epoch and return average training loss."""
    model.train()
    running_loss = 0.0
    num_batches = 0

    for x, y, _ in dataloader:
        x, y = x.to(device), y.to(device)

        optimizer.zero_grad()
        logits = model(x)  # (Batch, num_classes, Sequence_Length)

        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        num_batches += 1

    return running_loss / max(1, num_batches)


@torch.no_grad()
def validate(
    model: nn.Module,
    dataloader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device,
    num_classes: int = 3,
    ignore_index: int = -100,
) -> tuple[float, dict]:
    """Evaluate model performance on validation set.

    Returns:
        val_loss: Average validation loss.
        metrics: Dict containing per-class Intersection-Over-Union (IoU) scores.
    """
    model.eval()
    running_loss = 0.0
    num_batches = 0

    intersection = torch.zeros(num_classes, device=device)
    union = torch.zeros(num_classes, device=device)

    for x, y, _ in dataloader:
        x, y = x.to(device), y.to(device)

        logits = model(x)
        loss = criterion(logits, y)
        running_loss += loss.item()
        num_batches += 1

        # Predictions: argmax over class dimension
        preds = torch.argmax(logits, dim=1)  # (Batch, Sequence_Length)

        # Calculate IoU per class
        valid_mask = (y != ignore_index)
        for c in range(num_classes):
            c_pred = (preds == c) & valid_mask
            c_target = (y == c) & valid_mask

            intersection[c] += (c_pred & c_target).sum()
            union[c] += (c_pred | c_target).sum()

    val_loss = running_loss / max(1, num_batches)
    iou = (intersection / (union + 1e-5)).cpu().numpy()

    metrics = {
        "iou_good": float(iou[0]),
        "iou_purge": float(iou[1]),
        "iou_recovery": float(iou[2]),
        "mean_iou": float(iou.mean()),
    }

    return val_loss, metrics


def train_model(
    nc_roots: list,
    corr_dir: str,
    output_dir: str,
    train_years: list[int],
    val_years: list[int],
    epochs: int = 30,
    batch_size: int = 4,
    lr: float = 1e-3,
    base_filters: int = 32,
    seed: int = 42,
    model_name: str = "unet1d_best.pt",
    device_name: str = "auto",
):
    """Main training routine."""
    # Set random seeds for reproducibility
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Determine device (CPU vs CUDA)
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)

    print(f"Using device: {device} | Seed: {seed}")
    print(f"Training years: {train_years} | Validation years: {val_years}")

    # Build DataLoaders
    train_loader, val_loader = create_data_loaders(
        nc_roots=nc_roots,
        corr_dir=corr_dir,
        train_years=train_years,
        val_years=val_years,
        batch_size=batch_size,
    )

    print(f"Loaded {len(train_loader.dataset)} training days and {len(val_loader.dataset)} validation days.")

    if len(train_loader.dataset) == 0:
        print("Error: No training files found.", file=sys.stderr)
        sys.exit(1)

    # Compute class weights to address heavy class imbalance (Good vs Purge vs Recovery)
    print("Computing class weights from training dataset...")
    class_weights = calculate_class_weights(train_loader).to(device)
    print(f"Class weights -> Good: {class_weights[0]:.2f}, Purge: {class_weights[1]:.2f}, Recovery: {class_weights[2]:.2f}")

    # Model, Loss, Optimizer, Scheduler
    model = UNet1D(in_channels=4, num_classes=3, base_filters=base_filters).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights, ignore_index=-100)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=3)

    best_val_loss = float("inf")
    best_model_path = out_path / model_name

    print("\nStarting training loop...")
    for epoch in range(1, epochs + 1):
        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, metrics = validate(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} | "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_loss:.4f} | "
            f"Purge IoU: {metrics['iou_purge']:.3f} | "
            f"Recovery IoU: {metrics['iou_recovery']:.3f} | "
            f"mIoU: {metrics['mean_iou']:.3f}"
        )

        # Checkpoint best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": val_loss,
                    "metrics": metrics,
                    "class_weights": class_weights.cpu(),
                },
                best_model_path,
            )
            print(f"  --> Saved new best model to {best_model_path}")

    print(f"\nTraining complete. Best validation loss: {best_val_loss:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Train 1D U-Net for HMP155 purge & recovery detection.")
    parser.add_argument("--nc-roots", nargs="+", required=True,
                        help="Data root directories containing NetCDF year subfolders")
    parser.add_argument("--corr-dir", default="corrections",
                        help="Base directory of .corr ground truth files (default: corrections)")
    parser.add_argument("--output-dir", default="checkpoints",
                        help="Directory to save model checkpoints (default: checkpoints)")
    parser.add_argument("--train-years", nargs="+", type=int, default=[2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023],
                        help="Years to use for training (default: 2015-2023)")
    parser.add_argument("--val-years", nargs="+", type=int, default=[2024],
                        help="Years to use for validation (default: 2024)")
    parser.add_argument("--epochs", type=int, default=30, help="Number of training epochs (default: 30)")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size (default: 4)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate (default: 0.001)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--model-name", default="unet1d_best.pt", help="Output checkpoint filename (default: unet1d_best.pt)")
    parser.add_argument("--device", default="auto", help="Device: 'auto', 'cpu', or 'cuda'")

    args = parser.parse_args()
    train_model(
        nc_roots=args.nc_roots,
        corr_dir=args.corr_dir,
        output_dir=args.output_dir,
        train_years=args.train_years,
        val_years=args.val_years,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        model_name=args.model_name,
        device_name=args.device,
    )


if __name__ == "__main__":
    main()
