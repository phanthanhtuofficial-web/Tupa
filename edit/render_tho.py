"""Bản THÔ: chỉ cắt khoảng lặng / vấp / lặp câu + phụ đề chữ trắng viền đen, không đồ họa, tốc độ gốc.

Chạy:  .venv-video/bin/python -I edit/render_tho.py <video> <cuts.json> <subs.json> <END> <out.mp4>
- cuts.json: [[start, end, lý do], ...] (giây video gốc), giống file dùng cho render_*.py
- subs.json: [[start, end, "câu phụ đề"], ...] (giây video gốc, chính tả đã sửa tay)
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

SRC, CUTS, SUBS, END, OUT = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
WORK = os.path.join(os.path.dirname(os.path.abspath(OUT)), "_work_tho")
os.makedirs(WORK, exist_ok=True)
FPS, SR = 30, 48000

segs, cur = [], 0.0
for s, e, *_ in sorted(json.load(open(CUTS))):
    if s > cur + 0.05:
        segs.append((cur, min(s, END)))
    cur = max(cur, e)
if END > cur + 0.05:
    segs.append((cur, END))
segs = [(round(a * FPS) / FPS, round(b * FPS) / FPS) for a, b in segs if b > a]  # khớp khung hình


def out_t(t):
    o = 0.0
    for a, b in segs:
        if t < a:
            return o
        if t < b:
            return o + t - a
        o += b - a
    return o


# ---- phụ đề ASS
def ts(x):
    h, m = int(x // 3600), int(x % 3600 // 60)
    return f"{h}:{m:02d}:{x % 60:05.2f}"


ass = os.path.join(WORK, "subs.ass")
with open(ass, "w", encoding="utf-8") as f:
    f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Be Vietnam Pro,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,"
            "2,70,70,520,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    subs = json.load(open(SUBS))
    for k, (a, b, text) in enumerate(subs):
        oa, ob = out_t(a), out_t(b)
        if k + 1 < len(subs):
            ob = min(ob + 0.25, out_t(subs[k + 1][0]))  # giữ chữ thêm chút cho dễ đọc, không đè câu sau
        if ob - oa > 0.15:
            f.write(f"Dialogue: 0,{ts(oa)},{ts(ob)},Default,,0,0,0,,{text}\n")

# ---- âm thanh: ghép đoạn, fade 12ms mỗi chỗ cắt
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                     capture_output=True, check=True).stdout
a = np.frombuffer(raw, np.float32).astype(np.float64)
parts, fd = [], int(0.012 * SR)
for s, e in segs:
    n0, n1 = int(round(s * FPS)), int(round(e * FPS))
    seg = a[n0 * SR // FPS:n1 * SR // FPS].copy()
    r = np.linspace(0, 1, min(fd, len(seg) // 2))
    seg[:len(r)] *= r
    seg[len(seg) - len(r):] *= r[::-1]
    parts.append(seg)
voice = np.clip(np.concatenate(parts), -1, 1)
wav = os.path.join(WORK, "voice.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((voice * 32767).astype(np.int16).tobytes())

# ---- hình: giải mã đúng 30 khung/giây, giữ khung nằm trong đoạn giữ lại (khớp tuyệt đối với âm thanh)
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"fps={FPS},scale=1080:1920", "-f", "rawvideo",
                        "-pix_fmt", "yuv420p", "-"], stdout=subprocess.PIPE)
tmp = os.path.join(WORK, "video.mp4")
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", "1080x1920",
                        "-r", str(FPS), "-i", "-", "-vf", f"subtitles='{ass}':fontsdir='{FONT_DIR}'", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
keep = set()
for s_, e_ in segs:
    keep.update(range(int(round(s_ * FPS)), int(round(e_ * FPS))))
fsz, i, last = 1080 * 1920 * 3 // 2, 0, max(keep)
while i <= last:
    buf = dec.stdout.read(fsz)
    if len(buf) < fsz:
        break
    if i in keep:
        enc.stdin.write(buf)
    i += 1
dec.kill()
enc.stdin.close()
enc.wait()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", wav, "-af",
                "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-14:TP=-1.5:LRA=11,"
                "aresample=48000", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest",
                "-movflags", "+faststart", OUT], check=True)
print("Done ->", OUT, f"({len(keep) / FPS:.1f}s)")
