"""Tìm các đoạn người nói nhìn xuống (đọc kịch bản).

Chạy:  python find_lookdown.py <video> <face_landmarker.task> <out.json> [fps=5]
Dùng MediaPipe FaceLandmarker: điểm "nhìn xuống" = trung bình blendshape eyeLookDown trái/phải
cộng độ cúi đầu (pitch). Ghi ra danh sách mẫu (t, down, pitch) + các đoạn liên tục nhìn xuống.
Cài thêm: pip install mediapipe ; model: storage.googleapis.com/mediapipe-models/face_landmarker/...
"""
import json
import math
import subprocess
import sys

import mediapipe as mp
import numpy as np

SRC, MODEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FPS = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
SW = 360  # chiều rộng ảnh phân tích

probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout.strip().split(",")
w0, h0 = int(probe[0]), int(probe[1])
SH = int(round(h0 * SW / w0 / 2) * 2)

opts = mp.tasks.vision.FaceLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=MODEL),
    running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1,
    output_face_blendshapes=True, output_facial_transformation_matrixes=True)
lm = mp.tasks.vision.FaceLandmarker.create_from_options(opts)

p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", SRC, "-vf", f"fps={FPS},scale={SW}:{SH}", "-f", "rawvideo",
                      "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
n = SW * SH * 3
samples, i = [], 0
while True:
    buf = p.stdout.read(n)
    if len(buf) < n:
        break
    fr = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
    t = i / FPS
    r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=fr), int(t * 1000))
    if r.face_blendshapes:
        bs = {b.category_name: b.score for b in r.face_blendshapes[0]}
        down = (bs.get("eyeLookDownLeft", 0) + bs.get("eyeLookDownRight", 0)) / 2
        blink = (bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2
        m = np.array(r.facial_transformation_matrixes[0])
        pitch = math.degrees(math.atan2(-m[1, 2], m[2, 2]))  # dương = ngẩng, âm = cúi (tùy model)
        samples.append((round(t, 2), round(down, 3), round(pitch, 1), round(blink, 3)))
    else:
        samples.append((round(t, 2), None, None, None))
    i += 1
json.dump({"fps": FPS, "samples": samples}, open(OUT, "w"))
print(f"{len(samples)} mẫu -> {OUT}")
