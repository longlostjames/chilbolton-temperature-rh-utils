"""1D U-Net Architecture for automated sequence segmentation of HMP155 time series data.

Classifies each 10-second sample into:
  0: Normal / Good data
  1: Purge period (flag 3)
  2: Recovery period (flag 4)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock1D(nn.Module):
    """Two-layer 1D Convolutional block with Batch Normalization and ReLU activations."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 7):
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=kernel_size, padding=padding),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv1d(out_channels, out_channels, kernel_size=kernel_size, padding=padding),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UNet1D(nn.Module):
    """1D U-Net sequence segmentation model.

    Input shape:  (Batch, in_channels, Sequence_Length)  e.g., (B, 4, 8640)
    Output shape: (Batch, num_classes, Sequence_Length)  e.g., (B, 3, 8640)
    """

    def __init__(self, in_channels: int = 4, num_classes: int = 3, base_filters: int = 32):
        """
        Args:
            in_channels: Number of input feature channels (default: 2 -> Temp, RH).
            num_classes: Number of target segmentation classes (default: 3 -> Good, Purge, Recovery).
            base_filters: Initial channel count for the first encoder stage (default: 32).
        """
        super().__init__()
        f = base_filters

        # Encoder (Contracting Path)
        self.enc1 = ConvBlock1D(in_channels, f)
        self.pool1 = nn.MaxPool1d(kernel_size=2, stride=2)

        self.enc2 = ConvBlock1D(f, f * 2)
        self.pool2 = nn.MaxPool1d(kernel_size=2, stride=2)

        self.enc3 = ConvBlock1D(f * 2, f * 4)
        self.pool3 = nn.MaxPool1d(kernel_size=2, stride=2)

        # Bottleneck
        self.bottleneck = ConvBlock1D(f * 4, f * 8)

        # Decoder (Expanding Path)
        self.up3 = nn.ConvTranspose1d(f * 8, f * 4, kernel_size=2, stride=2)
        self.dec3 = ConvBlock1D(f * 8, f * 4)

        self.up2 = nn.ConvTranspose1d(f * 4, f * 2, kernel_size=2, stride=2)
        self.dec2 = ConvBlock1D(f * 4, f * 2)

        self.up1 = nn.ConvTranspose1d(f * 2, f, kernel_size=2, stride=2)
        self.dec1 = ConvBlock1D(f * 2, f)

        # Output classification head
        self.classifier = nn.Conv1d(f, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        e3 = self.enc3(self.pool2(e2))

        # Bottleneck
        b = self.bottleneck(self.pool3(e3))

        # Decoder with skip connections (matching temporal shapes if needed)
        u3 = self.up3(b)
        if u3.shape[-1] != e3.shape[-1]:
            u3 = F.interpolate(u3, size=e3.shape[-1], mode="nearest")
        d3 = self.dec3(torch.cat([u3, e3], dim=1))

        u2 = self.up2(d3)
        if u2.shape[-1] != e2.shape[-1]:
            u2 = F.interpolate(u2, size=e2.shape[-1], mode="nearest")
        d2 = self.dec2(torch.cat([u2, e2], dim=1))

        u1 = self.up1(d2)
        if u1.shape[-1] != e1.shape[-1]:
            u1 = F.interpolate(u1, size=e1.shape[-1], mode="nearest")
        d1 = self.dec1(torch.cat([u1, e1], dim=1))

        # Class logits per sample
        return self.classifier(d1)
