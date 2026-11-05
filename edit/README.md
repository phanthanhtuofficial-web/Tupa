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

## Video 2: "2 kịch bản giá vàng" (`render_v2.py`)

Video gốc 3:13 → 3:01 sau khi cắt khoảng lặng. Ngoài phong cách như video 1, bản này:

- Chú thích **trực tiếp lên biểu đồ**: dải vàng đặt đúng vùng giá 4.050–4.060 (kháng cự) và 3.870–3.900 (hỗ trợ), có nhãn "KỊCH BẢN 1/2", zoom chậm vào chart.
- Sơ đồ motion graphic cho từng ý: hỗ trợ cũ → kháng cự, mục tiêu 4.250–4.300, kịch bản thủng hỗ trợ, vùng hợp lưu (trendline + hỗ trợ cứng T10/2025), lịch tin vĩ mô (Non-farm 06/11, CPI 10/11, họp Fed 08–09/12), mục tiêu dài hạn 3.000–3.300 $/oz (≈100–110 triệu/lượng).
- Phụ đề từ khóa ở mọi đoạn người nói, câu miễn trừ trách nhiệm ở cuối.

Chạy: `python render_v2.py <video_goc.mov> <thu_muc_font> <output.mp4>`
Xem thử nhanh vài khung hình: `PREVIEW="1.5,8.5,30" python render_v2.py <video> <font> preview.jpg` (thời gian theo video gốc).
