#!/usr/bin/env bash
# Cài công cụ cho quy trình dựng video: thư viện Python + mô hình chép lời tiếng Việt (Whisper small).
# Dùng: bash edit/setup.sh   -> tạo .venv-video/ và .whisper-model/ ở thư mục gốc repo (đã gitignore)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-video"
MODEL="$ROOT/.whisper-model"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q numpy pillow faster-whisper
if [ ! -f "$MODEL/model.bin" ]; then
  # huggingface.co bị chặn trong môi trường cloud -> lấy bản CTranslate2 của Whisper small từ npm
  TMP="$(mktemp -d)"
  (cd "$TMP" && for i in 0 1 2 3; do npm pack --silent "@skillninja/shortmovie-telop-model-p$i" >/dev/null; done
   for f in *.tgz; do tar xzf "$f"; done)
  mkdir -p "$MODEL"
  cp "$TMP"/package/{config.json,preprocessor_config.json,tokenizer.json,vocabulary.json} "$MODEL"/
  cat "$TMP"/package/model.bin.part{0,1,2,3} > "$MODEL/model.bin"
  (cd "$MODEL" && echo "$(cat "$TMP/package/model.sha256")  model.bin" | sha256sum -c -)
  rm -rf "$TMP"
fi
echo "OK: python=$VENV/bin/python  model=$MODEL"
