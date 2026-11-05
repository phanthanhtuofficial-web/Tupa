# Tupa – quy trình dựng video TikTok phân tích vàng / Bitcoin

Repo này chứa công cụ dựng video dọc 9:16 theo phong cách **dark-premium** (nền đen, nhấn vàng #F5C542,
font Be Vietnam Pro, sơ đồ node phát sáng, phụ đề in hoa có từ khóa tô vàng, whip-pan + whoosh).
Người dùng nói tiếng Việt – luôn trả lời bằng tiếng Việt, dễ hiểu, không thuật ngữ lập trình thừa.

## Cấu trúc
- `edit/render_v2.py` – **mẫu chuẩn mới nhất** (video "2 kịch bản giá vàng"). Video mới: copy thành
  `edit/render_<ten>.py` rồi sửa phần kịch bản, KHÔNG sửa file cũ.
- `edit/render.py` – mẫu video ngắn đầu tiên (intro 27s).
- `edit/transcribe.py` – chép lời tiếng Việt kèm mốc thời gian từng từ.
- `edit/setup.sh` – cài thư viện + mô hình chép lời (chạy 1 lần mỗi phiên, ~2 phút).
- `edit/fonts/` – font Be Vietnam Pro (OFL).
- `output/` – video thành phẩm.

## Quy trình cho video mới
1. `bash edit/setup.sh`
2. Lấy video: file đính kèm trong chat, hoặc Google Drive (connector Google Drive; file lớn thì tải qua
   `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t` – file phải đang chia sẻ
   "Bất kỳ ai có link"; tải xong nhắc người dùng tắt chia sẻ). Đặt vào `work/` (đã gitignore).
3. Chép lời: `.venv-video/bin/python -I edit/transcribe.py work/<video> .whisper-model work/tr.json`
   Whisper hay nghe sai thuật ngữ ("kích bản", "cấu chúc", "giải hạn", "phét"=Fed): tự sửa khi viết chữ lên hình.
   Con số giá phải khớp lời nói; số nào không chắc thì hỏi lại hoặc bỏ, không tự bịa.
4. Xem video: contact sheet `ffmpeg -i v -vf "fps=1/3,scale=200:-1,tile=11x3"`, tìm đoạn chèn biểu đồ
   (`select='gt(scene,0.25)'`), khoảng lặng (`silencedetect=n=-35dB:d=0.35`), vị trí khuôn mặt.
5. Copy `render_v2.py`, sửa: `SILENCES`, `END`, `SCENES` (head / chart tĩnh / chart động / đồ họa g_*),
   các hàm `g_*`, `CAPTIONS`, `POPS`/`DINGS`, chú thích chart (`y_A1`… đo trục giá từ khung hình), `draw_hook`.
   Mọi mốc thời gian theo **giây của video gốc**.
6. Xem thử: `PREVIEW="1.5,8,30" .venv-video/bin/python -I edit/render_<ten>.py <video> edit/fonts preview.jpg`
   rồi đọc ảnh, sửa bố cục trước khi render thật.
7. Render: `.venv-video/bin/python -I edit/render_<ten>.py <video> edit/fonts output/<ten>.mp4`
   (~2 phút render cho mỗi phút video). Kiểm tra loudness ~ -14 LUFS, gửi file cho người dùng, commit + push.

## Quy tắc nội dung
- Không dùng tên/logo kênh người khác. Không tự thêm số liệu, tin tức không có trong lời nói.
- Cuối video phân tích luôn có câu "Nội dung mang tính tham khảo, không phải lời khuyên đầu tư".
- Font không có ký tự "→": viết bằng chữ ("LÊN", "XUỐNG").
- Nhạc nền hiện là nhạc tự tạo (không bản quyền). Nếu người dùng gửi file nhạc/SFX riêng, trộn thay thế
  trong `render_audio` (nhạc -24 dB, tự giảm khi có giọng nói).
