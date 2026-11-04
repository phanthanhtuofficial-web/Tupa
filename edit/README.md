# Dựng video "Xu hướng vàng 02/11"

Script `render.py` dựng lại video talking-head theo phong cách dark-premium (nền đen + nhấn vàng):

- Cắt khoảng lặng/ngập ngừng (27,5s → 21,6s), che jump-cut bằng zoom punch-in xen kẽ.
- Hook 0–3s: banner "GIÁ VÀNG" + tiêu đề lớn "XU HƯỚNG / VÀNG / TUẦN NÀY".
- Motion graphic dạng sơ đồ node (viền trắng, node đang nói phát sáng vàng, đường nối có chấm sáng chạy, ô "?" gây tò mò).
- Phụ đề in hoa 2 dòng, từ khóa tô vàng, pop-in.
- Whip-pan + whoosh khi chuyển cảnh, pop/ding khi hiện node, nhạc nền ambient tự tạo (ducking dưới giọng nói), chuẩn -14 LUFS.

Chạy:

```bash
pip install numpy pillow
python render.py <video_goc.mov> <thu_muc_font_BeVietnamPro> <output.mp4>
```

Muốn sửa chữ/thời điểm: chỉnh `SEGS` (đoạn giữ lại), `CAPTIONS`, `draw_hook`, `draw_g1`, `draw_g2`.
