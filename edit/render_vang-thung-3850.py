"""Dựng video "Vàng thủng hỗ trợ 3.850" (18/11/2026, tốc độ 1.1x).
Nguồn: work/v1_combo.mp4 (tạo bằng edit/build_combo_thung-3850.sh từ v1.mov + 3 clip chèn). Chèn 4 ảnh chart người dùng gửi (edit/assets/thung-3850).

Chạy:  CUTS=edit/cuts_vang-thung-3850.json python render_vang-thung-3850.py work/v1_combo.mp4 <thu_muc_font> <output.mp4>
Mọi mốc thời gian trong file này tính theo GIÂY CỦA VIDEO GỐC (src).
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC, FONT_DIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PREVIEW = os.environ.get("PREVIEW")  # danh sách thời gian output, vd "1,5,10" -> chỉ xuất ảnh xem thử
WORK = os.path.join(os.path.dirname(os.path.abspath(OUT)), "_work_thung3850")
os.makedirs(WORK, exist_ok=True)

W, H, FPS = 1080, 1920, 30
GOLD = (245, 197, 66)
WHITE = (255, 255, 255)
GREY = (190, 190, 190)

# ============================================================ cắt khoảng lặng
SILENCES = []  # dùng CUTS=edit/cuts_vang-thung-3850.json
# Nguồn ghép (work/v1_combo.mp4) = v1.mov + 3 clip chèn. (tên, bắt đầu trong nguồn ghép, bắt đầu trong clip gốc, độ dài)
# a8  = clip 8s "vàng đang giao dịch quanh 3.780" (đã xoá logo TikTok, lấy 0.95–5.55s)
# b15 = video cũ 15s (0–9.05s), c32 = video cũ 32s (9.1–17.75s). Xem edit/build_combo_thung-3850.sh
PIECES = [("v1", 0.0, 0.0, 27.5), ("a8", 27.5, 0.0, 4.6), ("v1", 32.1, 27.5, 10.7),
          ("b15", 42.8, 0.0, 9.066667), ("c32", 51.866667, 0.0, 8.666667), ("v1", 60.533333, 38.2, 232.8)]


def T(t):
    """giây của v1.mov -> giây của nguồn ghép."""
    for nm, cs, ss, ln in PIECES:
        if nm == "v1" and ss <= t < ss + ln:
            return cs + t - ss
    return PIECES[-1][1] + t - PIECES[-1][2]


def where(tc):
    """giây của nguồn ghép -> (tên đoạn, giây trong đoạn đó)."""
    for nm, cs, ss, ln in PIECES:
        if cs <= tc < cs + ln:
            return nm, ss + tc - cs
    nm, cs, ss, ln = PIECES[-1]
    return nm, ss + tc - cs


END = T(268.20)
SPEED = float(os.environ.get("SPEED", "1.1"))  # tăng tốc toàn video, giữ cao độ giọng
PAD = 0.09
# Nếu có CUTS=<cuts.json> (tạo bởi edit/find_cuts.py: lặng + à/ừm + vấp + lặp từ) thì dùng danh sách đó.
if os.environ.get("CUTS"):
    import json
    CUT_LIST = []
    for s, e, *_ in json.load(open(os.environ["CUTS"])):  # mốc theo v1.mov -> đổi sang nguồn ghép
        for nm, cs, ss, ln in PIECES:
            a_, b_ = max(s, ss), min(e, ss + ln if nm != PIECES[-1][0] or cs != PIECES[-1][1] else 1e9)
            if nm == "v1" and b_ > a_:
                CUT_LIST.append((cs + a_ - ss, cs + b_ - ss))
else:
    CUT_LIST = [(s + PAD, e - PAD) for s, e in SILENCES if e - s > 0.3]
SEGS, cur = [], 0.0
for s, e in sorted(CUT_LIST):
    if s > cur + 0.05:
        SEGS.append((cur, s))
    cur = max(cur, e)
if END > cur + 0.05:
    SEGS.append((cur, END))

frames = []
for si, (a, b) in enumerate(SEGS):
    n = int(round((b - a) * FPS / SPEED))
    for k in range(n):
        frames.append((a + k * SPEED / FPS, si))
N = len(frames)


def out_time(src):
    lo, hi = 0, N - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if frames[mid][0] < src - 1e-6:
            lo = mid + 1
        else:
            hi = mid
    return lo / FPS


# ============================================================ kịch bản hình ảnh
# (src_start, src_end, scene)
SCENES = [
    (0.00, 22.55, "head"),
    (22.55, 27.50, "h4"),
    (27.50, 38.20, "m_proof"),
    (38.20, 44.90, "head"),
    (44.90, 61.40, "c_target1"),
    (61.40, 80.30, "head"),
    (80.30, 98.80, "c_confluence"),
    (98.80, 116.46, "head"),
    (116.46, 144.80, "c_target2"),
    (144.80, 157.40, "head"),
    (157.40, 188.10, "g_macro"),
    (188.10, 204.00, "head"),
    (204.00, 249.20, "g_advice"),
    (249.20, 259.60, "g_fomc"),
    (259.60, 999.0, "head"),
]
HOOK_END = 6.20
DISC_AT = 264.70


def scene_at(tc):
    nm, src = where(tc)
    if nm != "v1":
        for n2, cs, ss, ln in PIECES:
            if n2 == nm:
                return nm, cs, cs + ln
    for a, b, sc in SCENES:
        if a <= src < b:
            return sc, a, b
    return "head", 0.0, 999.0


FR_SCENE = [scene_at(s) for s, _ in frames]
WHIPS = [i for i in range(1, N) if FR_SCENE[i][0] != FR_SCENE[i - 1][0]]

# Zoom cho từng đoạn người nói: xen kẽ 1.12 / 1.22 để che jump-cut
HEAD_BLOCKS = [a for a, b, sc in SCENES if sc == "head"]


def head_zoom(src, si, block_start):
    bi = HEAD_BLOCKS.index(block_start)
    base = 1.12 if bi % 2 == 0 else 1.22
    # trong cùng một block, mỗi lần cắt khoảng lặng thì đổi zoom một chút
    if si % 2 == 1:
        base += 0.05
    a, b = SEGS[si]
    p = (src - a) / max(b - a, 1e-3)
    return base * (1.0 + 0.025 * p)


# ============================================================ helpers
def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


_fc = {}


def font(weight, size):
    k = (weight, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(os.path.join(FONT_DIR, f"BeVietnamPro-{weight}.ttf"), size)
    return _fc[k]


def parse_rich(line):
    out, gold = [], False
    for part in line.split("*"):
        if part:
            out.append((part, gold))
        gold = not gold
    return out


def glow(layer, radius=14, strength=1.6, color=GOLD):
    small = layer.resize((max(1, layer.width // 2), max(1, layer.height // 2)), Image.BILINEAR)
    a = small.split()[3].filter(ImageFilter.GaussianBlur(radius / 2))
    a = a.point(lambda v: min(255, int(v * strength)))
    g = Image.new("RGBA", small.size, color + (0,))
    g.putalpha(a)
    return g.resize(layer.size, Image.BILINEAR)


def with_glow(img, radius=24, strength=1.2):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(glow(img, radius, strength))
    out.alpha_composite(img)
    return out


def shadowed(layer, radius=10, opacity=0.85, offset=(0, 5)):
    a = layer.split()[3].filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(layer)
    return out


_cache = {}
MAXW = 980


def rich_block(lines, sizes, weight="Black", pad=40, line_gap=8, shadow=True, maxw=MAXW):
    key = ("rb", tuple(lines), tuple(sizes), weight, shadow, maxw)
    if key in _cache:
        return _cache[key]
    rows = []
    for ln, sz in zip(lines, sizes):
        toks = parse_rich(ln)
        while True:  # tự thu nhỏ cho vừa khung
            f = font(weight, sz)
            w = sum(f.getlength(t) for t, _ in toks)
            if w <= maxw or sz <= 30:
                break
            sz -= 2
        rows.append((toks, f, w, sz))
    bw = int(max(r[2] for r in rows)) + pad * 2
    bh = int(sum(r[3] * 1.2 + line_gap for r in rows)) + pad * 2
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for toks, f, w, sz in rows:
        x = (bw - w) / 2
        for t, g in toks:
            d.text((x, y), t, font=f, fill=GOLD if g else WHITE)
            x += f.getlength(t)
        y += sz * 1.2 + line_gap
    if shadow:
        img = shadowed(img, radius=9, opacity=0.9, offset=(0, 4))
    _cache[key] = img
    return img


def paste_center(canvas, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01:
        return
    if abs(scale - 1.0) > 0.005:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.split()[3].point(lambda v: int(v * alpha)))
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def pop(canvas, img, cx, cy, now, t_in, dur=0.28):
    if now < t_in:
        return
    p = (now - t_in) / dur
    paste_center(canvas, img, cx, cy, scale=0.82 + 0.18 * ease_back(p), alpha=ease_out(p * 1.6))


# ------------------------------------------------------------ icons
def icon(d, kind, x, y, s, col):
    lw = max(3, s // 9)
    if kind == "calendar":
        d.rounded_rectangle([x, y + s * 0.12, x + s, y + s], radius=s * 0.15, outline=col, width=lw)
        d.line([x, y + s * 0.38, x + s, y + s * 0.38], fill=col, width=lw)
        d.line([x + s * 0.28, y, x + s * 0.28, y + s * 0.25], fill=col, width=lw)
        d.line([x + s * 0.72, y, x + s * 0.72, y + s * 0.25], fill=col, width=lw)
    elif kind == "up":
        d.line([(x, y + s * 0.85), (x + s * 0.38, y + s * 0.45), (x + s * 0.6, y + s * 0.65), (x + s, y + s * 0.15)],
               fill=col, width=lw, joint="curve")
        d.polygon([(x + s, y + s * 0.05), (x + s * 0.68, y + s * 0.12), (x + s * 0.95, y + s * 0.4)], fill=col)
    elif kind == "down":
        d.line([(x, y + s * 0.15), (x + s * 0.38, y + s * 0.55), (x + s * 0.6, y + s * 0.35), (x + s, y + s * 0.85)],
               fill=col, width=lw, joint="curve")
        d.polygon([(x + s, y + s * 0.95), (x + s * 0.68, y + s * 0.88), (x + s * 0.95, y + s * 0.6)], fill=col)
    elif kind == "shield":
        d.polygon([(x + s / 2, y), (x + s, y + s * 0.18), (x + s * 0.9, y + s * 0.7), (x + s / 2, y + s),
                   (x + s * 0.1, y + s * 0.7), (x, y + s * 0.18)], outline=col, width=lw)
    elif kind == "warn":
        d.polygon([(x + s / 2, y), (x + s, y + s * 0.92), (x, y + s * 0.92)], outline=col, width=lw)
        d.line([x + s / 2, y + s * 0.32, x + s / 2, y + s * 0.62], fill=col, width=lw)
        d.ellipse([x + s / 2 - lw * 0.7, y + s * 0.72, x + s / 2 + lw * 0.7, y + s * 0.72 + lw * 1.4], fill=col)
    elif kind == "line":  # trendline
        d.line([x, y + s * 0.9, x + s, y + s * 0.1], fill=col, width=lw)
        for px, py in ((0.15, 0.78), (0.5, 0.5), (0.85, 0.22)):
            d.ellipse([x + s * px - lw, y + s * py - lw, x + s * px + lw, y + s * py + lw], fill=col)
    elif kind == "bank":
        d.polygon([(x, y + s * 0.32), (x + s / 2, y), (x + s, y + s * 0.32)], outline=col, width=lw)
        for px in (0.18, 0.5, 0.82):
            d.line([x + s * px, y + s * 0.42, x + s * px, y + s * 0.82], fill=col, width=lw)
        d.line([x, y + s * 0.94, x + s, y + s * 0.94], fill=col, width=lw)
    elif kind == "coin":
        d.ellipse([x, y, x + s, y + s], outline=col, width=lw)
        f = font("Black", int(s * 0.6))
        d.text((x + s / 2 - f.getlength("$") / 2, y + s * 0.12), "$", font=f, fill=col)


def node_img(label, kind=None, sub=None, gold=False, qmark=False, size=50):
    key = ("node", label, kind, sub, gold, qmark, size)
    if key in _cache:
        return _cache[key]
    col = GOLD if gold else WHITE
    pad = 90
    if qmark:
        bw, bh = 100, 100
        f = font("Black", 54)
    else:
        f = font("Black", size)
        isz = int(size * 0.88) if kind else 0
        bw = int(f.getlength(label) + (isz + 22 if kind else 0) + 72)
        bh = int(size * 2.16)
    fsub = font("Medium", 31)
    sub_w = int(fsub.getlength(sub)) if sub else 0
    cw = max(bw, sub_w) + pad * 2
    ch = bh + (58 if sub else 0) + pad * 2
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bx, by = (cw - bw) / 2, pad
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=(12, 12, 14, 235), outline=col, width=4)
    if qmark:
        d.text((bx + (bw - f.getlength("?")) / 2, by + 12), "?", font=f, fill=WHITE)
    else:
        x = bx + 36
        if kind:
            icon(d, kind, x, by + (bh - isz) / 2, isz, col)
            x += isz + 22
        d.text((x, by + bh / 2 - size * 0.66), label, font=f, fill=col)
    if sub:
        d.text(((cw - sub_w) / 2, by + bh + 12), sub, font=fsub, fill=(205, 205, 205, 220))
    if gold:
        img = with_glow(img, 26, 1.3)
    _cache[key] = (img, by + bh / 2 - ch / 2, bh)
    return _cache[key]


def place_node(canvas, label, cy, t_in, now, cx=540, **kw):
    if now < t_in:
        return
    img, off, _ = node_img(label, **kw)
    p = (now - t_in) / 0.30
    paste_center(canvas, img, cx, cy - off, scale=0.82 + 0.18 * ease_back(p), alpha=ease_out(p * 1.6))


def header(canvas, text, now, t_in, y=400):
    a = ease_out((now - t_in) / 0.4)
    if a <= 0:
        return
    f = font("SemiBold", 30)
    t = text.upper()
    track = 12
    tw = sum(f.getlength(c) for c in t) + track * (len(t) - 1)
    lay = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x = (W - tw) / 2
    for c in t:
        d.text((x, 8), c, font=f, fill=GREY + (int(255 * a),))
        x += f.getlength(c) + track
    canvas.alpha_composite(lay, (0, y - int(14 * (1 - a))))


def connector(canvas, x1, y1, x2, y2, now, t0, dur=0.35, dashed=False, gold=False):
    p = ease_out((now - t0) / dur)
    if p <= 0:
        return
    d = ImageDraw.Draw(canvas)
    ex, ey = x1 + (x2 - x1) * p, y1 + (y2 - y1) * p
    col = (GOLD if gold else (220, 220, 220)) + (230,)
    L = math.hypot(ex - x1, ey - y1)
    if dashed and L > 0:
        ux, uy = (ex - x1) / L, (ey - y1) / L
        s = 0.0
        while s < L:
            e = min(s + 12, L)
            d.line([x1 + ux * s, y1 + uy * s, x1 + ux * e, y1 + uy * e], fill=col, width=3)
            s += 22
    else:
        d.line([x1, y1, ex, ey], fill=col, width=3)
    if p >= 1:
        ph = ((now - t0) * 0.9) % 1.0
        cx, cy = x1 + (x2 - x1) * ph, y1 + (y2 - y1) * ph
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 236, 170, 255))
    else:
        d.ellipse([ex - 7, ey - 7, ex + 7, ey + 7], fill=(255, 236, 170, 255))


def big_text(canvas, line, size, cy, now, t_in, gold_glow=True, weight="Black"):
    if now < t_in:
        return
    img = rich_block([line], [size], weight=weight, shadow=False)
    if gold_glow and "*" in line:
        key = ("bg", line, size, weight)
        if key not in _cache:
            _cache[key] = with_glow(img, 26, 1.0)
        img = _cache[key]
    pop(canvas, img, 540, cy, now, t_in, dur=0.3)


# ------------------------------------------------------------ backgrounds
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - 540) / 700) ** 2 + ((yy - 980) / 1000) ** 2)
    v = np.clip(1 - r, 0, 1) ** 1.6
    base = np.array([7, 7, 9], np.float32)
    hi = np.array([34, 33, 36], np.float32)
    img = base + (hi - base) * v[..., None]
    img += np.random.default_rng(1).normal(0, 1.4, img.shape[:2])[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


BG = make_bg()


def make_shade(start=0.5, strength=0.72):
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    bottom = np.clip((yy - start) / (1 - start), 0, 1) ** 1.4 * strength
    vig = np.clip((xx ** 2) * 0.35 + ((yy - 0.45) * 1.6) ** 2 * 0.18, 0, 1) * 0.55
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (np.clip(bottom + vig, 0, 0.85) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


SHADE = make_shade()
SHADE_LOW = make_shade(0.62, 0.8)


BANNER_SMALL, BANNER_BIG = "PHÂN TÍCH XU HƯỚNG", "GIÁ VÀNG"


def make_banner():
    bh = 300
    t = np.linspace(0, 1, bh)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    arr = np.zeros((bh, W, 4), np.uint8)
    arr[..., 0] = (12 + 40 * x * (1 - t * 0.3)).astype(np.uint8)
    arr[..., 1] = (10 + 26 * x * (1 - t * 0.3)).astype(np.uint8)
    arr[..., 2] = (8 + 10 * x).astype(np.uint8)
    arr[..., 3] = 245
    img = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(img)
    d.line([0, bh - 3, W, bh - 3], fill=GOLD + (200,), width=3)
    f1 = font("SemiBold", 30)
    x0 = 70
    for c in BANNER_SMALL:
        d.text((x0, 70), c, font=f1, fill=(225, 200, 150))
        x0 += f1.getlength(c) + 6
    f2 = font("Black", 112)
    m = Image.new("L", (W, bh), 0)
    ImageDraw.Draw(m).text((66, 112), BANNER_BIG, font=f2, fill=255)
    gy = np.linspace(0, 1, bh)[:, None] * np.ones((1, W))
    top, bot = np.array([255, 233, 160]), np.array([196, 140, 40])
    grad = top + (bot - top) * np.clip((gy - 0.35) / 0.45, 0, 1)[..., None]
    gimg = Image.fromarray(grad.astype(np.uint8)).convert("RGBA")
    gimg.putalpha(m)
    img.alpha_composite(shadowed(gimg, radius=6, opacity=0.8, offset=(0, 3)))
    return img


BANNER = make_banner()


def make_disclaimer():
    f = font("Medium", 26)
    t = "Nội dung mang tính tham khảo, không phải lời khuyên đầu tư"
    img = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    ImageDraw.Draw(img).text(((W - f.getlength(t)) / 2, 12), t, font=f, fill=(230, 230, 230, 210))
    return shadowed(img, radius=4, opacity=0.9, offset=(0, 2))


DISC = make_disclaimer()


def grab(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", SRC, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return Image.fromarray(np.frombuffer(raw, np.uint8).reshape(H, W, 3)).convert("RGBA")

# ============================================================ captions (cảnh người nói)
CAPTIONS = [
    (13.10, 21.50, ["SÁNG NAY VỪA NGỦ DẬY", "*MỞ CHART RA NHÌN*"], [60, 84]),
    (21.50, 23.30, ["*SANG CHẤN*", "*TÂM LÝ LUÔN*"], [96, 96]),
    (38.90, 44.90, ["THỦNG VÙNG NÀY", "*VỀ VÙNG GIÁ RẤT SÂU*"], [60, 84]),
    (61.40, 64.00, ["TẠI SAO", "*MÌNH NÓI NHƯ VẬY?*"], [64, 84]),
    (98.80, 103.30, ["NẾU VÀNG *GIỮ ĐƯỢC*", "*VÙNG NÀY*"], [64, 96]),
    (103.30, 116.50, ["VẪN CÓ THỂ", "*TĂNG NGẮN HẠN*"], [60, 96]),
    (144.70, 157.40, ["BỐI CẢNH VĨ MÔ", "*BẤT LỢI CHO VÀNG*"], [60, 88]),
    (196.60, 204.00, ["NHÀ ĐẦU TƯ", "*TÍCH SẢN VÀNG VẬT CHẤT*"], [60, 80]),
    (259.60, 999.0, ["THEO DÕI MÌNH ĐỂ CẬP NHẬT", "*TIN VÀNG MỖI NGÀY*"], [54, 88]),
]


def draw_captions(canvas, src, cy=1530):
    for a, b, lines, sizes in CAPTIONS:
        if a <= src < b:
            img = rich_block(lines, sizes)
            p = (src - a) / 0.16
            paste_center(canvas, img, 540, cy, scale=0.88 + 0.12 * ease_back(p), alpha=ease_out(p * 1.5))


def draw_hook(canvas, src):
    t = src - SEGS[0][0]  # tính từ khung hình đầu tiên của output
    p = ease_out(t / 0.35)
    canvas.alpha_composite(BANNER, (0, int(-300 * (1 - p))))
    rows = [
        (["VÀNG ĐÃ THỦNG"], [92], 1320, 0.00),
        (["*HỖ TRỢ 3.850*"], [124], 1460, 0.12),
        (["XU HƯỚNG *SẮP TỚI* RA SAO?"], [54], 1600, 0.40),
    ]
    for lines, sizes, cy, d in rows:
        img = rich_block(lines, sizes, pad=30)
        q = (t - d) / 0.25
        paste_center(canvas, img, 540, cy, scale=0.75 + 0.25 * ease_back(q), alpha=ease_out(q * 1.5))


# ============================================================ ảnh chart người dùng gửi
def pill(text, size=40, gold=True, sub=None):
    key = ("pill", text, size, gold, sub)
    if key in _cache:
        return _cache[key]
    f = font("Black", size)
    fs = font("SemiBold", int(size * 0.55))
    tw = f.getlength(text)
    sw = fs.getlength(sub) if sub else 0
    bw = int(max(tw, sw) + 56)
    bh = int(size * 1.7 + (size * 0.8 if sub else 0))
    pad = 60
    img = Image.new("RGBA", (bw + pad * 2, bh + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = GOLD if gold else WHITE
    d.rounded_rectangle([pad, pad, pad + bw, pad + bh], radius=14, fill=(10, 10, 12, 230), outline=col, width=4)
    y = pad + size * 0.3
    if sub:
        d.text((pad + (bw - sw) / 2, y - 4), sub, font=fs, fill=(215, 215, 215))
        y += size * 0.75
    d.text((pad + (bw - tw) / 2, y - size * 0.12), text, font=f, fill=col)
    if gold:
        img = with_glow(img, 22, 1.0)
    _cache[key] = img
    return img


IMGDIR = os.environ.get("IMGDIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "thung-3850"))
_imgs = {}


def load_img(name):
    """Ảnh chụp màn hình (1179x2556 hoặc 2556x1179) -> đưa về hệ tọa độ đã đo (923x2000 / 2000x923)."""
    if name not in _imgs:
        im = Image.open(os.path.join(IMGDIR, name + ".png")).convert("RGBA")
        size = (923, 2000) if im.height > im.width else (2000, 923)
        _imgs[name] = im.resize(size, Image.LANCZOS)
    return _imgs[name]


def ken_burns(img, z, cx=540, cy=960):
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def hl_band(lay, x0, y0, x1, y1, now, t_in):
    """Dải vàng nhấp nháy (tọa độ trên layer)."""
    p = ease_out((now - t_in) / 0.45)
    if p <= 0:
        return
    xe = x0 + (x1 - x0) * p
    d = ImageDraw.Draw(lay)
    pulse = 0.5 + 0.5 * math.sin((now - t_in) * 4)
    d.rectangle([x0, y0, xe, y1], fill=GOLD + (int(60 + 40 * pulse),))
    d.line([x0, y0, xe, y0], fill=GOLD + (255,), width=4)
    d.line([x0, y1, xe, y1], fill=GOLD + (255,), width=4)


def hl_line(lay, x0, y0, x1, y1, now, t_in, width=7):
    p = ease_out((now - t_in) / 0.6)
    if p <= 0:
        return
    d = ImageDraw.Draw(lay)
    d.line([x0, y0, x0 + (x1 - x0) * p, y0 + (y1 - y0) * p], fill=GOLD + (255,), width=width)


def finish_layer(base, lay):
    base.alpha_composite(glow(lay, 16, 1.2))
    base.alpha_composite(lay)


# --- ảnh 1: XAU/USD khung 4H (dọc) – phủ kín khung hình
S4 = 1080 / 923


def h4_xy(x, y):
    return x * S4, (y - 160) * S4


def h4_price(p):  # trục giá đo từ ảnh: 3.900 ở y=649, 3.800 ở y=1049
    return h4_xy(0, 649 + (3900 - p) * 4.0)[1]


def draw_h4(src, a, t_band, t_pill):
    im = load_img("h4")
    c = im.resize((W, int(im.height * S4)), Image.LANCZOS).crop((0, int(160 * S4), W, int(160 * S4) + H))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hl_band(lay, 0, h4_price(3862), 876, h4_price(3848), src, t_band)
    finish_layer(c, lay)
    pop(c, pill("THỦNG HỖ TRỢ 3.850", 50, sub="KHUNG 4 GIỜ"), 360, 1300, src, t_pill)
    return c


# --- ảnh ngang (khung tuần): cắt vùng quan trọng, đặt thành thẻ giữa màn hình
CW = 1040
CARDS = {  # tên: (ảnh, vùng cắt x0, y0, x1, y1 trên ảnh 2000x923)
    "w_wide": ("w_wide", (700, 40, 1860, 700)),
    "w_mid": ("w_mid", (900, 40, 1860, 700)),
    "w_zoom": ("w_zoom", (560, 80, 1690, 690)),
}


def card_base(name):
    key = ("card", name)
    if key not in _cache:
        im, box = CARDS[name]
        sc = CW / (box[2] - box[0])
        crop = load_img(im).crop(box)
        _cache[key] = (crop.resize((CW, int(crop.height * sc)), Image.LANCZOS), sc, box)
    return _cache[key]


def card_frame(name, annotate, src, cy=960):
    img, sc, box = card_base(name)

    def m(x, y):
        return (x - box[0]) * sc, (y - box[1]) * sc
    c = img.copy()
    lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
    annotate(lay, m, src)
    finish_layer(c, lay)
    fr = Image.new("RGBA", (c.width + 12, c.height + 12), (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle([0, 0, fr.width - 1, fr.height - 1], radius=20, fill=GOLD + (230,))
    fr.alpha_composite(c, (6, 6))
    canvas = BG.copy()
    canvas.alpha_composite(shadowed(with_glow(fr, 30, 0.7), radius=16, opacity=0.9, offset=(0, 8)),
                           (int(540 - fr.width / 2), int(cy - fr.height / 2)))
    return canvas, cy - fr.height / 2, cy + fr.height / 2


def wide_price(p):  # w_wide: 4.000 ở y=235, 3.000 ở y=386
    return 386 - (p - 3000) * 0.151


def mid_price(p):  # w_mid: 4.000 ở y=242, 3.000 ở y=377
    return 377 - (p - 3000) * 0.135


def ann_target_3000(lay, m, s):
    x0, y0 = m(700, wide_price(3300))
    x1, y1 = m(1690, wide_price(3000))
    hl_band(lay, x0, y0, x1, y1, s, 49.3)


def ann_confluence(lay, m, s):
    hl_line(lay, *m(560, 637), *m(1688, 420), s, 80.6)
    x0, y0 = m(560, 470)
    x1, y1 = m(1442, 497)
    hl_band(lay, x0, y0, x1, y1, s, 90.2)


def ann_target_3300(lay, m, s):
    x0, y0 = m(900, mid_price(3500))
    x1, y1 = m(1690, mid_price(3300))
    hl_band(lay, x0, y0, x1, y1, s, 132.9)


def draw_card(sc, src, a):
    if sc == "c_target1":
        c, top, bot = card_frame("w_wide", ann_target_3000, src)
        header(c, "Vàng · khung tuần", src, a + 0.05, y=int(top - 230))
        pop(c, pill("3.000 – 3.300 $/oz", 60, sub="VÙNG GIÁ RẤT SÂU"), 540, top - 110, src, 49.3)
        pop(c, pill("≈ 100 – 110 TRIỆU / LƯỢNG", 46, gold=False, sub="QUY ĐỔI GIÁ VÀNG VẬT CHẤT"), 540, bot + 130,
            src, 55.5)
    elif sc == "c_confluence":
        c, top, bot = card_frame("w_zoom", ann_confluence, src)
        pop(c, pill("VÙNG HỢP LƯU", 64), 540, top - 120, src, a + 0.05)
        pop(c, pill("XU HƯỚNG TĂNG DÀI HẠN", 44, gold=False, sub="1 · ĐƯỜNG XU HƯỚNG"), 540, bot + 110, src, 80.6)
        if src >= 88.8:
            pop(c, pill("VÙNG MUA FOMO", 44, sub="2 · HỖ TRỢ CỦA NHÀ ĐẦU TƯ NĂM NGOÁI"), 540, bot + 300, src, 88.8)
    else:  # c_target2
        c, top, bot = card_frame("w_mid", ann_target_3300, src)
        pop(c, pill("ĐÃ THỦNG VÙNG HỖ TRỢ", 54, gold=False), 540, top - 120, src, a + 0.05)
        pop(c, pill("3.300 – 3.500 $/oz", 60, sub="KHÔNG CÒN QUÁ XA"), 540, bot + 120, src, 132.9)
    return c


# ============================================================ đoạn chèn: clip 8s, ảnh nhận định, video cũ
A8_CAPS = [(0.0, 9.0, ["HIỆN TẠI VÀNG GIAO DỊCH", "*QUANH 3.780 $/oz*"], [58, 96])]


def draw_a8(src_rgb, t):
    z = 1.14 + 0.03 * t / 4.6
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, min(max(1020 - 800 / z, 0), H - ch)
    canvas = Image.fromarray(src_rgb).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
    canvas.alpha_composite(SHADE)
    for a, b, lines, sizes in A8_CAPS:
        if a <= t < b:
            p = (t - a) / 0.16
            paste_center(canvas, rich_block(lines, sizes), 540, 1530, scale=0.88 + 0.12 * ease_back(p),
                         alpha=ease_out(p * 1.5))
    return canvas


# Ảnh chụp nhận định (theo thứ tự thời gian): (file, vùng khung đỏ x0,y0,x1,y1, nhãn ngày, giây v1 hiện ra)
PROOFS = [
    ("p1_0611", (13, 1034, 940, 1534), "06/11", 27.80),
    ("p2", (288, 334, 1145, 759), None, 28.95),
    ("p3_0811", (54, 170, 949, 742), "08/11", 30.05),
    ("p4", (278, 184, 1153, 681), None, 31.10),
    ("p5_1311", (272, 865, 1127, 1401), "13/11", 32.10),
    ("p6_1311", (293, 866, 1130, 1401), "13/11", 33.75),
    ("p7_1311", (294, 1274, 1115, 1700), "13/11", 35.00),
]
PROOF_T = [p[3] for p in PROOFS]
PROOF_STAMP = 36.30


def proof_card(k):
    """Nguyên ảnh chụp màn hình (thấy rõ giao diện Zalo/Telegram) + vị trí ô đỏ trên thẻ."""
    key = ("proof", k)
    if key not in _cache:
        name, box, date, _ = PROOFS[k]
        im = Image.open(os.path.join(IMGDIR, name + ".jpg")).convert("RGBA")
        sc = min(900 / im.width, 1380 / im.height)
        full = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        mask = Image.new("L", full.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, full.width - 1, full.height - 1], radius=26, fill=255)
        full.putalpha(mask)
        pad, top = 50, 110
        card = Image.new("RGBA", (full.width + pad * 2, full.height + pad + top), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([pad - 5, top - 5, pad + full.width + 4, top + full.height + 4],
                                               radius=30, fill=(70, 70, 76, 255))
        card.alpha_composite(full, (pad, top))
        card = shadowed(card, radius=18, opacity=0.95, offset=(0, 12))
        if date:
            tg = pill("NGÀY " + date, 36, gold=False)
            card.alpha_composite(tg, (0, max(0, top - tg.height + 25)))
        m = 10  # ô đỏ (cắt từ ảnh gốc, nét hơn) + vị trí trên thẻ
        bx = (max(box[0] - m, 0), max(box[1] - m, 0), min(box[2] + m, im.width), min(box[3] + m, im.height))
        hi = im.crop(bx)
        hi = hi.resize((max(1, int(hi.width * sc)), max(1, int(hi.height * sc))), Image.LANCZOS)
        pos = (pad + bx[0] * sc + hi.width / 2, top + bx[1] * sc + hi.height / 2)
        _cache[key] = (card, hi, pos, (pad, top, full.width, full.height))
    return _cache[key]


def rotated(img, deg):
    key = ("rot", id(img), round(deg, 1))
    if key not in _cache:
        _cache[key] = img.rotate(deg, Image.BICUBIC, expand=True)
    return _cache[key]


def hi_scale(hi, w):
    """Phóng ô đỏ: tối đa rộng 1000px, to hơn tối thiểu 12%."""
    return max(1.12, min(1000 / hi.width, 2.2)) if w else 1.0


def draw_proof(s):
    c = BG.copy()
    header(c, "Nhận định mình đã chia sẻ", s, 27.55, y=150)
    shown = [k for k, p in enumerate(PROOFS) if s >= p[3]]
    if not shown:
        return c
    cur = shown[-1]
    CY = 1010
    for k in shown[-3:-1]:  # ảnh trước lùi ra sau, nghiêng, tối đi
        depth = cur - k
        card = proof_card(k)[0]
        img = rotated(card, (-5 if k % 2 == 0 else 5)).copy()
        dark = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dark.putalpha(img.split()[3].point(lambda v: int(v * (0.5 + 0.15 * depth))))
        img.alpha_composite(dark)
        paste_center(c, img, 540 + (-60 if k % 2 == 0 else 60) * depth, CY - 30 * depth, scale=0.92 - 0.05 * depth)
    card, hi, pos, (px, py, fw, fh) = proof_card(cur)
    t = s - PROOFS[cur][3]
    p = t / 0.24  # 1) cả ảnh bay vào
    dx = (1 - ease_out(p)) * (300 if cur % 2 == 0 else -300)
    scale = 1.25 - 0.25 * ease_back(p)
    ox, oy = 540 + dx - card.width * scale / 2, CY - card.height * scale / 2
    paste_center(c, card, 540 + dx, CY, scale=scale, alpha=ease_out(p * 2.2))
    q = ease_out((t - 0.30) / 0.25)  # 2) phần ngoài ô đỏ tối đi, ô đỏ phóng to nổi lên
    if q > 0:
        dim = Image.new("RGBA", (fw, fh), (0, 0, 0, int(150 * q)))
        c.alpha_composite(dim, (int(ox + px * scale), int(oy + py * scale)))
        z = 1 + (hi_scale(hi, 1) - 1) * ease_back(min(1.0, (t - 0.30) / 0.28))
        hx = ox + pos[0] * scale
        hy = oy + pos[1] * scale
        hw = hi.width * z
        hx = min(max(hx, hw / 2 + 20), W - hw / 2 - 20)  # không tràn khỏi khung hình
        key = ("higlow", cur)
        if key not in _cache:
            f = Image.new("RGBA", (hi.width + 16, hi.height + 16), (0, 0, 0, 0))
            ImageDraw.Draw(f).rounded_rectangle([0, 0, f.width - 1, f.height - 1], radius=14, fill=GOLD + (255,))
            f.alpha_composite(hi, (8, 8))
            _cache[key] = shadowed(with_glow(f, 30, 1.2), radius=20, opacity=0.95, offset=(0, 14))
        paste_center(c, _cache[key], hx, hy, scale=z, alpha=min(1.0, q * 1.5))
    if t < 0.12:  # chớp sáng khi ảnh mới bật ra
        c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(70 * (1 - t / 0.12)))))
    if s >= PROOF_STAMP:
        pop(c, pill("ĐÃ CHIA SẺ RẤT NHIỀU LẦN", 54, sub="VÙNG HỖ TRỢ CỰC KỲ QUAN TRỌNG"), 540, 1790, s, PROOF_STAMP)
    return c


CLIP_LABEL = {"b15": ("VIDEO NHẬN ĐỊNH TRƯỚC ĐÂY", "Thủng 3.870 – 3.900: về vùng giá rất sâu"),
              "c32": ("VIDEO XU HƯỚNG DÀI HẠN", "Vùng hỗ trợ cực kỳ quan trọng 3.880 – 3.900")}


def draw_clip(nm, src_rgb, t):
    fr = Image.fromarray(src_rgb)
    bg = fr.resize((W // 10, H // 10), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.62).convert("RGBA")
    sc = 0.70
    cw, ch = int(W * sc), int(H * sc)
    v = fr.resize((cw, ch), Image.BILINEAR).convert("RGBA")
    key = ("clipframe", cw, ch)
    if key not in _cache:
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=28, fill=255)
        f = Image.new("RGBA", (cw + 16, ch + 16), (0, 0, 0, 0))
        ImageDraw.Draw(f).rounded_rectangle([0, 0, cw + 15, ch + 15], radius=34, fill=GOLD + (255,))
        _cache[key] = (m, with_glow(f, 30, 1.0))
    m, f = _cache[key]
    v.putalpha(m)
    card = f.copy()
    card.alpha_composite(v, (8, 8))
    p = t / 0.32
    paste_center(bg, card, 540, 1010, scale=0.55 + 0.45 * ease_back(p), alpha=ease_out(p * 2))
    top, sub = CLIP_LABEL[nm]
    pop(bg, pill(top, 46), 540, 150, t, 0.15)
    lay = Image.new("RGBA", (W, 80), (0, 0, 0, 0))  # chấm đỏ nhấp nháy "XEM LẠI"
    d = ImageDraw.Draw(lay)
    if int(t * 2.5) % 2 == 0:
        d.ellipse([370, 22, 402, 54], fill=(235, 45, 55, 255))
    d.text((418, 38), "XEM LẠI", font=font("Black", 40), fill=WHITE, anchor="lm")
    if t >= 0.3:
        bg.alpha_composite(lay, (0, 228))
    if t >= 0.5:
        pop(bg, rich_block([sub], [40], weight="ExtraBold"), 540, 1740, t, 0.5)
    return bg


# ============================================================ các cảnh đồ họa
def g_macro(c, s):
    header(c, "Vì sao vàng chịu áp lực", s, 157.45)
    place_node(c, "FED TĂNG LÃI NHIỀU LẦN", 560, 158.4, s, kind="bank", gold=158.4 <= s < 170.1, size=44,
               sub="lãi cao, gửi tiền có lãi – giữ vàng không sinh lãi" if s >= 162.4 else None)
    place_node(c, "USD MẠNH NHẤT 19 THÁNG", 800, 170.2, s, kind="coin", gold=170.2 <= s < 177.6, size=44)
    place_node(c, "CHI TIÊU NGƯỜI MỸ VẪN MẠNH", 1010, 177.6, s, kind="up", gold=177.6 <= s < 185.3, size=44)
    connector(c, 540, 1100, 540, 1200, s, 184.9, dur=0.4, dashed=True, gold=True)
    place_node(c, "FED CÓ LÝ DO TĂNG LÃI", 1280, 185.4, s, kind="warn", gold=True, size=50)


def g_advice(c, s):
    header(c, "Với vàng vật chất", s, 204.05)
    place_node(c, "MUA Ở VÙNG TÍCH LŨY", 560, 209.9, s, kind="shield", gold=209.9 <= s < 215.9, size=46)
    place_node(c, "KHÔNG MUA VÙNG FOMO", 790, 212.8, s, kind="warn", gold=False, size=46)
    place_node(c, "VÀNG VẪN TIẾP TỤC GIẢM", 1020, 215.9, s, kind="down", gold=215.9 <= s < 227.5, size=46,
               sub="trong thời gian sắp tới")
    if s >= 227.6:
        pop(c, pill("GIỮ DÀI HẠN · KHÔNG LƯỚT SÓNG", 50, sub="VÀNG VẬT CHẤT"), 540, 1320, s, 227.6)


def g_fomc(c, s):
    header(c, "Trước mắt", s, 249.25)
    place_node(c, "ÁP LỰC LÊN VÀNG VẪN LỚN", 600, 249.3, s, kind="down", gold=s < 251.6, size=46)
    place_node(c, "ĐỔI XU HƯỚNG KHI FED NGỪNG TĂNG LÃI", 860, 251.6, s, kind="bank", gold=251.6 <= s < 255.0,
               size=36)
    connector(c, 540, 980, 540, 1080, s, 254.6, dur=0.3, dashed=True, gold=True)
    place_node(c, "2H SÁNG MAI · BIÊN BẢN HỌP FED", 1160, 255.0, s, kind="calendar", gold=True, size=42,
               sub="giá có thể giật mạnh" if s >= 257.5 else None)


GRAPHICS = {"g_macro": g_macro, "g_advice": g_advice, "g_fomc": g_fomc}


# ============================================================ compose
def motion_blur_x(arr, k):
    if k < 2:
        return arr
    a = arr.astype(np.float32)
    c = np.cumsum(np.pad(a, ((0, 0), (k, 0), (0, 0)), mode="edge"), axis=1)
    return ((c[:, k:] - c[:, :-k]) / k).astype(np.uint8)


def compose(i, src_rgb):
    src_c, si = frames[i]
    nm, src = where(src_c)
    sc, a, b = FR_SCENE[i]
    prog = ((src if nm == "v1" else src_c) - a) / max(b - a, 1e-3)
    if sc == "a8":
        canvas = draw_a8(src_rgb, src)
    elif sc in ("b15", "c32"):
        canvas = draw_clip(sc, src_rgb, src)
    elif sc == "m_proof":
        canvas = draw_proof(src)
    elif sc == "head":
        z = head_zoom(src_c, si, a)
        img = Image.fromarray(src_rgb)
        cw, ch = W / z, H / z
        x0 = min(max(540 - cw / 2, 0), W - cw)
        y0 = min(max(1020 - 800 / z, 0), H - ch)  # đưa mặt lên cao, chừa vùng ngực cho chữ
        canvas = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
        canvas.alpha_composite(SHADE)
        if src < HOOK_END:
            draw_hook(canvas, src)
        else:
            draw_captions(canvas, src)
        if src >= DISC_AT:
            canvas.alpha_composite(DISC, (0, 1790))
    elif sc == "h4":
        canvas = ken_burns(draw_h4(src, a, 23.8, 25.6), 1.0 + 0.06 * ease_out(prog), cy=820)
    elif sc.startswith("c_"):
        canvas = ken_burns(draw_card(sc, src, a), 1.0 + 0.04 * ease_out(prog))
    else:
        canvas = BG.copy()
        GRAPHICS[sc](canvas, src)
        if src >= DISC_AT:
            canvas.alpha_composite(DISC, (0, 1790))
    arr = np.asarray(canvas.convert("RGB"))
    for bnd in WHIPS:
        dist = i - bnd
        if -4 <= dist <= 3:
            s = 1 - (abs(dist + 0.5) - 0.5) / 4.0
            k = int(10 + 150 * s)
            shift = int(160 * s * (1 if dist < 0 else -1))
            arr = motion_blur_x(arr, k)
            if shift:
                arr = np.roll(arr, shift, axis=1)
                if shift > 0:
                    arr[:, :shift] = arr[:, shift:shift + 1]
                else:
                    arr[:, shift:] = arr[:, shift - 1:shift]
            break
    return arr


def render_video(tmp_video):
    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", SRC, "-vf",
         "eq=contrast=1.06:brightness=-0.02:saturation=0.97,colorbalance=rs=0.02:bs=-0.03:rm=0.02:bm=-0.02",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", tmp_video],
        stdin=subprocess.PIPE)
    fsize = W * H * 3
    src_idx, cur = -1, None
    for i, (src, si) in enumerate(frames):
        want = int(round(src * FPS))
        while src_idx < want:
            buf = dec.stdout.read(fsize)
            if len(buf) < fsize:
                break
            cur = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            src_idx += 1
        enc.stdin.write(compose(i, cur).tobytes())
        if i % 300 == 0:
            print(f"  frame {i}/{N}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.kill()


# ============================================================ audio
SR = 48000


def tone_env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def sfx_whoosh(dur=0.42):
    n = int(SR * dur)
    x = np.random.default_rng(3).normal(0, 1, n)
    out = np.zeros(n)
    for j, k in enumerate(np.linspace(40, 4, 12).astype(int)):
        a, b = j * n // 12, (j + 1) * n // 12
        out[a:b] = np.convolve(x, np.ones(k) / k, mode="same")[a:b]
    return out * np.sin(np.linspace(0, math.pi, n)) ** 2 * 0.5


def sfx_pop():
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    f = 950 - 450 * t / t[-1]
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * tone_env(n, 0.002, 0.03) * 0.45


def sfx_ding():
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    s = np.sin(2 * math.pi * 1568 * t) + 0.5 * np.sin(2 * math.pi * 2352 * t) + 0.25 * np.sin(2 * math.pi * 3136 * t)
    return s * tone_env(n, 0.003, 0.22) * 0.15


def sfx_boom():
    n = int(SR * 1.1)
    t = np.arange(n) / SR
    f = 70 - 32 * np.clip(t / 0.6, 0, 1)
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) * tone_env(n, 0.003, 0.35)
    click = np.random.default_rng(5).normal(0, 1, n) * tone_env(n, 0.001, 0.012) * 0.3
    return (s + click) * 0.8


def sfx_shutter():
    n = int(SR * 0.12)
    x = np.random.default_rng(9).normal(0, 1, n)
    e = tone_env(n, 0.0005, 0.012) + 0.6 * np.roll(tone_env(n, 0.0005, 0.015), int(SR * 0.055))
    hp = x - np.convolve(x, np.ones(6) / 6, mode="same")
    return hp * e * 0.55


def music(n):
    t = np.arange(n) / SR
    bar = 4 * 60 / 75
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    out = np.zeros(n)
    for b in range(int(n / SR / bar) + 2):
        a = int(b * bar * SR)
        if a >= n:
            break
        L = min(n - a, int(bar * SR * 1.25))
        tt = np.arange(L) / SR
        env = np.minimum(1, tt / 0.8) * np.minimum(1, (bar * 1.25 - tt) / 0.6)
        ch = chords[b % 4]
        s = np.zeros(L)
        for f in ch:
            for det in (-0.6, 0.6):
                s += np.sin(2 * math.pi * (f + det) * tt) * 0.12
        s += np.sin(2 * math.pi * ch[0] / 2 * tt) * 0.22
        step = bar / 8
        for k in range(8):
            st = int(k * step * SR)
            if st >= L:
                break
            m = min(L - st, int(0.5 * SR))
            tp = np.arange(m) / SR
            s[st:st + m] += np.sin(2 * math.pi * ch[[0, 1, 2, 1][k % 4]] * 2 * tp) * np.exp(-tp / 0.12) * 0.10
        out[a:a + L] += s * env
    return out


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


POPS = [158.4, 170.2, 177.6, 209.9, 212.8, 215.9, 249.3, 251.6, 25.6, 55.5, 80.6, 88.8, 116.5]
DINGS = [23.8, 49.3, 80.4, 132.9, 185.4, 227.6, 255.0]


def render_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).astype(np.float64)
    parts, fade = [], int(0.012 * SR)
    for (s, e) in SEGS:
        n = int(round(int(round((e - s) * FPS / SPEED)) * SPEED * SR / FPS))
        seg = a[int(s * SR): int(s * SR) + n].copy()
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        r = np.linspace(0, 1, fade)
        seg[:fade] *= r
        seg[-fade:] *= r[::-1]
        parts.append(seg)
    voice = np.concatenate(parts)
    n = N * SR // FPS  # độ dài output (sau khi tăng tốc)
    write_wav(os.path.join(WORK, "voice.wav"), voice)
    fx = np.zeros(n)

    def add(sig, t, g=1.0):
        st = int(t * SR)
        if st < 0:
            sig, st = sig[-st:], 0
        m = min(len(sig), n - st)
        if m > 0:
            fx[st:st + m] += sig[:m] * g

    add(sfx_boom(), 0.0, 0.9)
    add(sfx_whoosh(0.35), 0.0, 0.6)
    for bnd in WHIPS:
        add(sfx_whoosh(), bnd / FPS - 0.25)
    for t in POPS:
        add(sfx_pop(), out_time(T(t)))
    for t in DINGS:
        add(sfx_ding(), out_time(T(t)))
    for c in CAPTIONS:
        add(sfx_pop(), out_time(T(c[0])), 0.45)
    for t in PROOF_T:  # ảnh nhận định nảy ra: whoosh ngắn + tiếng chụp + pop
        add(sfx_whoosh(0.28), out_time(T(t)) - 0.16, 0.7)
        add(sfx_shutter(), out_time(T(t)), 0.9)
        add(sfx_pop(), out_time(T(t)) + 0.03, 0.6)
    add(sfx_boom(), out_time(T(PROOF_STAMP)), 0.55)
    add(sfx_ding(), out_time(T(PROOF_STAMP)) + 0.05)
    for nm2, cs, ss, ln in PIECES:  # clip chèn bật ra: boom nhẹ + ding
        if nm2 in ("b15", "c32"):
            add(sfx_boom(), out_time(cs), 0.45)
            add(sfx_ding(), out_time(cs + 0.25), 0.8)
    write_wav(os.path.join(WORK, "fx.wav"), fx)
    mus = music(n)
    mus /= np.max(np.abs(mus)) + 1e-9
    fo = int(1.2 * SR)
    mus[-fo:] *= np.linspace(1, 0, fo)
    write_wav(os.path.join(WORK, "music.wav"), mus * 0.5)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", os.path.join(WORK, "voice.wav"), "-i", os.path.join(WORK, "music.wav"),
        "-i", os.path.join(WORK, "fx.wav"), "-filter_complex",
        f"[0]atempo={SPEED},apad,atrim=end_sample={n},highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,asplit=2[v][sc];"
        f"[1]volume=-24dB[m];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];"
        f"[2]volume=-6dB[f];[v][md][f]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-ac", "2", path], check=True)


if __name__ == "__main__":
    print(f"Output: {N} frames ({N / FPS:.2f}s), {len(WHIPS)} transitions")
    if PREVIEW:
        ims = []
        for st in [float(x) for x in PREVIEW.split(",")]:  # thời gian theo video gốc
            i = min(int(round(out_time(st) * FPS)), N - 1)  # PREVIEW: giây của nguồn ghép
            ims.append(Image.fromarray(compose(i, np.asarray(grab(frames[i][0]).convert("RGB")))).resize((270, 480)))
        cols = 6
        sheet = Image.new("RGB", (270 * cols, 480 * math.ceil(len(ims) / cols)))
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * 270, (k // cols) * 480))
        sheet.save(OUT)
        sys.exit(0)
    vtmp, atmp = os.path.join(WORK, "video.mp4"), os.path.join(WORK, "audio.wav")
    render_audio(atmp)
    render_video(vtmp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vtmp, "-i", atmp, "-c:v", "copy", "-c:a", "aac", "-b:a",
                    "192k", "-shortest", "-movflags", "+faststart", OUT], check=True)
    print("Done ->", OUT)
