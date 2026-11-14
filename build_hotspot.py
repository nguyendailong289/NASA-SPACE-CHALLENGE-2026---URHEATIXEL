"""
Phần 05 – Quan hệ LST – NDVI và điểm nóng cần can thiệp.

    python web/build_hotspot.py

Chồng LST chuẩn hoá (2_Data/LST/ket_qua/Normalize_LST_*.tif) và NDVI chuẩn hoá
(2_Data/NDVI/NDVI_normalized_*.tif), phân 5 cấp bước 0,2, rồi xếp mức ưu tiên:

  Cực kỳ khẩn cấp (2): LST cấp >= EXT_LST  VÀ NDVI cấp <= LOW_NDVI
  Khẩn cấp        (1): chỉ một điều kiện xấu:
                       LST cấp >= EXT_LST và NDVI cấp > LOW_NDVI, hoặc
                       NDVI cấp <= LOW_NDVI và LST cấp == EXT_LST - 1
  Còn lại         (0)

(NDVI cấp 1 chủ yếu là mặt nước, vốn mát, nên điều kiện "thiếu cây xanh" luôn đi kèm LST cao.)
Đầu ra: web/data/hotspot/hotspot_meta.js
"""
import json
import os

import numpy as np
import rasterio

from build_data import read_shp, read_dbf, simplify, contains, en_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LST_DIR = os.path.join(ROOT, "2_Data", "LST", "ket_qua")
NDVI_DIR = os.path.join(ROOT, "2_Data", "NDVI")
AREA = os.path.join(ROOT, "1_Study area")
OUT = os.path.join(ROOT, "web", "data", "hotspot")
YEARS = ["2017", "2025"]
R_EARTH = 6371008.8

# ---- Quy tắc điểm nóng (sửa ở đây nếu muốn đổi ngưỡng) ----
EXT_LST = 5   # LST "rất cao": Very High (0,8 – 1,0)
LOW_NDVI = 2  # NDVI "thấp": Very Low + Low (0,0 – 0,4)


def classify(v):
    return np.clip(np.ceil(np.round(v, 6) / 0.2), 1, 5).astype(int)


def level(lc, vc):
    hot, bare = lc >= EXT_LST, vc <= LOW_NDVI
    lv = np.zeros(lc.shape, int)
    lv[(hot & ~bare) | (bare & (lc == EXT_LST - 1))] = 1
    lv[hot & bare] = 2
    return lv


