"""Tạo ảnh bìa (banner) TikTok 1080x1920 cho video: người tách nền + chart + chữ 3D lớn + checklist.

Chạy:  .venv-video/bin/python -I edit/cover.py <ten_bia> <out.png>
Cần:   pip install mediapipe ; model selfie_multiclass_256x256.tflite đặt ở work/selfie.tflite
Nội dung từng bìa nằm trong COVERS bên dưới (ảnh người lấy từ khung hình video gốc).
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "edit", "fonts")
ASSET = os.path.join(ROOT, "edit", "assets", "thung-3850")
W, H = 1080, 1920
GOLD = (245, 197, 66)
RED = (235, 45, 55)


def font(w, s):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"BeVietnamPro-{w}.ttf"), s)


def frame(video, t):
    out = os.path.join(ROOT, "work", f"_cov_{os.path.basename(video)}_{t}.png")
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", out], check=True)
    return Image.open(out).convert("RGB")


def cutout(img):
    """Tách người khỏi nền bằng MediaPipe (selfie multiclass)."""
    import mediapipe as mp
    seg = mp.tasks.vision.ImageSegmenter.create_from_options(mp.tasks.vision.ImageSegmenterOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=os.path.join(ROOT, "work", "selfie.tflite")),
        output_confidence_masks=True))
    res = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(img)))
    bg = np.squeeze(res.confidence_masks[0].numpy_view()).copy()
    seg.close()
    a = np.clip((1 - bg - 0.15) / 0.7, 0, 1)
    m = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    out = img.convert("RGBA")
    out.putalpha(m)
    return out


def chart_bg(name, box, tint, dark=0.45):
    im = Image.open(os.path.join(ASSET, name + ".png")).convert("RGB")
    im = im.resize((2000, 923) if im.width > im.height else (923, 2000), Image.LANCZOS).crop(box)
    sc = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
    a = np.asarray(im).astype(np.float32) * dark
    a = a * 0.6 + np.array(tint, np.float32) * 0.18 * (a.mean(2, keepdims=True) / 60 + 0.4)
    yy = np.linspace(0, 1, H)[:, None, None]
    a = a * (1 - 0.55 * np.clip((yy - 0.55) / 0.45, 0, 1))  # tối dần xuống đáy cho chữ nổi
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


def glow_of(layer, r, col, k=1.6):
    a = layer.split()[3].filter(ImageFilter.GaussianBlur(r)).point(lambda v: min(255, int(v * k)))
    g = Image.new("RGBA", layer.size, col + (0,))
    g.putalpha(a)
    return g


def text3d(text, size, top, bot, depth=14, stroke=10, rot=-4, weight="Black"):
    """Chữ nổi 3D: tô gradient, viền đen dày, khối đùn xuống phải, ánh sáng viền."""
    f = font(weight, size)
    l, t, r, b = f.getbbox(text)
    pad = 60
    cw, ch = r - l + pad * 2 + depth, b - t + pad * 2 + depth

    def mask(st=0):
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).text((pad - l, pad - t), text, font=f, fill=255, stroke_width=st, stroke_fill=255)
        return m
    m0, ms = mask(), mask(stroke)
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ext = tuple(int(c * 0.35) for c in bot)
    for k in range(depth, 0, -1):  # khối đùn
        layer = Image.new("RGBA", (cw, ch), (8, 6, 6, 255))
        layer.putalpha(ms)
        out.alpha_composite(layer, (k, k))
        if k == depth:
            continue
    sl = Image.new("RGBA", (cw, ch), ext + (255,))
    sl.putalpha(ms)
    out.alpha_composite(sl, (depth // 2, depth // 2))
    blk = Image.new("RGBA", (cw, ch), (10, 8, 8, 255))
    blk.putalpha(ms)
    out.alpha_composite(blk)
    gy = np.linspace(0, 1, ch)[:, None]
    yb0, yb1 = (pad) / ch, (pad + b - t) / ch
    p = np.clip((gy - yb0) / max(yb1 - yb0, 1e-3), 0, 1)
    top_, bot_ = np.array(top, np.float32), np.array(bot, np.float32)
    mid = np.clip(1 - np.abs(p - 0.42) / 0.12, 0, 1)[..., None] * 0.35  # vệt sáng ngang kiểu kim loại
    grad = top_ + (bot_ - top_) * p[..., None]
    grad = grad + (255 - grad) * mid
    gimg = Image.fromarray(np.clip(np.broadcast_to(grad, (ch, cw, 3)), 0, 255).astype(np.uint8)).convert("RGBA")
    gimg.putalpha(m0)
    out.alpha_composite(gimg)
    hl = Image.new("RGBA", (cw, ch), (255, 255, 255, 0))  # viền sáng mảnh phía trên
    edge = m0.filter(ImageFilter.FIND_EDGES).point(lambda v: 120 if v > 40 else 0)
    hl.putalpha(Image.fromarray(np.asarray(edge)))
    out.alpha_composite(hl, (0, -1))
    if rot:
        out = out.rotate(rot, Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh.alpha_composite(glow_of(out, 18, (0, 0, 0), 1.3), (0, 10))
    sh.alpha_composite(out)
    return sh


def place(canvas, img, cx, cy, maxw=1040):
    if img.width > maxw:
        img = img.resize((maxw, int(img.height * maxw / img.width)), Image.LANCZOS)
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def tag(canvas, text, x, y, size, fill, fg=(255, 255, 255), down=False, rot=0):
    f = font("Black", size)
    tw = f.getlength(text)
    extra = size * 0.9 if down else 0
    w, h = int(tw + size * 1.0 + extra), int(size * 1.6)
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=int(size * 0.3), fill=fill + (245,))
    x0 = 20 + size * 0.5
    if down:
        s = size * 0.6
        cy = 20 + h / 2
        d.polygon([(x0, cy - s / 2), (x0 + s, cy - s / 2), (x0 + s / 2, cy + s / 2)], fill=fg)
        x0 += extra
    d.text((x0, 20 + h / 2), text, font=f, fill=fg, anchor="lm")
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    canvas.alpha_composite(glow_of(im, 14, (0, 0, 0), 1.0), (int(x), int(y) + 6))
    canvas.alpha_composite(im, (int(x), int(y)))


def checklist(canvas, title, items, x, y, w, accent, size=30):
    f, ft = font("ExtraBold", size), font("Black", size + 4)
    lh = int(size * 1.9)
    h = int(size * 2.2) + lh * len(items) + 20
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=(10, 10, 12, 215), outline=accent + (255,), width=3)
    d.text((24, 18), title, font=ft, fill=accent)
    yy = int(size * 2.2) + 6
    for it in items:
        b = size * 1.1
        d.rounded_rectangle([24, yy, 24 + b, yy + b], radius=6, outline=accent, width=3)
        d.line([(30, yy + b * 0.52), (24 + b * 0.42, yy + b * 0.8), (24 + b * 0.95, yy + b * 0.12)],
               fill=(90, 220, 120), width=6, joint="curve")
        d.text((24 + b + 16, yy + b / 2), it, font=f, fill=(240, 240, 240), anchor="lm")
        yy += lh
    canvas.alpha_composite(glow_of(im, 16, accent, 0.6), (int(x), int(y)))
    canvas.alpha_composite(im, (int(x), int(y)))


def arrow(canvas, x0, y0, x1, y1, col, wdt=34):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ang = math.atan2(y1 - y0, x1 - x0)
    hx, hy = x1 - math.cos(ang) * wdt * 1.6, y1 - math.sin(ang) * wdt * 1.6
    d.line([x0, y0, hx, hy], fill=col + (255,), width=wdt)
    px, py = -math.sin(ang), math.cos(ang)
    d.polygon([(x1, y1), (hx + px * wdt * 1.5, hy + py * wdt * 1.5), (hx - px * wdt * 1.5, hy - py * wdt * 1.5)],
              fill=col + (255,))
    canvas.alpha_composite(glow_of(lay, 22, col, 1.4))
    canvas.alpha_composite(lay)


def person(canvas, video, t, h_target, cx, top, rim):
    p = cutout(frame(video, t))
    bb = p.split()[3].point(lambda v: 255 if v > 60 else 0).getbbox()
    p = p.crop(bb)
    sc = h_target / p.height
    p = p.resize((int(p.width * sc), h_target), Image.LANCZOS)
    arr = np.asarray(p).astype(np.float32)  # tăng tương phản nhẹ cho nổi trên nền tối
    arr[..., :3] = np.clip((arr[..., :3] - 128) * 1.08 + 128 + 4, 0, 255)
    p = Image.fromarray(arr.astype(np.uint8), "RGBA")
    x = int(cx - p.width / 2)
    canvas.alpha_composite(glow_of(p, 26, rim, 1.2), (x, top))
    canvas.alpha_composite(p, (x, top))


VIDEO1 = os.path.join(ROOT, "work", "v1.mov")


def cover_thung(c):
    c.alpha_composite(chart_bg("w_zoom", (560, 60, 1700, 700), RED, 0.55))
    arrow(c, 760, 330, 960, 760, RED)
    person(c, VIDEO1, 128, 1380, 410, 540, (255, 70, 60))
    tag(c, "GIÁ VÀNG · 18/11", 40, 270, 38, (20, 20, 22), fg=GOLD)
    tag(c, "XAU/USD 3.766  -2,15%", 440, 350, 38, RED, down=True, rot=4)
    checklist(c, "VÌ SAO THỦNG?", ["Vỡ vùng hợp lưu", "Fed tăng lãi nhiều lần", "USD mạnh nhất 19 tháng"],
              590, 640, 460, GOLD, size=28)
    place(c, text3d("VÀNG THỦNG", 150, (255, 255, 255), (200, 200, 205), rot=-4), 540, 1180)
    place(c, text3d("3.850", 330, (255, 236, 150), (205, 130, 20), depth=20, stroke=14, rot=-4), 540, 1370)
    place(c, text3d("VỀ 3.000$?", 170, (255, 120, 110), (190, 20, 30), rot=-4), 560, 1560)


def cover_tichsan(c):
    c.alpha_composite(chart_bg("w_wide", (980, 0, 1700, 700), GOLD, 0.5))
    person(c, VIDEO1, 220, 1380, 480, 540, GOLD)
    tag(c, "VÀNG VỀ ĐÁY HƠN 1 NĂM", 40, 270, 38, RED, down=True)
    tag(c, "SJC 134,2 – 137 TRIỆU", 40, 370, 34, (20, 20, 22), fg=GOLD)
    checklist(c, "CẦN BIẾT", ["Chênh mua–bán 3–4 triệu", "Bán lại mất 2–3%", "Giữ dài hạn, đừng lướt"],
              560, 470, 500, GOLD, size=28)
    place(c, text3d("NGƯỜI", 150, (255, 255, 255), (200, 200, 205), rot=-4), 360, 1150)
    place(c, text3d("TÍCH SẢN", 230, (255, 236, 150), (205, 130, 20), depth=18, stroke=13, rot=-4), 540, 1350)
    place(c, text3d("CẦN BIẾT GÌ?", 160, (255, 120, 110), (190, 20, 30), rot=-4), 560, 1555)


COVERS = {"thung-3850": cover_thung, "tich-san": cover_tichsan}

if __name__ == "__main__":
    name, out = sys.argv[1], sys.argv[2]
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    COVERS[name](canvas)
    canvas.convert("RGB").save(out, quality=95)
    print("->", out)
