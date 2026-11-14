"""
Đóng gói lớp Built-up (Esri | Sentinel-2 Land Cover, lớp Built Area) cho trang 2.

    python web/build_builtup.py

Đầu ra (web/data/builtup/):
  - built_2017.png, built_2025.png, change_2017_2025.png : raster đã hạ độ phân giải
  - builtup_meta.js : kích thước ảnh, ranh giới (toạ độ pixel), thống kê đếm pixel
Và chép 3 bản đồ kết quả từ 4_Results/LULC sang web/assets/maps/ để tải về.
"""
import json
import os
import shutil
import struct

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform as warp_transform
from PIL import Image

from build_data import en_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LULC = os.path.join(ROOT, "2_Data", "LULC")
AREA = os.path.join(ROOT, "1_Study area")
RESULTS = os.path.join(ROOT, "4_Results", "LULC")
OUT = os.path.join(ROOT, "web", "data", "builtup")
MAPS_OUT = os.path.join(ROOT, "web", "assets", "maps")
FACTOR = 2  # 10 m -> 20 m cho web

# giá trị -> RGBA (khớp chú giải bản đồ kết quả)
PAL_BUILT = {0: (0, 0, 0, 255), 7: (255, 250, 192, 255)}
PAL_CHANGE = {0: (0, 0, 0, 255), 1: (123, 30, 122, 255), 2: (244, 100, 95, 255), 3: (255, 250, 192, 255)}

LAYERS = [
    ("built_2017", "Built_Area_HN_2017.tif", PAL_BUILT),
    ("built_2025", "Built_Area_HN_2025.tif", PAL_BUILT),
    ("change_2017_2025", "Built_Area_HN_2017_2025.tif", PAL_CHANGE),
]
MAPS = {
    "built_2017": "Built_up_Areas_HN_2017.png",
    "built_2025": "Buitl_up_Areas_HN_2025.png",
    "change_2017_2025": "Built_up_Areas_HN_2017_2025.png",
}


def read_shp(path):
    b = open(path, "rb").read()
    out, pos = [], 100
    while pos < len(b):
        clen = struct.unpack(">i", b[pos + 4:pos + 8])[0] * 2
        rec = b[pos + 8:pos + 8 + clen]
        pos += 8 + clen
        rings = []
        if struct.unpack("<i", rec[:4])[0] == 5:
            nparts, npts = struct.unpack("<2i", rec[36:44])
            parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])) + [npts]
            off = 44 + 4 * nparts
            pts = np.frombuffer(rec[off:off + 16 * npts], dtype="<f8").reshape(-1, 2)
            rings = [pts[parts[i]:parts[i + 1]] for i in range(nparts)]
        out.append(rings)
    return out


def read_dbf_names(path, field):
    b = open(path, "rb").read()
    nrec, hl, rl = struct.unpack("<IHH", b[4:12])
    fields, p = [], 32
    while b[p] != 0x0D:
        fields.append((b[p:p + 11].split(b"\0")[0].decode(), b[p + 16]))
        p += 32
    names = []
    for k in range(nrec):
        r, o = b[hl + k * rl + 1:hl + (k + 1) * rl], 0
        for name, ln in fields:
            if name == field:
                names.append(r[o:o + ln].decode("utf-8", "replace").strip())
            o += ln
    return names


def to_pixels(ring, crs, inv, step_px=1.5):
    xs, ys = warp_transform("EPSG:4326", crs, ring[:, 0].tolist(), ring[:, 1].tolist())
    cols, rows = inv * (np.array(xs), np.array(ys))
    pts = [[round(float(rows[0]), 1), round(float(cols[0]), 1)]]
    for r, c in zip(rows[1:], cols[1:]):
        if abs(r - pts[-1][0]) + abs(c - pts[-1][1]) > step_px:
            pts.append([round(float(r), 1), round(float(c), 1)])
    return pts


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(MAPS_OUT, exist_ok=True)
    meta = {"layers": {}, "counts": {}}

    for key, fname, pal in LAYERS:
        with rasterio.open(os.path.join(LULC, fname)) as d:
            full = d.read(1)
            valid = full > -1e30
            vals, cnt = np.unique(full[valid], return_counts=True)
            meta["counts"][key] = {str(int(v)): int(c) for v, c in zip(vals, cnt)}
            meta["pixelArea"] = abs(d.res[0] * d.res[1])
            h, w = d.height // FACTOR, d.width // FACTOR
            small = d.read(1, out_shape=(h, w), resampling=Resampling.nearest)
            crs = d.crs
            # transform của ảnh nhỏ: pixel (col,row) -> UTM
            tr = d.transform * d.transform.scale(d.width / w, d.height / h)
        del full
        rgba = np.zeros((h, w, 4), np.uint8)
        for v, c in pal.items():
            rgba[small == v] = c
        Image.fromarray(rgba, "RGBA").save(os.path.join(OUT, key + ".png"), optimize=True)
        meta["layers"][key] = {"w": w, "h": h}
        print(key, (w, h), meta["counts"][key])

    meta["size"] = {"w": w, "h": h}
    # pixel (col,row) -> UTM: x = a*col + b*row + c ; y = d*col + e*row + f
    meta["transform"] = [tr.a, tr.b, tr.c, tr.d, tr.e, tr.f]
    meta["epsg"] = crs.to_epsg()
    inv = ~tr
    tinh = read_shp(os.path.join(AREA, "Ha_noi_tinh.shp"))
    meta["tinh"] = [to_pixels(r, crs, inv, 2.5) for rec in tinh for r in rec]
    xa = read_shp(os.path.join(AREA, "Ha_noi_xa.shp"))
    names = [en_name(n) for n in read_dbf_names(os.path.join(AREA, "Ha_noi_xa.dbf"), "tenXa")]
    meta["xa"] = [{"ten": n, "rings": [to_pixels(r, crs, inv) for r in rings]} for rings, n in zip(xa, names)]

    # Bản đồ kết quả: bản gốc để tải + bản xem trước nhẹ
    meta["maps"] = {}
    for key, fname in MAPS.items():
        src = os.path.join(RESULTS, fname)
        dst_name = key + ".png"
        shutil.copyfile(src, os.path.join(MAPS_OUT, dst_name))
        im = Image.open(src).convert("RGB")
        im.thumbnail((1800, 1800))
        im.save(os.path.join(MAPS_OUT, key + "_preview.jpg"), quality=85)
        # Ảnh vuông chỉ vùng Hà Nội cho thẻ ở trang bìa (theo bố cục bản đồ 3507 x 2480 px)
        Image.open(src).convert("RGB").crop((180, 110, 2340, 2270)).resize((800, 800), Image.LANCZOS).save(os.path.join(MAPS_OUT, key + "_card.jpg"), quality=82)
        meta["maps"][key] = {"file": "assets/maps/" + dst_name,
                             "preview": "assets/maps/" + key + "_preview.jpg",
                             "bytes": os.path.getsize(src)}

    with open(os.path.join(OUT, "builtup_meta.js"), "w", encoding="utf-8") as fh:
        fh.write("window.BUILTUP=" + json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + ";\n")
    for f in sorted(os.listdir(OUT)):
        print(f, f"{os.path.getsize(os.path.join(OUT, f)) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
