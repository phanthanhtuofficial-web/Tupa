"""Tự tìm các đoạn nên cắt: khoảng lặng, tiếng đệm (à/ừm/ờ), chỗ kéo dài ngập ngừng, lặp từ.

Dùng:  .venv-video/bin/python -I edit/find_cuts.py <video> <tr.json> <cuts.json>
- tr.json: kết quả edit/transcribe.py (có mốc thời gian từng từ).
- In ra báo cáo từng đoạn cắt (lý do + câu xung quanh) và lưu cuts.json = [[start, end, lý do], ...]
  (giây theo video gốc). render_*.py đọc file này qua biến môi trường CUTS=cuts.json.

Nguyên tắc (thận trọng, ưu tiên không cắt mất chữ):
1. Lặng      : âm lượng < -35 dB kéo dài > 0.35s  -> cắt, chừa lại 0.09s mỗi bên.
2. Tiếng đệm : khoảng giữa hai từ > 0.25s mà vẫn có tiếng (Whisper không ghi "à/ừm") -> cắt.
3. Ngập ngừng: một âm tiết (không phải con số) kéo dài > 0.9s (bình thường ~0.15–0.35s) -> bỏ phần giữa,
   giữ 0.3s đầu và cuối.
4. Lặp từ    : cụm 1–3 từ lặp liền nhau ("vùng vùng") hoặc vấp ở từ chức năng ("vẫn sẽ vẫn") -> cắt lần nói đầu.
"""
import json
import re
import subprocess
import sys

import numpy as np

video, trp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
SR = 16000
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
END = len(a) / SR
hop = SR // 100  # 10ms
rms = np.sqrt(np.convolve(a ** 2, np.ones(hop * 3) / (hop * 3), mode="same")[::hop] + 1e-12)
db = 20 * np.log10(rms)
voiced = db > -35


def vfrac(s, e):
    i, j = int(s * 100), int(e * 100)
    return float(voiced[i:j].mean()) if j > i else 0.0


words = []
for seg in json.load(open(trp)):
    for w in seg["words"]:
        words.append(dict(t=w["w"].strip(), s=w["s"], e=w["e"]))
norm = [re.sub(r"[^\wÀ-ỹ]", "", w["t"].lower()) for w in words]
FILLERS = {"à", "ừ", "ừm", "ờ", "ơ", "ờm", "ưm", "hừm", "ừa", "uh", "um", "ah", "eh"}
# từ chức năng hay bị vấp kiểu "vẫn sẽ vẫn", "có sẽ có" (danh từ như "vàng thì vàng" là câu đúng)
STUTTER = {"vẫn", "sẽ", "có", "đang", "là", "cái", "những", "mà", "được", "đã", "thì", "và", "của", "cho"}
OK_DOUBLE = {"từ", "nhiều", "lâu", "xa", "dần", "rất", "mãi", "hơn"}  # lặp có chủ ý

cuts = []
PAD = 0.09


def ctx(t):
    i = min(range(len(words)), key=lambda k: abs(words[k]["s"] - t))
    return " ".join(w["t"] for w in words[max(0, i - 4): i + 5])


# 1. lặng
i = 0
n = len(voiced)
while i < n:
    if not voiced[i]:
        j = i
        while j < n and not voiced[j]:
            j += 1
        s, e = i / 100, j / 100
        if e - s > 0.35:
            cuts.append([s + (0 if s < 0.05 else PAD), e - (0 if e > END - 0.05 else PAD), "lặng"])
        i = j
    else:
        i += 1

# 2. tiếng đệm trong khoảng trống giữa hai từ / 3. âm tiết kéo dài
for k in range(len(words)):
    w = words[k]
    if norm[k] in FILLERS:
        cuts.append([w["s"] - 0.03, w["e"] + 0.03, "tiếng đệm"])
        continue
    if k > 0:
        gs, ge = words[k - 1]["e"], w["s"]
        if ge - gs > 0.25 and vfrac(gs, ge) > 0.5:
            cuts.append([gs + 0.04, ge - 0.04, "tiếng đệm (à/ừm)"])
    dur = w["e"] - w["s"]
    is_num = any(ch.isdigit() for ch in w["t"])  # số đọc dài là bình thường ("bốn nghìn không trăm...")
    if dur > 0.9 and not is_num and vfrac(w["s"], w["e"]) > 0.3:
        # giữ 0.3s đầu (phụ âm) và 0.3s cuối, bỏ phần kéo dài ở giữa
        cuts.append([w["s"] + 0.3, w["e"] - 0.3, f"ngập ngừng ('{w['t']}' kéo dài {dur:.1f}s)"])

# 4. lặp từ / lặp cụm
k = 0
while k < len(words):
    hit = False
    for m in (3, 2, 1):
        if k + 2 * m <= len(words) and norm[k:k + m] == norm[k + m:k + 2 * m] and all(norm[k:k + m]):
            if m == 1 and norm[k] in OK_DOUBLE:
                continue
            if all(x.isdigit() for x in norm[k:k + m]):
                continue
            cuts.append([words[k]["s"] - 0.02, words[k + m]["s"] - 0.02, f"lặp từ: '{' '.join(w['t'] for w in words[k:k+m])}'"])
            k += m
            hit = True
            break
    if not hit:
        # lặp cách một từ đệm: "vẫn sẽ vẫn"
        if k + 2 < len(words) and norm[k] == norm[k + 2] and norm[k] in STUTTER:
            cuts.append([words[k]["s"] - 0.02, words[k + 2]["s"] - 0.02,
                         f"vấp: '{words[k]['t']} {words[k+1]['t']} {words[k+2]['t']}'"])
            k += 2
        else:
            k += 1

# gộp các đoạn chồng nhau, bỏ đoạn quá ngắn
cuts = [c for c in cuts if c[1] - c[0] > 0.08]
cuts.sort()
merged = []
for c in cuts:
    if merged and c[0] <= merged[-1][1] + 0.05:
        merged[-1][1] = max(merged[-1][1], c[1])
        if c[2] not in merged[-1][2]:
            merged[-1][2] += " + " + c[2]
    else:
        merged.append(list(c))
merged = [[round(max(0, s), 3), round(min(END, e), 3), r] for s, e, r in merged]
json.dump(merged, open(outp, "w"), ensure_ascii=False, indent=1)

tot = sum(e - s for s, e, _ in merged)
print(f"{len(merged)} đoạn cắt, tổng {tot:.1f}s / {END:.1f}s -> còn {END - tot:.1f}s\n")
for s, e, r in merged:
    if r != "lặng":
        print(f"{s:7.2f}-{e:7.2f} ({e - s:.2f}s) {r:40s} | {ctx(s)}")
