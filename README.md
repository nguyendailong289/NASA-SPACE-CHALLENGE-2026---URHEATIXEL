# UrHeatixel

Giám sát biến động không gian của các vùng nhiệt độ cao phục vụ nhận diện xu hướng mở rộng đô thị tại thành phố Hà Nội.
Dự án tham gia **NASA Space Apps Challenge 2026** (Hà Nội).

## Website

| Phần | Trang | Nội dung |
| --- | --- | --- |
| 01 | `index.html` | Nhiệt độ bề mặt (LST) theo ngày, 2017 và 2025 |
| 02 | `normalized.html` | LST trung bình năm, LST chuẩn hóa, phân cấp và biến động phân cấp |
| 03 | `builtup.html` | Đất xây dựng 2017, 2025 và biến động |

## Dữ liệu

- NASA MODIS Terra MOD11A1 v061, lớp LST_Day_1km (1 km, theo ngày)
- Esri | Sentinel-2 Land Cover Explorer, lớp Built Area (10 m)
- Ranh giới hành chính TP. Hà Nội và 126 xã/phường (2025)

## Cập nhật dữ liệu

Các script `build_*.py` đọc dữ liệu gốc ở thư mục dự án (`1_Study area`, `2_Data`, `4_Results`, không có trong repo này)
và ghi lại các file trong `data/` và `assets/maps/`:

```bash
python build_data.py
python build_normalized.py
python build_builtup.py
```

Xem thử trên máy: `python -m http.server 8765` rồi mở http://localhost:8765
