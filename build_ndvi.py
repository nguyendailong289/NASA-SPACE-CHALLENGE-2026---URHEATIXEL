"""
Đóng gói NDVI đã phân cấp 2017 & 2025 và biến động cấp (Phần 04).

    python web/build_ndvi.py

Đầu vào : 2_Data/NDVI/NDVI_classification_{2017,2025}.tif (5 cấp theo NDVI chuẩn hoá, bước 0,2)
          1_Study area/Ha_noi_tinh, Ha_noi_xa ; 4_Results/NDVI/*.png (bản đồ kết quả, nếu có)
Đầu ra  : web/data/ndvi/ndvi_meta.js ; web/assets/maps/ndvi_*.png
Biến động: mã = cấp 2017 * 10 + cấp 2025 (11..55).
"""
import json
import os
import shutil

import numpy as np
import rasterio
from PIL import Image

from build_data import read_shp, read_dbf, simplify, contains, en_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NDVI = os.path.join(ROOT, "2_Data", "NDVI")
AREA = os.path.join(ROOT, "1_Study area")
RESULTS = os.path.join(ROOT, "4_Results", "NDVI")
OUT = os.path.join(ROOT, "web", "data", "ndvi")
MAPS_OUT = os.path.join(ROOT, "web", "assets", "maps")
YEARS = ["2017", "2025"]
R_EARTH = 6371008.8

# khoá trên web -> file bản đồ kết quả (bổ sung khi có, thiếu thì bỏ qua)
MAPS = {
    "ndvi_2017": "NDVI_classification_2017.png",
    "ndvi_2025": "NDVI_classification_2025.png",
    "ndvi_change": "NDVI_classification_2017_2025.png",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(MAPS_OUT, exist_ok=True)

    cls = {}
    for y in YEARS:
        with rasterio.open(os.path.join(NDVI, f"NDVI_classification_{y}.tif")) as d:
            a = d.read(1)
            tr, (h, w) = d.transform, d.shape
            lon0, lat0, lon1, lat1 = d.bounds
            nd = d.nodata
        cls[y] = np.where((a != nd) & np.isfinite(a), np.round(a), 0).astype(int)
    mask = (cls["2017"] > 0) & (cls["2025"] > 0)
    print("Pixel hợp lệ:", int(mask.sum()))

    lat_c = tr.f + (np.arange(h) + 0.5) * tr.e
    px_km2 = (R_EARTH * np.radians(abs(tr.e))) * (R_EARTH * np.cos(np.radians(lat_c)) * np.radians(tr.a)) / 1e6
    area = np.repeat(px_km2[:, None], w, axis=1)

    meta = {"width": w, "height": h, "bounds": [lon0, lat0, lon1, lat1], "years": {},
            "totalKm2": float(area[mask].sum()), "totalPx": int(mask.sum())}
    for y in YEARS:
        c = np.where(mask, cls[y], 0)
        meta["years"][y] = {
            "cls": c.ravel().tolist(),
            "classPx": {str(k): int((c == k).sum()) for k in range(1, 6)},
            "classKm2": {str(k): float(area[c == k].sum()) for k in range(1, 6)},
        }

    trans = cls["2017"] * 10 + cls["2025"]
    meta["trans"] = {str(int(t)): {"px": int(((trans == t) & mask).sum()), "km2": float(area[(trans == t) & mask].sum())}
                     for t in np.unique(trans[mask])}
    delta = (cls["2025"] - cls["2017"])[mask]
    print("Thay đổi cấp (min..max):", int(delta.min()), "..", int(delta.max()))

    # Ranh giới + pixel -> xã
    meta["tinh"] = [simplify(r) for rec in read_shp(os.path.join(AREA, "Ha_noi_tinh.shp")) for r in rec]
    xa_shapes = read_shp(os.path.join(AREA, "Ha_noi_xa.shp"))
    names = [en_name(a["tenXa"]) for a in read_dbf(os.path.join(AREA, "Ha_noi_xa.dbf"))]
    meta["xa"] = [{"ten": n, "rings": [simplify(r) for r in rings]} for rings, n in zip(xa_shapes, names)]
    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    xs, ys = tr.c + cols * tr.a, tr.f + rows * tr.e
    pix_xa = np.full((h, w), -1, int)
    for k, rings in enumerate(xa_shapes):
        pix_xa[contains(rings, xs, ys) & (pix_xa == -1)] = k
    meta["pixXa"] = pix_xa.ravel().tolist()

    meta["maps"] = {}
    for key, fname in MAPS.items():
        src = os.path.join(RESULTS, fname)
        if not os.path.exists(src):
            print("Chưa có bản đồ:", fname)
            continue
        shutil.copyfile(src, os.path.join(MAPS_OUT, key + ".png"))
        im = Image.open(src).convert("RGB")
        im.thumbnail((1800, 1800))
        im.save(os.path.join(MAPS_OUT, key + "_preview.jpg"), quality=85)
        meta["maps"][key] = {"file": "assets/maps/" + key + ".png", "preview": "assets/maps/" + key + "_preview.jpg",
                             "bytes": os.path.getsize(src)}

    # Ảnh thẻ cho trang bìa: bản đồ biến động cấp vẽ từ dữ liệu (nền trong suốt, hiệu chỉnh tỉ lệ kinh/vĩ)
    colors = {-2: (185, 28, 28), -1: (248, 113, 113), 0: (203, 213, 225), 1: (134, 239, 172), 2: (21, 128, 61)}
    rgba = np.zeros((h, w, 4), np.uint8)
    dgrid = cls["2025"] - cls["2017"]
    for dv, col in colors.items():
        rgba[mask & (dgrid == dv)] = (*col, 255)
    k = 7
    sx = np.cos(np.radians((lat0 + lat1) / 2)) * tr.a / abs(tr.e)
    img = Image.fromarray(rgba, "RGBA").resize((int(w * k * sx), h * k), Image.NEAREST)
    side = max(img.size) + 60
    card = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    card.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2))
    card.save(os.path.join(MAPS_OUT, "ndvi_change_card.png"), optimize=True)
    # Có bản đồ biến động thì dùng ảnh cắt vùng Hà Nội từ bản đồ (giống các thẻ khác)
    chg_map = os.path.join(RESULTS, MAPS["ndvi_change"])
    if os.path.exists(chg_map):
        Image.open(chg_map).convert("RGB").crop((180, 110, 2340, 2270)).resize((800, 800), Image.LANCZOS)             .save(os.path.join(MAPS_OUT, "ndvi_change_card.jpg"), quality=82)

    out = os.path.join(OUT, "ndvi_meta.js")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("window.NDVI=" + json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("Đã ghi", out, f"({os.path.getsize(out) / 1e6:.2f} MB)")
    for y in YEARS:
        m = meta["years"][y]
        print(y, m["classPx"], {k: round(v, 1) for k, v in m["classKm2"].items()})
    print("Biến động:", {k: v["px"] for k, v in meta["trans"].items()})
    print("Tổng diện tích", round(meta["totalKm2"], 1), "km²")


if __name__ == "__main__":
    main()
