#!/usr/bin/env python3
# 04_metrics.py
# PSNR-Y i SSIM-Y liczone na luminancji BT.709 po linearizacji sRGB
# Wersja z resume + równoległością zapisu CSV

import pathlib, subprocess, csv, math, os, tempfile
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter
import warnings
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None                      # wyłącza limit
warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
ImageFile.LOAD_TRUNCATED_IMAGES = True             

BASE = pathlib.Path(__file__).resolve().parents[1]
PREP = BASE/"data/prepared"
OUT  = BASE/"results/encodes"
CSV_DIR  = BASE/"results/csv"; CSV_DIR.mkdir(parents=True, exist_ok=True)

def load_png(p: pathlib.Path):
    return np.array(Image.open(p).convert("RGB"), dtype=np.uint8)

def srgb_to_linear(x_uint8):
    x = x_uint8.astype(np.float32) / 255.0
    a = 0.055
    return np.where(x <= 0.04045, x/12.92, ((x + a)/(1 + a))**2.4)

def luma709_linear(rgb):
    r = srgb_to_linear(rgb[:, :, 0])
    g = srgb_to_linear(rgb[:, :, 1])
    b = srgb_to_linear(rgb[:, :, 2])
    return 0.2126*r + 0.7152*g + 0.0722*b  # BT.709

def PSNR_Y(ref_rgb, dec_rgb):
    yr = luma709_linear(ref_rgb)
    yd = luma709_linear(dec_rgb)
    mse = np.mean((yr - yd)**2)
    return 999.0 if mse == 0 else 10.0 * math.log10(1.0 / mse)  # peak=1.0

def SSIM_Y(ref_rgb, dec_rgb):
    # SSIM liczony na luminancji w skali 0..255 (uint8) dla stabilności
    yr = (luma709_linear(ref_rgb) * 255.0).astype(np.uint8)
    yd = (luma709_linear(dec_rgb) * 255.0).astype(np.uint8)
    return ssim(yr, yd, data_range=255)

def dec2png(inp: pathlib.Path, outp: pathlib.Path) -> bool:
    ext = inp.suffix.lower()
    if ext == ".webp":
        cmd = ["dwebp", str(inp), "-o", str(outp)]
    elif ext == ".avif":
        cmd = ["avifdec", str(inp), str(outp)]
    elif ext == ".jxl":
        cmd = ["djxl", str(inp), str(outp)]
    else:
        return False
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0

#  Resume: wczytaj istniejące metrics.csv (jeśli jest) 
metrics_path = CSV_DIR/"metrics.csv"
done = set()
resume = metrics_path.exists()

if resume:
    try:
        with open(metrics_path, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                try:
                    done.add((row["encoder"], int(row["quality"]), row["img_id"]))
                except Exception:
                    # pomiń uszkodzone wiersze, jeśli jakieś są
                    pass
    except Exception:
        # jeśli nie da się odczytać, traktuj jak brak resume
        resume = False
        done = set()

print(f"[INFO] Resume: {'TAK' if resume else 'NIE'}; wierszy już policzonych: {len(done)}")

# Zbierz zadania 
encoders = ["webp", "avif", "jxl"]
jobs = []
for enc in encoders:
    for fp in sorted((OUT/enc).glob("*.*")):
        stem = fp.stem
        if "_q" not in stem:
            continue
        img_id, q = stem.split("_q")
        key = (enc, int(q), img_id)
        if key in done:
            continue
        jobs.append((enc, str(fp), img_id, int(q)))

todo_per_enc = Counter(j[0] for j in jobs)
for enc in encoders:
    if todo_per_enc[enc]:
        print(f"[INFO] {enc.upper()}: {todo_per_enc[enc]} plików do przeliczenia…")

if not jobs and resume:
    print("[INFO] Nic do zrobienia — metrics.csv jest kompletny.")
    # mimo wszystko spróbuj zbudować rd.csv
    enc_log = CSV_DIR/"encode_log.csv"
    if enc_log.exists():
        try:
            import pandas as pd
            dfm = pd.read_csv(metrics_path)
            dfe = pd.read_csv(enc_log)
            df = pd.merge(dfm, dfe, on=["encoder", "quality", "img_id"], how="left")
            df.to_csv(CSV_DIR/"rd.csv", index=False)
            print("OK:", CSV_DIR/"rd.csv")
        except Exception as e:
            print("[WARN] Nie udało się zbudować rd.csv:", e)
    raise SystemExit(0)

# Funkcja robocza (dla procesów) 
def compute_one(enc: str, fp_str: str, img_id: str, q: int):
    fp = pathlib.Path(fp_str)
    # unikatowy plik tymczasowy, usuwany w finally
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as t:
        tmp_png = pathlib.Path(t.name)
    try:
        if not dec2png(fp, tmp_png):
            return ("ERR", enc, q, img_id, f"decode_failed:{fp.name}")
        ref = load_png(PREP/f"{img_id}.png")
        dec = load_png(tmp_png)
        h, w, _ = ref.shape
        bpp = (8.0 * fp.stat().st_size) / (w * h)
        row = [enc, q, img_id,
               f"{PSNR_Y(ref, dec):.4f}",
               f"{SSIM_Y(ref, dec):.6f}",
               f"{bpp:.6f}"]
        return ("OK", row)
    except Exception as e:
        return ("ERR", enc, q, img_id, f"{type(e).__name__}:{e}")
    finally:
        try:
            tmp_png.unlink(missing_ok=True)
        except Exception:
            pass

# Uruchom równolegle i zapisuj w głównym procesie
workers = 1 #max(1, min(4, (os.cpu_count() or 2) - 1))
print(f"[INFO] Równoległość: {workers} workerów")

mode = "a" if resume else "w"
with open(metrics_path, mode, newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if not resume:
        w.writerow(["encoder", "quality", "img_id", "psnr_y", "ssim_y", "bpp"])

    done_counts = Counter()
    futures = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for enc, fp, img_id, q in jobs:
            futures.append(ex.submit(compute_one, enc, fp, img_id, q))

        for i, fut in enumerate(as_completed(futures), 1):
            status = fut.result()
            if status is None:
                continue
            if status[0] == "OK":
                row = status[1]
                w.writerow(row)
                f.flush()
                done_counts[row[0]] += 1  # enc
            else:
                _, enc, q, img_id, err = status
                print(f"[WARN] {enc.upper()} {img_id}_q{q}: {err}")

            if i % 25 == 0 or i == len(futures):
                total_rows = sum(done_counts.values())
                print(f"[PROGRESS] {total_rows}/{len(futures)} OK (łącznie wierszy: {len(done)+total_rows})")

print("OK:", metrics_path)

# Zbuduj rd.csv jeśli mamy encode_log.csv 
enc_log = CSV_DIR/"encode_log.csv"
if enc_log.exists():
    try:
        import pandas as pd
        dfm = pd.read_csv(metrics_path)
        dfe = pd.read_csv(enc_log)
        df = pd.merge(dfm, dfe, on=["encoder", "quality", "img_id"], how="left")
        df.to_csv(CSV_DIR/"rd.csv", index=False)
        print("OK:", CSV_DIR/"rd.csv")
    except Exception as e:
        print("[WARN] Nie udało się zbudować rd.csv:", e)
