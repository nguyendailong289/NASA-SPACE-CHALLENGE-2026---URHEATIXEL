"""
Cắt 3 lớp Built-up 10 m (2017, 2025, biến động) thành ô ảnh 256 x 256 px cho Phần 03.

    python web/build_builtup_tiles.py

Đầu ra: web/data/builtup/tiles/<lớp>/<x>_<y>.png  (chỉ ô có dữ liệu)
        web/data/builtup/tiles_meta.js            (danh sách ô, kích thước 10 m)
Ô (x, y) phủ cột x*256..x*256+255, hàng y*256..y*256+255 của raster 10 m gốc.
Chạy sau build_builtup.py (dùng chung bảng màu).
"""
import json
import os
import shutil

import numpy as np
import rasterio
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LULC = os.path.join(ROOT, "2_Data", "LULC")
OUT = os.path.join(ROOT, "web", "data", "builtup", "tiles")
T = 256

# giá trị -> màu (khớp build_builtup.py / bản đồ kết quả)
PAL_BUILT = {0: (0, 0, 0), 7: (255, 250, 192)}
PAL_CHANGE = {0: (0, 0, 0), 1: (123, 30, 122), 2: (244, 100, 95), 3: (255, 250, 192)}
LAYERS = [("built_2017", "Built_Area_HN_2017.tif", PAL_BUILT),
          ("built_2025", "Built_Area_HN_2025.tif", PAL_BUILT),
          ("change_2017_2025", "Built_Area_HN_2017_2025.tif", PAL_CHANGE)]


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    tiles = None
    total = 0
    for key, fname, pal in LAYERS:
        with rasterio.open(os.path.join(LULC, fname)) as d:
            a = d.read(1)
            H, W = a.shape
        # chỉ số bảng màu: 0 = trong suốt (ngoài vùng), 1.. = theo pal
        idx = np.zeros(a.shape, np.uint8)
        palette = [0, 0, 0]
        for i, (v, rgb) in enumerate(pal.items(), start=1):
            idx[a == v] = i
            palette += list(rgb)
        del a
        palette += [0, 0, 0] * (256 - len(palette) // 3)
        os.makedirs(os.path.join(OUT, key))
        found = []
        for ty in range(0, (H + T - 1) // T):
            for tx in range(0, (W + T - 1) // T):
                block = idx[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
                if not block.any():
                    continue
                full = np.zeros((T, T), np.uint8)
                full[:block.shape[0], :block.shape[1]] = block
                im = Image.fromarray(full, "P")
                im.putpalette(palette)
                im.save(os.path.join(OUT, key, f"{tx}_{ty}.png"), optimize=True, transparency=0)
                found.append(f"{tx}_{ty}")
        tiles = tiles or found
        assert tiles == found, "các lớp phải có cùng tập ô"
        size = sum(os.path.getsize(os.path.join(OUT, key, f + ".png")) for f in found)
        total += size
        print(f"{key}: {len(found)} ô, {size / 1e6:.1f} MB")
    meta = {"tile": T, "w": W, "h": H, "tiles": tiles}
    with open(os.path.join(ROOT, "web", "data", "builtup", "tiles_meta.js"), "w", encoding="utf-8") as fh:
        fh.write("window.BUILTUP_TILES=" + json.dumps(meta, separators=(",", ":")) + ";\n")
    print(f"Tổng {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
