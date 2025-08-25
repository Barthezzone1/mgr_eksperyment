#!/usr/bin/env bash
set -euo pipefail
BASE="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. && pwd )"
PREP="$BASE/data/prepared"
OUT="$BASE/results/encodes"
CSV="$BASE/results/csv"

mkdir -p "$OUT/webp" "$OUT/avif" "$OUT/jxl" "$CSV"

LOG="$CSV/encode_log.csv"
# nie nadpisuj logu przy wznowieniach
if [[ ! -s "$LOG" ]]; then
  echo "encoder,quality,img_id,bytes,wall_s,user_s,sys_s,max_rss_kb" > "$LOG"
fi

# siatka jakości 
webp_q=(60 75 90)
avif_q=(28 36 44)
jxl_q=(30 50 70 90)

for inpng in "$PREP"/*.png; do
  id="$(basename "$inpng" .png)"
  echo "== $id =="

  # WEBP (lossy) – szybciej: -m 4, wątki: -mt
  for q in "${webp_q[@]}"; do
    out="$OUT/webp/${id}_q${q}.webp"
    if [[ -s "$out" ]]; then echo "skip webp q$q"; continue; fi
    /usr/bin/time -v bash -c "cwebp -q $q -mt -m 4 \"$inpng\" -o \"$out\"" \
      2>tmp.log 1>/dev/null || true
    bytes=$(stat -c%s "$out")
    wall=$(grep 'Elapsed (wall clock) time' tmp.log | awk -F': ' '{print $2}')
    user=$(grep 'User time (seconds)' tmp.log | awk -F': ' '{print $2}')
    sys=$(grep 'System time (seconds)' tmp.log | awk -F': ' '{print $2}')
    rss=$(grep 'Maximum resident set size (kbytes)' tmp.log | awk -F': ' '{print $2}')
    python3 - "$wall" "$user" "$sys" "$rss" "$bytes" "$q" "$id" <<'PY' >> "$LOG"
import sys
def to_s(s):
    p=[float(x) for x in s.split(':')]
    return p[0]*3600+p[1]*60+p[2] if len(p)==3 else (p[0]*60+p[1] if len(p)==2 else p[0])
wall,user,sys_t,rss,bytes_,q,img_id=sys.argv[1:8]
print(f"webp,{q},{img_id},{bytes_},{to_s(wall):.3f},{float(user):.3f},{float(sys_t):.3f},{rss}")
PY
  done

  # AVIF – szybciej: -s 8, wątki: -j 4, 4:2:0: -y 420
  for q in "${avif_q[@]}"; do
    out="$OUT/avif/${id}_q${q}.avif"
    if [[ -s "$out" ]]; then echo "skip avif q$q"; continue; fi
    /usr/bin/time -v bash -c "avifenc -q $q -s 8 -j 4 -y 420 \"$inpng\" \"$out\"" \
      2>tmp.log 1>/dev/null || true
    bytes=$(stat -c%s "$out")
    wall=$(grep 'Elapsed (wall clock) time' tmp.log | awk -F': ' '{print $2}')
    user=$(grep 'User time (seconds)' tmp.log | awk -F': ' '{print $2}')
    sys=$(grep 'System time (seconds)' tmp.log | awk -F': ' '{print $2}')
    rss=$(grep 'Maximum resident set size (kbytes)' tmp.log | awk -F': ' '{print $2}')
    python3 - "$wall" "$user" "$sys" "$rss" "$bytes" "$q" "$id" <<'PY' >> "$LOG"
import sys
def to_s(s):
    p=[float(x) for x in s.split(':')]
    return p[0]*3600+p[1]*60+p[2] if len(p)==3 else (p[0]*60+p[1] if len(p)==2 else p[0])
wall,user,sys_t,rss,bytes_,q,img_id=sys.argv[1:8]
print(f"avif,{q},{img_id},{bytes_},{to_s(wall):.3f},{float(user):.3f},{float(sys_t):.3f},{rss}")
PY
  done

  # JPEG XL – szybciej: -e 3, wątki: --num_threads=4
  for q in "${jxl_q[@]}"; do
    out="$OUT/jxl/${id}_q${q}.jxl"
    if [[ -s "$out" ]]; then echo "skip jxl q$q"; continue; fi
    /usr/bin/time -v bash -c "cjxl \"$inpng\" \"$out\" -q $q -e 3 --num_threads=4" \
      2>tmp.log 1>/dev/null || true
    bytes=$(stat -c%s "$out")
    wall=$(grep 'Elapsed (wall clock) time' tmp.log | awk -F': ' '{print $2}')
    user=$(grep 'User time (seconds)' tmp.log | awk -F': ' '{print $2}')
    sys=$(grep 'System time (seconds)' tmp.log | awk -F': ' '{print $2}')
    rss=$(grep 'Maximum resident set size (kbytes)' tmp.log | awk -F': ' '{print $2}')
    python3 - "$wall" "$user" "$sys" "$rss" "$bytes" "$q" "$id" <<'PY' >> "$LOG"
import sys
def to_s(s):
    p=[float(x) for x in s.split(':')]
    return p[0]*3600+p[1]*60+p[2] if len(p)==3 else (p[0]*60+p[1] if len(p)==2 else p[0])
wall,user,sys_t,rss,bytes_,q,img_id=sys.argv[1:8]
print(f"jxl,{q},{img_id},{bytes_},{to_s(wall):.3f},{float(user):.3f},{float(sys_t):.3f},{rss}")
PY
  done

done
rm -f tmp.log
echo "OK: $LOG"
