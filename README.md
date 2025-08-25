# Zestaw eksperymentalny: WebP / AVIF / JPEG XL

Ten pakiet zawiera **gotowe skrypty** do przeprowadzenia badań porównawczych:
- przygotowanie zbioru (Unsplash → manifest → pliki „prepared”),
- kodowanie (WebP/AVIF/JPEG XL) z pomiarem czasu i RAM,
- liczenie metryk (PSNR-Y, SSIM-Y; opcjonalnie VMAF),
- agregacja wyników (CSV + wykresy RD / rate–complexity).

## Wymagania (Linux / WSL rekomendowane)
- Python 3.10+ oraz: `pip install -r requirements.txt`
- Narzędzia CLI: `cwebp`/`dwebp` (webp), `avifenc`/`avifdec` (libavif), `cjxl`/`djxl` (libjxl),
  `magick` lub `identify` (ImageMagick), `time` (/usr/bin/time -v). (Opcjonalnie: `ffmpeg` + libvmaf).


## Struktura katalogów
```
image_codec_experiment_kit/
  data/
    raw/           # tu wrzuć pliki (JPEG/PNG/TIFF)
    prepared/      # tu skrypt zapisze pliki po ujednoliceniu (PNG sRGB, parzyste wymiary)
  results/
    encodes/       # tu zapiszą się pliki wynikowe (webp/avif/jxl)
    csv/           # tu trafią logi i metryki (CSV)
    plots/         # tu trafią wykresy (PNG)
  scripts/         # skrypty .py oraz .sh
  manifest.csv     # manifest obrazów (uzupełnij lub wygeneruj 01_download_unsplash.py)
  config.yaml      # siatki jakości i ustawienia
```

## Minimalny przebieg
1. Przygotuj `manifest.csv`
2. Przygotuj dane: `python scripts/02_prepare_dataset.py`
3. Zakoduj: `bash scripts/03_encode.sh`
4. Metryki: `python scripts/04_metrics.py`
5. Agregacja + wykresy: `python scripts/05_aggregate.py`
