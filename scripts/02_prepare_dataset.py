#!/usr/bin/env bash
# SZYBKI, RÓWNOLEGŁY ENCODING: WebP / AVIF / JXL
set -euo pipefail

# parametry łatwe do zmiany 
THREADS_PER_CODEC=${THREADS_PER_CODEC:-4}        # wątki wewnątrz kodera (VM ma 4 vCPU)
MAX_PAR_JOBS=${MAX_PAR_JOBS:-$(nproc)}           # ile obrazów równolegle
JXL_Q="${JXL_Q:-30 50 70 90}"                    # poziomy jakości (na start 4)
AVIF_Q="${AVIF_Q:-28 36 44}"                     # 3 jakości ( możesz dodać np. 52 )
WEBP_Q="${WEBP_Q:-60 75 90}"                     # 3 jakości
AVIF_SPEED=${AVIF_SPEED:-8}                      # 8 = szybciej, 6 = wolniej/lepiej
JXL_EFFORT=${JXL_EFFORT:-3}                      # 3 = szybko, 7–9 = wolniej/lepiej
WEBP_METHOD=${WEBP_METHOD:-4}                    # 4 = szybko, 6 = wolniej/lepiej


BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IN_DIR="$BASE/data/prepared"
OUT_BASE="$BASE/results/encodes"
LOG_DIR="$BASE/results/csv"
mkdir -p "$OUT_BASE/jxl" "$OUT_BASE/avif" "$OUT_BASE/webp" "$LOG_DIR"

LOG="$LOG_DIR/encode_log.csv"
if [[ ! -s "$LOG" ]]; then
  echo "id,fmt,q,bytes,sec,user_sec,sys_sec,max_rss_kb" > "$LOG"
fi

encode_one() {
  local png="$1"
  local id base out sz t user sys rss
  base="$(basename "${png%.png}")"
  id="${base}"

  # JPEG XL 
  for q in $JXL_Q; do
    out="$OUT_BASE/jxl/${base}_q${q}.jxl"
    if [[ ! -s "$out" ]]; then
      /usr/bin/time -f "%e,%U,%S,%M" -o /tmp/t.$$.txt cjxl "$png" "$out" \
        -q "$q" -e "$JXL_EFFORT" --num_threads="$THREADS_PER_CODEC" --quiet >/dev/null
      IFS=, read -r t user sys rss < /tmp/t.$$.txt
      sz=$(stat -c%s "$out")
      echo "$id,JXL,$q,$sz,$t,$user,$sys,$rss" >> "$LOG"
      rm -f /tmp/t.$$.txt
    fi
  done

  # AVIF 
  for q in $AVIF_Q; do
    out="$OUT_BASE/avif/${base}_q${q}.avif"
    if [[ ! -s "$out" ]]; then
      /usr/bin/time -f "%e,%U,%S,%M" -o /tmp/t.$$.txt avifenc -y 420 -j "$THREADS_PER_CODEC" \
        -s "$AVIF_SPEED" -q "$q" "$png" "$out" >/dev/null
      IFS=, read -r t user sys rss < /tmp/t.$$.txt
      sz=$(stat -c%s "$out")
      echo "$id,AVIF,$q,$sz,$t,$user,$sys,$rss" >> "$LOG"
      rm -f /tmp/t.$$.txt
    fi
  done

  # WebP 
  for q in $WEBP_Q; do
    out="$OUT_BASE/webp/${base}_q${q}.webp"
    if [[ ! -s "$out" ]]; then
      /usr/bin/time -f "%e,%U,%S,%M" -o /tmp/t.$$.txt cwebp -q "$q" -m "$WEBP_METHOD" -mt \
        "$png" -o "$out" >/dev/null
      IFS=, read -r t user sys rss < /tmp/t.$$.txt
      sz=$(stat -c%s "$out")
      echo "$id,WebP,$q,$sz,$t,$user,$sys,$rss" >> "$LOG"
      rm -f /tmp/t.$$.txt
    fi
  done

  echo "✓ $id"
}

export -f encode_one
export OUT_BASE LOG THREADS_PER_CODEC AVIF_SPEED JXL_EFFORT WEBP_METHOD JXL_Q AVIF_Q WEBP_Q

mapfile -t PNGS < <(ls "$IN_DIR"/img*.png)

# limiter równoległości 
running=0
for png in "${PNGS[@]}"; do
  encode_one "$png" &
  running=$((running+1))
  while [[ $running -ge $MAX_PAR_JOBS ]]; do
    wait -n
    running=$((running-1))
  done
done
wait
echo "DONE."
