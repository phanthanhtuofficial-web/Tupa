"""Chép lời tiếng Việt kèm mốc thời gian từng từ.

Dùng:  .venv-video/bin/python -I edit/transcribe.py <video> <thu_muc_model> <out.json> ["từ khóa gợi ý ..."]
In ra từng câu [start-end] và lưu JSON (câu + từng từ) để canh phụ đề/đồ họa.
"""
import json
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

video, model_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
prompt = sys.argv[4] if len(sys.argv) > 4 else (
    "Phân tích giá vàng: kịch bản, nhịp hồi kỹ thuật, vùng kháng cự, vùng hỗ trợ, cấu trúc tăng, dài hạn, "
    "trendline, retest, Fed, lãi suất, Non-farm, CPI, FOMC, Bitcoin, đô, ounce, triệu một lượng.")

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
m = WhisperModel(model_dir, device="cpu", compute_type="int8")
segs, _ = m.transcribe(audio, language="vi", word_timestamps=True, beam_size=5, initial_prompt=prompt,
                       condition_on_previous_text=False)
res = []
for s in segs:
    print(f"[{s.start:.2f}-{s.end:.2f}] {s.text}", flush=True)
    res.append({"start": s.start, "end": s.end, "text": s.text,
                "words": [{"w": w.word, "s": w.start, "e": w.end} for w in s.words]})
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
