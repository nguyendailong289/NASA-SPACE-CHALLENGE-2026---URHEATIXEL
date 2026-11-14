"""
Đóng gói LST trung bình, LST chuẩn hóa và phân cấp (Phần 02).

    python web/build_normalized.py

Đầu vào : 2_Data/LST/ket_qua/{mean_LST_*_C, Normalize_LST_*, Classification_LST_*}.tif
          1_Study area/Ha_noi_tinh, Ha_noi_xa ; 4_Results/LST/*.png (bản đồ kết quả)
Đầu ra  : web/data/normalized/normalized_meta.js ; web/assets/maps/lst_*.png
"""
import json
import os
import shutil

import numpy as np
import rasterio
from PIL import Image

from build_data import read_shp, read_dbf, simplify, contains, en_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KQ = os.path.join(ROOT, "2_Data", "LST", "ket_qua")
AREA = os.path.join(ROOT, "1_Study area")
RESULTS = os.path.join(ROOT, "4_Results", "LST")
OUT = os.path.join(ROOT, "web", "data", "normalized")
MAPS_OUT = os.path.join(ROOT, "web", "assets", "maps")
YEARS = ["2017", "2025"]
R_EARTH = 6371008.8

MAPS = {  # khoá trên web -> file bản đồ kết quả
    "mean_2017": "LST_Mean_2017.png", "mean_2025": "LST_Mean_2025.png",
    "class_2017": "LST_Classification_2017.png", "class_2025": "LST_Classification_2025.png",
    "change": "LST_Classification_2017_2025.png",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(MAPS_OUT, exist_ok=True)

    with rasterio.open(os.path.join(KQ, "mean_LST_2017_C.tif")) as d:
        h, w = d.shape
        tr = d.transform
        lon0, lat0, lon1, lat1 = d.bounds
        mask = d.read(1) != -9999
    meta = {"width": w, "height": h, "bounds": [lon0, lat0, lon1, lat1], "years": {}}

    # Diện tích từng pixel (km²) theo vĩ độ của hàng
    lat_c = tr.f + (np.arange(h) + 0.5) * tr.e
    px_km2 = (R_EARTH * np.radians(abs(tr.e))) * (R_EARTH * np.cos(np.radians(lat_c)) * np.radians(tr.a)) / 1e6
    area = np.repeat(px_km2[:, None], w, axis=1)

    cls_by = {}
    for y in YEARS:
        with rasterio.open(os.path.join(KQ, f"mean_LST_{y}_C.tif")) as d:
            mean = d.read(1)
        with rasterio.open(os.path.join(KQ, f"Normalize_LST_{y}.tif")) as d:
            norm = d.read(1)
        with rasterio.open(os.path.join(KQ, f"Classification_LST_{y}.tif")) as d:
            cls_file = d.read(1)
        mean = np.where(mask, mean, 0)
        norm = np.where(mask, norm, 0)
        # Phân cấp theo ngưỡng 0,2 (giống file Classification). Pixel có giá trị chuẩn hoá = 0
        # bị bỏ sót trong file gốc -> xếp vào cấp 1 (Very Low).
        cls = np.clip(np.ceil(np.round(norm, 6) / 0.2), 1, 5).astype(int)
        diff = int(((cls != cls_file) & mask).sum())
        print(f"{y}: pixel phân cấp khác file gốc = {diff}")

        mv = mean[mask]
        meta["years"][y] = {
            "mean": np.where(mask, np.round(mean, 3), None).ravel().tolist(),
            "norm": np.where(mask, np.round(norm, 4), None).ravel().tolist(),
            "cls": np.where(mask, cls, 0).ravel().tolist(),
            "lstMin": float(mv.min()), "lstMax": float(mv.max()),
            "lstMean": float((mv * area[mask]).sum() / area[mask].sum()),
            "classPx": {str(k): int(((cls == k) & mask).sum()) for k in range(1, 6)},
            "classKm2": {str(k): float(area[(cls == k) & mask].sum()) for k in range(1, 6)},
            "fixedPx": diff,
        }
        cls_by[y] = cls
    meta["totalKm2"] = float(area[mask].sum())

    # Biến động phân cấp 2017 -> 2025: mã = cấp 2017 * 10 + cấp 2025 (11..55)
    trans = cls_by["2017"] * 10 + cls_by["2025"]
    with rasterio.open(os.path.join(KQ, "Classification_LST_2017_2025.tif")) as d:
        trans_file = np.where(mask, d.read(1), 0)
    print("Biến động: pixel khác file gốc =", int(((trans != np.round(trans_file)) & mask).sum()))
    meta["trans"] = {str(int(c)): {"px": int(((trans == c) & mask).sum()),
                                   "km2": float(area[(trans == c) & mask].sum())}
                     for c in np.unique(trans[mask])}
    meta["totalPx"] = int(mask.sum())

    # Ranh giới (kinh/vĩ độ) + pixel -> xã
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
        dst = "lst_" + key + ".png"
        shutil.copyfile(src, os.path.join(MAPS_OUT, dst))
        im = Image.open(src).convert("RGB")
        im.thumbnail((1800, 1800))
        im.save(os.path.join(MAPS_OUT, "lst_" + key + "_preview.jpg"), quality=85)
        # Ảnh vuông chỉ vùng Hà Nội cho thẻ ở trang bìa (theo bố cục bản đồ 3507 x 2480 px)
        Image.open(src).convert("RGB").crop((180, 110, 2340, 2270)).resize((800, 800), Image.LANCZOS).save(os.path.join(MAPS_OUT, "lst_" + key + "_card.jpg"), quality=82)
        meta["maps"][key] = {"file": "assets/maps/" + dst, "preview": "assets/maps/lst_" + key + "_preview.jpg",
                             "bytes": os.path.getsize(src)}

    out = os.path.join(OUT, "normalized_meta.js")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("window.LSTN=" + json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("Đã ghi", out, f"({os.path.getsize(out) / 1e6:.2f} MB)")
    for y in YEARS:
        m = meta["years"][y]
        print(y, "TB", round(m["lstMean"], 2), "°C", m["classPx"], {k: round(v, 1) for k, v in m["classKm2"].items()})
    print("Tổng diện tích", round(meta["totalKm2"], 1), "km²")


if __name__ == "__main__":
    main()