def main():
    os.makedirs(OUT, exist_ok=True)
    with rasterio.open(os.path.join(LST_DIR, "mean_LST_2017_C.tif")) as d:
        tr, (h, w) = d.transform, d.shape
        lon0, lat0, lon1, lat1 = d.bounds
        mask = d.read(1) != -9999
    lat_c = tr.f + (np.arange(h) + 0.5) * tr.e
    px_km2 = (R_EARTH * np.radians(abs(tr.e))) * (R_EARTH * np.cos(np.radians(lat_c)) * np.radians(tr.a)) / 1e6
    area = np.repeat(px_km2[:, None], w, axis=1)

    # Ranh giới + pixel -> xã
    xa_shapes = read_shp(os.path.join(AREA, "Ha_noi_xa.shp"))
    names = [en_name(a["tenXa"]) for a in read_dbf(os.path.join(AREA, "Ha_noi_xa.dbf"))]
    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    xs, ys = tr.c + cols * tr.a, tr.f + rows * tr.e
    pix_xa = np.full((h, w), -1, int)
    for k, rings in enumerate(xa_shapes):
        pix_xa[contains(rings, xs, ys) & (pix_xa == -1)] = k

    meta = {"width": w, "height": h, "bounds": [lon0, lat0, lon1, lat1],
            "rule": {"extLst": EXT_LST, "lowNdvi": LOW_NDVI},
            "totalKm2": float(area[mask].sum()), "totalPx": int(mask.sum()), "years": {}}
    lv_by = {}
    for y in YEARS:
        with rasterio.open(os.path.join(LST_DIR, f"Normalize_LST_{y}.tif")) as d:
            ln = np.where(mask, d.read(1), 0)
        with rasterio.open(os.path.join(NDVI_DIR, f"NDVI_normalized_{y}.tif")) as d:
            vn = np.where(mask, d.read(1), 0)
        lc, vc = classify(ln), classify(vn)
        lv = np.where(mask, level(lc, vc), -1)
        lv_by[y] = lv
        L, V = ln[mask], vn[mask]
        rk = lambda a: a.argsort().argsort()
        slope, icpt = np.polyfit(V, L, 1)
        cross = np.zeros((5, 5), int)
        np.add.at(cross, (lc[mask] - 1, vc[mask] - 1), 1)
        cross_km2 = np.zeros((5, 5))
        np.add.at(cross_km2, (lc[mask] - 1, vc[mask] - 1), area[mask])

        # Thống kê theo xã: diện tích từng mức
        xa_stats = []
        for k, n in enumerate(names):
            sel = mask & (pix_xa == k)
            if not sel.any():
                continue
            e = float(area[sel & (lv == 2)].sum()); u = float(area[sel & (lv == 1)].sum())
            xa_stats.append({"k": k, "px": int(sel.sum()), "km2": float(area[sel].sum()),
                             "ext": e, "urg": u, "extPx": int((sel & (lv == 2)).sum()), "urgPx": int((sel & (lv == 1)).sum())})
        meta["years"][y] = {
            "lstN": np.where(mask, np.round(ln, 3), None).ravel().tolist(),
            "ndviN": np.where(mask, np.round(vn, 3), None).ravel().tolist(),
            "level": lv.ravel().tolist(),
            "pearson": float(np.corrcoef(L, V)[0, 1]),
            "spearman": float(np.corrcoef(rk(L), rk(V))[0, 1]),
            "slope": float(slope), "intercept": float(icpt),
            "cross": cross.tolist(), "crossKm2": cross_km2.round(3).tolist(),
            "levelPx": {str(v): int(((lv == v) & mask).sum()) for v in (0, 1, 2)},
            "levelKm2": {str(v): float(area[(lv == v) & mask].sum()) for v in (0, 1, 2)},
            "xa": xa_stats,
        }
        print(y, "r =", round(meta["years"][y]["pearson"], 3), "mức:", meta["years"][y]["levelPx"])

    # Biến động điểm nóng (điểm nóng = mức >= 1)
    h17, h25 = (lv_by["2017"] >= 1) & mask, (lv_by["2025"] >= 1) & mask
    chg = np.full((h, w), -1, int)
    chg[mask] = 0
    chg[h17 & h25] = 3  # duy trì
    chg[~h17 & h25] = 2  # mới xuất hiện
    chg[h17 & ~h25] = 1  # không còn
    meta["change"] = chg.ravel().tolist()
    meta["changeKm2"] = {str(v): float(area[chg == v].sum()) for v in (0, 1, 2, 3)}
    meta["changePx"] = {str(v): int((chg == v).sum()) for v in (0, 1, 2, 3)}
    print("Biến động điểm nóng:", meta["changePx"])

    meta["tinh"] = [simplify(r) for rec in read_shp(os.path.join(AREA, "Ha_noi_tinh.shp")) for r in rec]
    meta["xa"] = [{"ten": n, "rings": [simplify(r) for r in rings]} for rings, n in zip(xa_shapes, names)]
    meta["pixXa"] = pix_xa.ravel().tolist()

    # Ảnh thẻ cho trang bìa: điểm nóng 2025 (nền trong suốt, hiệu chỉnh tỉ lệ kinh/vĩ)
    from PIL import Image
    pal = {0: (203, 213, 225, 110), 1: (249, 115, 22, 255), 2: (220, 38, 38, 255)}
    rgba = np.zeros((h, w, 4), np.uint8)
    for v, col in pal.items():
        rgba[lv_by["2025"] == v] = col
    k, sx = 7, np.cos(np.radians((lat0 + lat1) / 2)) * tr.a / abs(tr.e)
    img = Image.fromarray(rgba, "RGBA").resize((int(w * k * sx), h * k), Image.NEAREST)
    side = max(img.size) + 60
    card = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    card.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2))
    card.save(os.path.join(ROOT, "web", "assets", "maps", "hotspot_card.png"), optimize=True)

    out = os.path.join(OUT, "hotspot_meta.js")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("window.HOT=" + json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("Đã ghi", out, f"({os.path.getsize(out) / 1e6:.2f} MB)")
    top = sorted(meta["years"]["2025"]["xa"], key=lambda s: -(s["ext"] * 10 + s["urg"]))[:10]
    for s in top:
        print(f"  {names[s['k']]}: cực kỳ {s['ext']:.1f} km², khẩn cấp {s['urg']:.1f} km²")


if __name__ == "__main__":
    main()
