"""Dựng video "Xu hướng vàng 02/11" theo phong cách dark-premium (nền đen + nhấn vàng).

Cách chạy:
    python render.py <video_goc.mov> <thu_muc_font> <output.mp4>

Cần: ffmpeg, numpy, pillow. Font: Be Vietnam Pro (Black/ExtraBold/Bold/SemiBold/Medium/Italic).
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SRC, FONT_DIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
WORK = os.path.join(os.path.dirname(os.path.abspath(OUT)), "_work")
os.makedirs(WORK, exist_ok=True)

W, H, FPS = 1080, 1920, 30
GOLD = (245, 197, 66)
WHITE = (255, 255, 255)
GREY = (190, 190, 190)

# ---------------------------------------------------------------- timeline
# Các đoạn giữ lại (giây, theo video gốc) - đã cắt khoảng lặng / ngập ngừng.
SEGS = [
    (0.36, 2.29),   # Hello, xin chào cả nhà
    (2.53, 5.82),   # hôm nay là ngày 2/11, mình sẽ cập nhật cho các bạn
    (6.14, 8.62),   # cái xu hướng của vàng trong tuần này
    (8.82, 13.87),  # cũng như xu hướng chính ... vàng sẽ chạy như thế nào
    (14.07, 17.89), # và sẽ có những thông tin, tin tức kinh tế vĩ mô nào
    (18.77, 21.07), # mà các bạn cần phải chú ý trong thời gian tới
    (24.06, 26.75), # Ok, bây giờ chúng ta sẽ đi vào những thông tin chính nhá
]

frames = []  # (src_time, seg_index)
for si, (a, b) in enumerate(SEGS):
    n = int(round((b - a) * FPS))
    for k in range(n):
        frames.append((a + k / FPS, si))
N = len(frames)
DUR = N / FPS


def scene_of(src, si):
    if si in (0, 1):
        return "head"
    if si in (2, 3) and src < 12.20:
        return "g1"
    if si == 3:
        return "head"
    if si == 4:
        return "g2"
    return "head"


def zoom_of(src, si):
    base = {0: 1.08, 1: 1.2, 3: 1.2, 5: 1.1, 6: 1.24}.get(si, 1.08)
    a, b = SEGS[si]
    if si == 3:
        a = 12.20
    p = (src - a) / max(b - a, 1e-3)
    z = base * (1.0 + 0.03 * p)  # Ken Burns nhẹ
    if si == 6:  # punch-in ở câu chốt
        q = min(1.0, (src - a) / 0.18)
        z *= 1.0 + 0.10 * (1 - ease_out(q))
    return z


SCENES = [scene_of(*f) for f in frames]
# Ranh giới đổi cảnh head <-> graphic => whip-pan
WHIPS = [i for i in range(1, N) if SCENES[i] != SCENES[i - 1]]
OUT_T = {}  # mốc src -> thời gian output (cho SFX)


def out_time(src):
    best = None
    for i, (s, si) in enumerate(frames):
        if s >= src - 1e-6:
            return i / FPS
        best = i
    return best / FPS


# ---------------------------------------------------------------- helpers
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


def text_w(t, f, track=0):
    if not track:
        return f.getlength(t)
    return sum(f.getlength(c) for c in t) + track * (len(t) - 1)


def draw_tracked(d, xy, t, f, fill, track):
    x, y = xy
    for c in t:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + track


def parse_rich(line):
    """'MÌNH SẼ *CẬP NHẬT*' -> [(text, gold?)]"""
    out, gold = [], False
    for i, part in enumerate(line.split("*")):
        if part:
            out.append((part, gold))
        gold = not gold
    return out


def glow(layer, radius=14, strength=1.6, color=None):
    """Trả về lớp glow (RGBA) từ alpha của layer."""
    small = layer.resize((layer.width // 2, layer.height // 2), Image.BILINEAR)
    a = small.split()[3].filter(ImageFilter.GaussianBlur(radius / 2))
    a = a.point(lambda v: min(255, int(v * strength)))
    if color is None:
        rgb = small.convert("RGB").filter(ImageFilter.GaussianBlur(radius / 2))
        g = Image.merge("RGBA", (*rgb.split(), a))
    else:
        g = Image.new("RGBA", small.size, color + (0,))
        g.putalpha(a)
    return g.resize(layer.size, Image.BILINEAR)


def shadowed(layer, radius=10, opacity=0.85, offset=(0, 5)):
    a = layer.split()[3].filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------ text blocks
_cache = {}


def rich_block(lines, sizes, weight="Black", pad=40, line_gap=8, shadow=True):
    """Khối chữ nhiều dòng căn giữa, đoạn *...* màu vàng. Trả về RGBA."""
    key = ("rb", tuple(lines), tuple(sizes), weight, shadow)
    if key in _cache:
        return _cache[key]
    rows = []
    for ln, sz in zip(lines, sizes):
        f = font(weight, sz)
        toks = parse_rich(ln)
        w = sum(f.getlength(t) for t, _ in toks)
        rows.append((toks, f, w, sz))
    bw = int(max(r[2] for r in rows)) + pad * 2
    bh = int(sum(r[3] * 1.18 + line_gap for r in rows)) + pad * 2
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for toks, f, w, sz in rows:
        x = (bw - w) / 2
        for t, g in toks:
            d.text((x, y), t, font=f, fill=GOLD if g else WHITE)
            x += f.getlength(t)
        y += sz * 1.18 + line_gap
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


# ------------------------------------------------------------- icons
def icon(d, kind, x, y, s, col):
    lw = max(3, s // 9)
    if kind == "calendar":
        d.rounded_rectangle([x, y + s * 0.12, x + s, y + s], radius=s * 0.15, outline=col, width=lw)
        d.line([x, y + s * 0.38, x + s, y + s * 0.38], fill=col, width=lw)
        d.line([x + s * 0.28, y, x + s * 0.28, y + s * 0.25], fill=col, width=lw)
        d.line([x + s * 0.72, y, x + s * 0.72, y + s * 0.25], fill=col, width=lw)
    elif kind == "compass":
        d.ellipse([x, y, x + s, y + s], outline=col, width=lw)
        c = (x + s / 2, y + s / 2)
        d.polygon([(c[0] + s * 0.22, c[1] - s * 0.22), (c[0] + s * 0.07, c[1] + s * 0.07),
                   (c[0] - s * 0.22, c[1] + s * 0.22), (c[0] - s * 0.07, c[1] - s * 0.07)], fill=col)
    elif kind == "globe":
        d.ellipse([x, y, x + s, y + s], outline=col, width=lw)
        d.ellipse([x + s * 0.28, y, x + s * 0.72, y + s], outline=col, width=lw)
        d.line([x, y + s / 2, x + s, y + s / 2], fill=col, width=lw)


def node_img(label, kind=None, sub=None, gold=False, qmark=False):
    key = ("node", label, kind, sub, gold, qmark)
    if key in _cache:
        return _cache[key]
    col = GOLD if gold else WHITE
    pad = 90  # chừa chỗ cho glow
    if qmark:
        bw, bh = 96, 96
        f = font("Black", 52)
    else:
        f = font("Black", 50)
        isz = 44 if kind else 0
        bw = int(f.getlength(label) + (isz + 22 if kind else 0) + 72)
        bh = 108
    fsub = font("Medium", 30)
    sub_w = int(fsub.getlength(sub)) if sub else 0
    cw = max(bw, sub_w) + pad * 2
    ch = bh + (56 if sub else 0) + pad * 2
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bx, by = (cw - bw) / 2, pad
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=(12, 12, 14, 235), outline=col, width=4)
    if qmark:
        tw = f.getlength("?")
        d.text((bx + (bw - tw) / 2, by + 12), "?", font=f, fill=WHITE)
    else:
        x = bx + 36
        if kind:
            icon(d, kind, x, by + (bh - 44) / 2, 44, col)
            x += 44 + 22
        d.text((x, by + 18), label, font=f, fill=col)
    if sub:
        d.text(((cw - sub_w) / 2, by + bh + 12), sub, font=fsub, fill=(200, 200, 200, 210))
    if gold:
        g = glow(img, radius=26, strength=1.3, color=GOLD)
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.alpha_composite(g)
        out.alpha_composite(img)
        img = out
    _cache[key] = (img, by + bh / 2 - ch / 2)  # offset tâm hộp so với tâm ảnh
    return _cache[key]


def place_node(canvas, label, cy, t_in, now, **kw):
    """Hiện node có tâm hộp tại (540, cy); pop-in tại t_in (giây src)."""
    if now < t_in:
        return
    img, off = node_img(label, **kw)
    p = (now - t_in) / 0.30
    paste_center(canvas, img, 540, cy - off, scale=0.82 + 0.18 * ease_back(p), alpha=ease_out(p * 1.6))


def header(canvas, text, now, t_in, y=330):
    a = ease_out((now - t_in) / 0.4)
    if a <= 0:
        return
    f = font("SemiBold", 30)
    t = text.upper()
    tw = text_w(t, f, 14)
    lay = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    draw_tracked(ImageDraw.Draw(lay), ((W - tw) / 2, 8), t, f, GREY + (int(255 * a),), 14)
    canvas.alpha_composite(lay, (0, y - int(14 * (1 - a))))


def connector(canvas, x, y1, y2, now, t0, dur=0.3, dashed=False, gold=False):
    p = ease_out((now - t0) / dur)
    if p <= 0:
        return
    d = ImageDraw.Draw(canvas)
    yend = y1 + (y2 - y1) * p
    col = (GOLD if gold else (220, 220, 220)) + (230,)
    if dashed:
        yy = y1
        while yy < yend:
            d.line([x, yy, x, min(yy + 12, yend)], fill=col, width=3)
            yy += 22
    else:
        d.line([x, y1, x, yend], fill=col, width=3)
    # chấm sáng chạy dọc đường nối (giống bản mẫu)
    if p >= 1:
        ph = ((now - t0) * 0.9) % 1.0
        cy = y1 + (y2 - y1) * ph
        d.ellipse([x - 6, cy - 6, x + 6, cy + 6], fill=(255, 236, 170, 255))
    else:
        d.ellipse([x - 7, yend - 7, x + 7, yend + 7], fill=(255, 236, 170, 255))


# ----------------------------------------------------------- backgrounds
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - 540) / 700) ** 2 + ((yy - 980) / 1000) ** 2)
    v = np.clip(1 - r, 0, 1) ** 1.6
    base = np.array([7, 7, 9], np.float32)
    hi = np.array([34, 33, 36], np.float32)
    img = base + (hi - base) * v[..., None]
    rng = np.random.default_rng(1)
    img += rng.normal(0, 1.4, img.shape[:2])[..., None]  # chống banding
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


BG = make_bg()


def make_head_shade():
    """Gradient tối ở đáy + vignette nhẹ cho cảnh người nói."""
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    bottom = np.clip((yy - 0.48) / 0.52, 0, 1) ** 1.4 * 0.72
    vig = np.clip((xx ** 2) * 0.35 + ((yy - 0.45) * 1.6) ** 2 * 0.18, 0, 1) * 0.55
    a = np.clip(bottom + vig, 0, 0.85)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


SHADE = make_head_shade()


def make_banner():
    """Banner trên cùng cho hook (gradient đen -> nâu, chữ vàng ánh kim)."""
    bh = 300
    arr = np.zeros((bh, W, 4), np.uint8)
    t = np.linspace(0, 1, bh)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    arr[..., 0] = (12 + 40 * x * (1 - t * 0.3)).astype(np.uint8)
    arr[..., 1] = (10 + 26 * x * (1 - t * 0.3)).astype(np.uint8)
    arr[..., 2] = (8 + 10 * x).astype(np.uint8)
    arr[..., 3] = 245
    img = Image.fromarray(arr, "RGBA")
    d = ImageDraw.Draw(img)
    d.line([0, bh - 3, W, bh - 3], fill=GOLD + (200,), width=3)
    f1 = font("SemiBold", 30)
    draw_tracked(d, (70, 70), "CẬP NHẬT THỊ TRƯỜNG · 02/11", f1, (225, 200, 150), 6)
    # chữ vàng gradient
    f2 = font("Black", 112)
    txt = "GIÁ VÀNG"
    m = Image.new("L", (W, bh), 0)
    ImageDraw.Draw(m).text((66, 112), txt, font=f2, fill=255)
    gy = np.linspace(0, 1, bh)[:, None] * np.ones((1, W))
    grad = np.zeros((bh, W, 3), np.float32)
    top, bot = np.array([255, 233, 160]), np.array([196, 140, 40])
    grad[:] = top + (bot - top) * np.clip((gy - 0.35) / 0.45, 0, 1)[..., None]
    gimg = Image.fromarray(grad.astype(np.uint8)).convert("RGBA")
    gimg.putalpha(m)
    img.alpha_composite(shadowed(gimg, radius=6, opacity=0.8, offset=(0, 3)))
    return img


BANNER = make_banner()


def make_disclaimer():
    f = font("Medium", 26)
    t = "Nội dung mang tính tham khảo, không phải lời khuyên đầu tư"
    img = Image.new("RGBA", (W, 60), (0, 0, 0, 0))
    ImageDraw.Draw(img).text(((W - f.getlength(t)) / 2, 12), t, font=f, fill=(230, 230, 230, 200))
    return shadowed(img, radius=4, opacity=0.9, offset=(0, 2))


DISC = make_disclaimer()


# ------------------------------------------------------------- captions
CAPTIONS = [  # (src_start, src_end, lines, sizes)
    (4.06, 5.82, ["MÌNH SẼ *CẬP NHẬT*", "CHO CÁC BẠN"], [70, 56]),
    (12.20, 13.87, ["VÀNG SẼ CHẠY", "*NHƯ THẾ NÀO?*"], [64, 84]),
    (18.77, 20.02, ["CÁC BẠN CẦN PHẢI", "*CHÚ Ý*"], [60, 92]),
    (20.02, 21.07, ["TRONG", "*THỜI GIAN TỚI*"], [56, 80]),
    (24.06, 24.50, ["OK!"], [120]),
    (24.50, 26.75, ["BÂY GIỜ ĐI VÀO", "*THÔNG TIN CHÍNH*"], [60, 82]),
]


def draw_captions(canvas, src):
    for a, b, lines, sizes in CAPTIONS:
        if a <= src < b:
            img = rich_block(lines, sizes)
            p = (src - a) / 0.16
            paste_center(canvas, img, 540, 1440, scale=0.88 + 0.12 * ease_back(p), alpha=ease_out(p * 1.5))


def draw_hook(canvas, src):
    t = src - 0.36
    # banner trượt xuống
    p = ease_out(t / 0.35)
    canvas.alpha_composite(BANNER, (0, int(-300 * (1 - p))))
    if src > 4.06:
        return
    rows = [
        (["XU HƯỚNG"], [104], 1330, 0.00),
        (["*VÀNG*"], [170], 1470, 0.10),
        (["TUẦN NÀY"], [104], 1610, 0.20),
        (["*+ TIN VĨ MÔ* CẦN CHÚ Ý"], [46], 1715, 0.45),
    ]
    for lines, sizes, cy, d in rows:
        img = rich_block(lines, sizes, pad=30)
        q = (t - d) / 0.25
        paste_center(canvas, img, 540, cy, scale=0.75 + 0.25 * ease_back(q), alpha=ease_out(q * 1.5))


# ------------------------------------------------------------- graphics
def draw_g1(canvas, src):
    header(canvas, "Xu hướng vàng · 02/11", src, 6.14, y=420)
    y1, y2, y3 = 760, 1060, 1360
    act2 = src >= 9.82
    place_node(canvas, "TUẦN NÀY", y1, 6.45, src, kind="calendar", sub="xu hướng ngắn hạn", gold=not act2)
    connector(canvas, 540, y1 + 92, y2 - 58, src, 9.55)
    place_node(canvas, "XU HƯỚNG CHÍNH", y2, 9.82, src, kind="compass", sub="thời gian sắp tới", gold=act2 and src < 11.15)
    connector(canvas, 540, y2 + 92, y3 - 50, src, 10.95, dashed=True, gold=True)
    if src >= 11.15:
        place_node(canvas, "?", y3, 11.15, src, qmark=True, gold=True, sub="vàng sẽ chạy thế nào?")


def draw_g2(canvas, src):
    header(canvas, "Tin tức vĩ mô cần chú ý", src, 14.07, y=420)
    if src >= 14.35:
        img = rich_block(["NHỮNG THÔNG TIN"], [60], weight="ExtraBold", shadow=False)
        p = (src - 14.35) / 0.3
        paste_center(canvas, img, 540, 580, scale=0.9 + 0.1 * ease_out(p), alpha=ease_out(p))
    if src >= 16.58:  # gõ chữ từng ký tự
        full = "KINH TẾ VĨ MÔ"
        n = min(len(full), int((src - 16.58) / 0.035) + 1)
        img = rich_block([f"*{full[:n]}*"], [104], shadow=False)
        g = glow(img, radius=24, strength=1.0, color=GOLD)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        lay.alpha_composite(g)
        lay.alpha_composite(img)
        paste_center(canvas, lay, 540, 700)
    ys = [920, 1130, 1340]
    ts = [15.34, 16.14, 16.94]
    for i, (y, t0) in enumerate(zip(ys, ts)):
        if i:
            connector(canvas, 540, ys[i - 1] + 50, y - 50, src, t0 - 0.2, dur=0.2, dashed=True)
        place_node(canvas, "?", y, t0, src, qmark=True, gold=(i == 2))


# --------------------------------------------------------------- video io
def motion_blur_x(arr, k):
    if k < 2:
        return arr
    a = arr.astype(np.float32)
    c = np.cumsum(np.pad(a, ((0, 0), (k, 0), (0, 0)), mode="edge"), axis=1)
    out = (c[:, k:] - c[:, :-k]) / k
    return out.astype(np.uint8)


def compose(i, src_rgb):
    src, si = frames[i]
    sc = SCENES[i]
    if sc == "head":
        z = zoom_of(src, si)
        img = Image.fromarray(src_rgb)
        if z > 1.001:
            cw, ch = W / z, H / z
            # đẩy khuôn mặt (y~1000 ở video gốc) lên ~800 trên khung output
            x0 = min(max(540 - cw / 2, 0), W - cw)
            y0 = min(max(1000 - 800 / z, 0), H - ch)
            img = img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        canvas = img.convert("RGBA")
        canvas.alpha_composite(SHADE)
        if si in (0, 1):
            draw_hook(canvas, src)
        draw_captions(canvas, src)
        if si == 6:
            canvas.alpha_composite(DISC, (0, 1780))
    else:
        canvas = BG.copy()
        (draw_g1 if sc == "g1" else draw_g2)(canvas, src)
    arr = np.asarray(canvas.convert("RGB"))
    # whip-pan quanh ranh giới đổi cảnh
    for b in WHIPS:
        dist = i - b  # âm: trước cắt, dương: sau cắt
        if -4 <= dist <= 3:
            s = 1 - (abs(dist + 0.5) - 0.5) / 4.0
            k = int(10 + 150 * s)
            shift = int((180 * s) * (1 if dist < 0 else -1))
            arr = np.roll(motion_blur_x(arr, k), shift, axis=1)
            break
    return arr


def render_video(tmp_video):
    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", SRC, "-vf",
         "eq=contrast=1.07:brightness=-0.025:saturation=0.96,colorbalance=rs=0.03:gs=0.01:bs=-0.03:rm=0.02:bm=-0.02",
         "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)
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
        if i % 60 == 0:
            print(f"  frame {i}/{N}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()


# ---------------------------------------------------------------- audio
SR = 48000


def tone_env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def sfx_whoosh(dur=0.45):
    n = int(SR * dur)
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, n)
    # quét bộ lọc: trộn low-pass động bằng moving average có độ dài thay đổi
    out = np.zeros(n)
    for j, k in enumerate(np.linspace(40, 4, 12).astype(int)):
        a, b = j * n // 12, (j + 1) * n // 12
        seg = np.convolve(x, np.ones(k) / k, mode="same")[a:b]
        out[a:b] = seg
    env = np.sin(np.linspace(0, math.pi, n)) ** 2
    return out * env * 0.55


def sfx_pop():
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    f = 950 - 450 * t / t[-1]
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * tone_env(n, 0.002, 0.03) * 0.45


def sfx_ding():
    n = int(SR * 0.9)
    t = np.arange(n) / SR
    s = np.sin(2 * math.pi * 1568 * t) + 0.5 * np.sin(2 * math.pi * 2352 * t) + 0.25 * np.sin(2 * math.pi * 3136 * t)
    return s * tone_env(n, 0.003, 0.22) * 0.16


def sfx_boom():
    n = int(SR * 1.1)
    t = np.arange(n) / SR
    f = 70 - 32 * np.clip(t / 0.6, 0, 1)
    s = np.sin(2 * math.pi * np.cumsum(f) / SR) * tone_env(n, 0.003, 0.35)
    rng = np.random.default_rng(5)
    click = rng.normal(0, 1, n) * tone_env(n, 0.001, 0.012) * 0.3
    return (s + click) * 0.8


def music(n):
    """Pad ambient nhẹ (Am - F - C - G), 75 BPM, tự tạo - không bản quyền."""
    t = np.arange(n) / SR
    bar = 4 * 60 / 75
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0 * 1.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    out = np.zeros(n)
    nb = int(n / SR / bar) + 2
    for b in range(nb):
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
        s += np.sin(2 * math.pi * ch[0] / 2 * tt) * 0.22  # bass
        # pluck arpeggio 8th notes
        step = bar / 8
        for k in range(8):
            st = int(k * step * SR)
            if st >= L:
                break
            m = min(L - st, int(0.5 * SR))
            tp = np.arange(m) / SR
            f = ch[[0, 1, 2, 1][k % 4]] * 2
            s[st:st + m] += np.sin(2 * math.pi * f * tp) * np.exp(-tp / 0.12) * 0.10
        out[a:a + L] += s * env
    return out


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], 1) if x.ndim == 1 else x
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


def render_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).astype(np.float64)
    parts = []
    fade = int(0.012 * SR)
    for (s, e) in SEGS:
        n = int(round((e - s) * FPS)) * SR // FPS
        seg = a[int(s * SR): int(s * SR) + n].copy()
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        ramp = np.linspace(0, 1, fade)
        seg[:fade] *= ramp
        seg[-fade:] *= ramp[::-1]
        parts.append(seg)
    voice = np.concatenate(parts)
    n = len(voice)
    write_wav(os.path.join(WORK, "voice.wav"), voice)

    fx = np.zeros(n)

    def add(sig, t, gain=1.0):
        st = int(t * SR)
        if st < 0:
            sig, st = sig[-st:], 0
        m = min(len(sig), n - st)
        if m > 0:
            fx[st:st + m] += sig[:m] * gain

    add(sfx_boom(), 0.0, 0.9)
    add(sfx_whoosh(0.35), 0.0, 0.6)
    for b in WHIPS:
        add(sfx_whoosh(), b / FPS - 0.26)
    for t in (6.45, 9.82, 15.34, 16.14):
        add(sfx_pop(), out_time(t))
    for t in (11.15, 16.94):
        add(sfx_ding(), out_time(t))
    add(sfx_ding(), out_time(16.58), 0.6)
    add(sfx_pop(), out_time(24.06), 1.2)
    add(sfx_pop(), out_time(4.06), 0.7)
    for c in CAPTIONS[1:4] + CAPTIONS[5:]:
        add(sfx_pop(), out_time(c[0]), 0.5)
    write_wav(os.path.join(WORK, "fx.wav"), fx)

    mus = music(n)
    mus /= np.max(np.abs(mus)) + 1e-9
    fo = int(0.6 * SR)
    mus[-fo:] *= np.linspace(1, 0, fo)
    write_wav(os.path.join(WORK, "music.wav"), mus * 0.5)

    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-i", os.path.join(WORK, "voice.wav"), "-i", os.path.join(WORK, "music.wav"), "-i", os.path.join(WORK, "fx.wav"),
        "-filter_complex",
        "[0]highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,asplit=2[v][sc];"
        "[1]volume=-23dB[m];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[md];"
        "[2]volume=-6dB[f];"
        "[v][md][f]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-ac", "2", path], check=True)


if __name__ == "__main__":
    print(f"Output: {N} frames ({DUR:.2f}s), whips at {[round(b / FPS, 2) for b in WHIPS]}")
    vtmp = os.path.join(WORK, "video.mp4")
    atmp = os.path.join(WORK, "audio.wav")
    render_audio(atmp)
    render_video(vtmp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vtmp, "-i", atmp, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], check=True)
    print("Done ->", OUT)
