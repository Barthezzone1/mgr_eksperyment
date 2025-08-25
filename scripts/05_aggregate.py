#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Agreguje wyniki i tworzy wykresy RD / rate–complexity.

import pathlib
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # bezpieczny backend do generowania plików PNG bez ekranu
import matplotlib.pyplot as plt

BASE = pathlib.Path(__file__).resolve().parents[1]
CSV = BASE / "results" / "csv"
PLOTS = BASE / "results" / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)

rd_path = CSV / "rd.csv"
if not rd_path.exists():
    raise SystemExit(f"Brak pliku z danymi: {rd_path}")

# wczytanie i przygotowanie danych
df = pd.read_csv(rd_path)

# upewniamy się, że kolumny metryk są liczbowe
for col in ["psnr_y", "ssim_y", "bpp"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

has_wall = "wall_s" in df.columns
if has_wall:
    df["wall_s"] = pd.to_numeric(df["wall_s"], errors="coerce")

# grupowanie: średnia dla jakości metryk, mediana dla czasu (jeśli jest)
agg = {"psnr_y": "mean", "ssim_y": "mean", "bpp": "mean"}
if has_wall:
    agg["wall_s"] = "median"

grp = df.groupby(["encoder", "quality"], as_index=False).agg(agg)
grp.to_csv(CSV / "rd_aggregated.csv", index=False)

# ustalona kolejność enkoderów na wykresach
encoders = ["webp", "avif", "jxl"]

#  Wykresy RD
for metric, ylabel in [("psnr_y", "PSNR-Y [dB]"), ("ssim_y", "SSIM-Y")]:
    plt.figure(figsize=(6, 4))
    for enc in encoders:
        sub = grp[grp.encoder == enc].sort_values("bpp")
        if not sub.empty:
            plt.plot(sub["bpp"], sub[metric], marker="o", label=enc.upper())
    plt.xlabel("Bitów na piksel (bpp)")
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / f"rd_{metric}.png", dpi=150)
    plt.close()

# Wykres rate–complexity (jeśli mamy czasy)
if has_wall:
    plt.figure(figsize=(6, 4))
    for enc in encoders:
        sub = grp[grp.encoder == enc].sort_values("bpp")
        if not sub.empty and "wall_s" in sub.columns:
            plt.plot(sub["bpp"], sub["wall_s"], marker="o", label=enc.upper())
    plt.xlabel("Bitów na piksel (bpp)")
    plt.ylabel("Czas kodowania [s] (mediana)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS / "rate_complexity.png", dpi=150)
    plt.close()
