"""Dựng video "Vàng tuần 9–15/11 – Phần 2" (tốc độ 1.1x).
Nguồn: work/n/clean1.mp4 (bản quay 720p nâng 1080x1920, 30fps).
Các đoạn nhìn xuống kịch bản (edit/find_lookdown.py) được thay bằng đồ họa motion. theo phong cách dark-premium nền đen + nhấn vàng.

Chạy:  python render_v2.py <video_goc.mov> <thu_muc_font_BeVietnamPro> <output.mp4>
Cần:   ffmpeg, numpy, pillow.

Mọi mốc thời gian trong file này tính theo GIÂY CỦA VIDEO GỐC (src). Script tự cắt khoảng lặng
và tự quy đổi sang thời gian output.
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
WORK = os.path.join(os.path.dirname(os.path.abspath(OUT)), "_work_phan2")
os.makedirs(WORK, exist_ok=True)

W, H, FPS = 1080, 1920, 30
GOLD = (245, 197, 66)
WHITE = (255, 255, 255)
GREY = (190, 190, 190)

# ============================================================ cắt khoảng lặng
SILENCES = []  # dùng CUTS=edit/cuts_vang-0611.json
END = 254.60
SPEED = float(os.environ.get("SPEED", "1.1"))  # tăng tốc toàn video, giữ cao độ giọng
PAD = 0.09
# Nếu có CUTS=<cuts.json> (tạo bởi edit/find_cuts.py: lặng + à/ừm + vấp + lặp từ) thì dùng danh sách đó.
if os.environ.get("CUTS"):
    import json
    CUT_LIST = [(s, e) for s, e, *_ in json.load(open(os.environ["CUTS"]))]
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
    (0.00, 6.40, "head"),
    (6.40, 28.60, "g_kb2"),
    (28.60, 47.40, "head"),
    (47.40, 59.20, "g_ladder"),
    (59.20, 69.40, "head"),
    (69.40, 92.75, "g_ladder"),
    (92.75, 108.60, "head"),
    (108.60, 151.20, "g_vn"),
    (151.20, 155.40, "head"),
    (155.40, 174.00, "g_nfp"),
    (174.00, 178.20, "head"),
    (178.20, 214.80, "g_cal"),
    (214.80, 248.65, "g_fed"),
    (248.65, 999.0, "head"),
]
HOOK_END = 6.40
DISC_AT = 248.65


def scene_at(src):
    for a, b, sc in SCENES:
        if a <= src < b:
            return sc, a, b
    return "head", 0.0, END


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


# ============================================================ captions (cảnh người nói & chart PiP)
CAPTIONS = [
    (28.60, 47.40, ["VÙNG HỖ TRỢ", "*CÁC BẠN CẦN LƯU Ý*"], [60, 88]),
    (59.20, 63.10, ["HỖ TRỢ MẠNH", "*4.010 – 4.020*"], [60, 110]),
    (63.10, 65.70, ["HỖ TRỢ GẦN NHẤT", "*4.030 – 4.040*"], [60, 110]),
    (65.70, 69.40, ["CÒN VÙNG", "*KHÁNG CỰ?*"], [60, 110]),
    (92.75, 98.00, ["SAU ĐÓ VÀNG", "*TIẾP TỤC CẤU TRÚC TĂNG*"], [60, 80]),
    (98.00, 108.60, ["MỤC TIÊU", "*4.250 – 4.300*"], [60, 110]),
    (151.20, 155.40, ["THÔNG TIN *VĨ MÔ*", "*CẦN NẮM TUẦN NÀY*"], [64, 80]),
    (174.00, 178.20, ["USD *ĐANG YẾU*", "DẦU *VẪN GIẢM*"], [76, 76]),
    (248.65, 999.0, ["FOLLOW ĐỂ CẬP NHẬT", "*TIN VÀNG MỚI NHẤT*"], [58, 88]),
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
        (["VÀNG TUẦN 9 – 15/11"], [84], 1320, 0.00),
        (["*KỊCH BẢN GIẢM*"], [120], 1460, 0.12),
        (["PHẦN 2 · *VÀNG TRONG NƯỚC & VĨ MÔ*"], [48], 1600, 0.40),
    ]
    for lines, sizes, cy, d in rows:
        img = rich_block(lines, sizes, pad=30)
        q = (t - d) / 0.25
        paste_center(canvas, img, 540, cy, scale=0.75 + 0.25 * ease_back(q), alpha=ease_out(q * 1.5))


# ============================================================ chart tĩnh có chú thích
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


def band(canvas, y_top, y_bot, now, t_in, x_end=880, dashed=False):
    p = ease_out((now - t_in) / 0.45)
    if p <= 0:
        return
    xe = int(x_end * p)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    pulse = 0.5 + 0.5 * math.sin((now - t_in) * 4)
    d.rectangle([0, y_top, xe, y_bot], fill=GOLD + (int(55 + 35 * pulse),))
    for yy in (y_top, y_bot):
        if dashed:
            for x in range(0, xe, 30):
                d.line([x, yy, min(x + 16, xe), yy], fill=GOLD + (255,), width=3)
        else:
            d.line([0, yy, xe, yy], fill=GOLD + (255,), width=3)
    canvas.alpha_composite(glow(lay, 16, 1.0))
    canvas.alpha_composite(lay)


# Trục giá (đo từ khung hình): y = y0 + (p0 - price) * k
def y_A1(p):
    return 89 + (4280 - p) * 2.827


def y_A2(p):
    return 32 + (4320 - p) * 2.65


STILLS = {}


def chart_still(name):
    if name not in STILLS:
        STILLS[name] = grab({"chartA1": 5.0, "chartA2": 34.0}[name])
    return STILLS[name]


def draw_chartA1(src, a):
    c = chart_still("chartA1").copy()
    pop(c, pill("HỒI KỸ THUẬT", 54, sub="KỊCH BẢN 1"), 330, 360, src, a + 0.05)
    band(c, y_A1(4060) - 2, y_A1(4050) + 2, src, 6.55)
    pop(c, pill("4.050 – 4.060", 44, sub="VÙNG KHÁNG CỰ"), 300, y_A1(4060) - 120, src, 6.75)
    return c


def draw_chartA2(src, a):
    c = chart_still("chartA2").copy()
    pop(c, pill("ĐIỀU CHỈNH", 54, sub="KỊCH BẢN 2"), 330, 360, src, a + 0.05)
    band(c, y_A2(3900), y_A2(3870), src, 36.55)
    pop(c, pill("RETEST 3.870", 44, sub="VÙNG HỖ TRỢ 3.870 – 3.900"), 360, y_A2(3870) + 150, src, 36.8)
    return c


def ken_burns(img, z, cx=560, cy=900):
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


# ============================================================ các cảnh đồ họa
def g_kb2(c, s):
    header(c, "Kịch bản 2 · giảm", s, 6.45)
    place_node(c, "KHÔNG GIỮ ĐƯỢC", 700, 7.5, s, kind="warn", gold=s < 21.5, sub="vùng hỗ trợ")
    big_text(c, "*4.030 – 4.040*", 110, 860, s, 10.8)
    connector(c, 540, 940, 540, 1110, s, 14.1, dur=0.6, dashed=True, gold=True)
    place_node(c, "4.020 – 4.010", 1180, 21.5, s, kind="down", gold=True, sub="vàng có thể giảm về vùng (đô)")


LADDER = [  # (nhãn, giá, kiểu, thời điểm hiện)
    ("KHÁNG CỰ", "4.060 – 4.070", "warn", 72.3),
    ("HỖ TRỢ GẦN NHẤT", "4.030 – 4.040", "shield", 63.2),
    ("HỖ TRỢ MẠNH", "4.010 – 4.020", "shield", 49.4),
]


def g_ladder(c, s):
    header(c, "Sóng tăng ngắn hạn", s, 47.45 if s < 69.4 else 69.45)
    ys = [620, 900, 1180]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.line([150, 540, 150, 1280], fill=(120, 120, 120, 160), width=3)  # trục giá
    for y in ys:
        d.line([150, y, 210, y], fill=(170, 170, 170, 200), width=3)
    c.alpha_composite(lay)
    for (lab, price, kind, t_in), y in zip(LADDER, ys):
        t_in = min(t_in, 69.45) if s >= 69.4 else t_in
        place_node(c, price, y, t_in, s, cx=600, kind=kind, sub=lab.lower(), gold=(lab == "KHÁNG CỰ" and 72.3 <= s < 81.0)
                   or (lab == "HỖ TRỢ GẦN NHẤT" and s >= 81.0) or (lab == "HỖ TRỢ MẠNH" and s < 63.2))
    if 78.0 <= s < 81.0:  # mình nghiêng về kịch bản 1: hồi về 4.030–4.040
        pop(c, pill("MÌNH NGHIÊNG VỀ KỊCH BẢN 1", 40), 540, 1420, s, 78.0)
    if s >= 81.0:
        pop(c, pill("HỒI VỀ 4.030 – 4.040", 44, sub="KỊCH BẢN 1"), 540, 1430, s, 81.0)


def g_vn(c, s):
    header(c, "Giá vàng trong nước", s, 108.65)
    f_h, f_v, f_l = font("SemiBold", 30), font("Black", 64), font("ExtraBold", 40)
    rows = [("VÀNG MIẾNG SJC", "137,9", "140,9", 114.2, 116.8, 119.6, 620),
            ("VÀNG NHẪN SJC", "136,7", "140,7", 121.9, 123.6, 126.2, 920)]
    for name, buy, sell, t0, tb, ts, y in rows:
        if s < t0:
            continue
        p = ease_out((s - t0) / 0.35)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle([70, y - 110, 1010, y + 150], radius=22, fill=(14, 14, 16, int(235 * p)),
                            outline=GOLD + (int(200 * p),), width=3)
        d.text((110, y - 90), name, font=f_l, fill=GOLD + (int(255 * p),))
        for lbl, val, x, tv in (("MUA VÀO", buy, 110, tb), ("BÁN RA", sell, 570, ts)):
            if s >= tv:
                q = ease_out((s - tv) / 0.3)
                d.text((x, y - 20), lbl, font=f_h, fill=(200, 200, 200, int(255 * q)))
                d.text((x, y + 20), val, font=f_v, fill=WHITE + (int(255 * q),))
                d.text((x + f_v.getlength(val) + 14, y + 52), "triệu", font=f_h, fill=(200, 200, 200, int(255 * q)))
        c.alpha_composite(with_glow(lay, 18, 0.5) if p >= 1 else lay)
    big_text(c, "CHÊNH LỆCH MUA – BÁN", 50, 1190, s, 127.4, weight="ExtraBold")
    place_node(c, "3 TRIỆU", 1330, 130.4, s, cx=290, kind="coin", gold=True, sub="vàng miếng / lượng", size=48)
    place_node(c, "4 TRIỆU", 1330, 133.7, s, cx=790, kind="coin", gold=True, sub="vàng nhẫn / lượng", size=48)


def g_nfp(c, s):
    header(c, "Việc làm Mỹ tháng 10", s, 155.45)
    big_text(c, "*+165.000*", 150, 640, s, 160.6)
    big_text(c, "việc làm", 44, 770, s, 161.5, weight="Medium")
    place_node(c, "DỰ BÁO 65.000", 930, 164.4, s, kind="calendar", sub="cao hơn rất nhiều so với dự báo", gold=False)
    connector(c, 540, 1040, 540, 1150, s, 165.6, dur=0.3, dashed=True, gold=True)
    place_node(c, "FED TĂNG LÃI T12: 81 – 84%", 1230, 170.2, s, kind="bank", gold=True, sub="xác suất", size=44)


def g_cal(c, s):
    header(c, "Lịch tin tuần này", s, 178.25)
    place_node(c, "USD YẾU", 560, 178.6, s, cx=300, kind="down", size=42, gold=False)
    place_node(c, "DẦU GIẢM", 560, 179.2, s, cx=780, kind="down", size=42, gold=False)
    place_node(c, "10/11 · 20:30 · CPI T10 MỸ", 860, 187.0, s, kind="calendar", size=42, gold=187.0 <= s < 199.5,
               sub="dự báo 0,3% so với tháng trước · lõi 0,2%" if s >= 192.4 else "chỉ số giá tiêu dùng")
    connector(c, 540, 980, 540, 1080, s, 199.0, dur=0.3)
    place_node(c, "13/11 · 20:30 · PPI T10", 1160, 199.5, s, kind="calendar", size=42, gold=s >= 199.5,
               sub="dự báo 0,4%" if s >= 206.1 else "chỉ số giá sản xuất")


def g_fed(c, s):
    header(c, "Sắp tới", s, 214.85)
    place_node(c, "18–19/12 · HỌP FED", 620, 216.2, s, kind="bank", gold=s < 223.0, size=48)
    place_node(c, "KỲ VỌNG FED TĂNG LÃI", 900, 224.3, s, cx=300, kind="down", size=34, sub="áp lực lên vàng")
    place_node(c, "USD & DẦU YẾU", 900, 229.2, s, cx=790, kind="up", size=34, sub="lực hồi cho vàng")
    connector(c, 300, 990, 500, 1150, s, 230.4, dur=0.4, gold=True)
    connector(c, 790, 990, 580, 1150, s, 230.4, dur=0.4, gold=True)
    place_node(c, "VÀNG ĐANG GIẰNG CO", 1220, 223.0, s, kind="coin", gold=True, size=50)


GRAPHICS = {"g_kb2": g_kb2, "g_ladder": g_ladder, "g_vn": g_vn, "g_nfp": g_nfp, "g_cal": g_cal, "g_fed": g_fed}


# ============================================================ compose
def motion_blur_x(arr, k):
    if k < 2:
        return arr
    a = arr.astype(np.float32)
    c = np.cumsum(np.pad(a, ((0, 0), (k, 0), (0, 0)), mode="edge"), axis=1)
    return ((c[:, k:] - c[:, :-k]) / k).astype(np.uint8)


def compose(i, src_rgb):
    src, si = frames[i]
    sc, a, b = FR_SCENE[i]
    prog = (src - a) / max(b - a, 1e-3)
    if sc == "head":
        z = head_zoom(src, si, a)
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
    elif sc in ("chartA1", "chartA2"):
        base = draw_chartA1(src, a) if sc == "chartA1" else draw_chartA2(src, a)
        canvas = ken_burns(base, 1.0 + 0.07 * ease_out(prog))
    elif sc in ("chartB", "chartC"):
        canvas = Image.fromarray(src_rgb).convert("RGBA")
        canvas = ken_burns(canvas, 1.0 + 0.03 * prog, cy=960)
        if sc == "chartB":
            if src < 82.3:
                pop(canvas, pill("3.900 LÊN 5.600", 50, sub="NHỊP TĂNG NĂM NGOÁI"), 330, 400, src, 80.05)
            else:
                pop(canvas, pill("VÙNG GIÁ FOMO", 52, sub="NHÀ ĐẦU TƯ MUA NHIỀU"), 330, 400, src, 82.3)
        else:
            canvas.alpha_composite(SHADE_LOW)
            draw_captions(canvas, src, cy=1560)
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


POPS = [7.5, 49.4, 63.2, 72.3, 78.0, 81.0, 114.2, 121.9, 116.8, 119.6, 123.6, 126.2, 164.4, 178.6, 179.2, 187.0,
        199.5, 224.3, 229.2]
DINGS = [10.8, 21.5, 130.4, 133.7, 160.6, 170.2, 216.2, 223.0]


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
        add(sfx_pop(), out_time(t))
    for t in DINGS:
        add(sfx_ding(), out_time(t))
    for c in CAPTIONS:
        add(sfx_pop(), out_time(c[0]), 0.45)
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
            i = min(int(round(out_time(st) * FPS)), N - 1)
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
