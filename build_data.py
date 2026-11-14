"""
Đóng gói dữ liệu LST (MODIS MOD11A1) theo ngày 2017 & 2025 + ranh giới
Hà Nội (tỉnh, xã) thành file JS cho website.

Chạy lại mỗi khi dữ liệu trong 2_Data/LST hoặc 1_Study area thay đổi:
    python web/build_data.py

Đầu ra: web/data/lst_data.js  (gán window.LST_DATA)
"""
import base64
import glob
import json
import os
import re
import struct

import numpy as np
import rasterio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LST_DIR = os.path.join(ROOT, "2_Data", "LST")
AREA_DIR = os.path.join(ROOT, "1_Study area")
OUT = os.path.join(ROOT, "web", "data", "lst_data.js")
YEARS = ["2017", "2025"]
SCALE = 0.02          # MOD11A1: raw * 0.02 = Kelvin
SIMPLIFY_DEG = 0.0004  # bỏ bớt đỉnh gần nhau hơn ~40 m cho file nhẹ


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def read_shp(path):
    """Polygon (type 5) -> list bản ghi, mỗi bản ghi là list vòng (np.ndarray Nx2)."""
    b = open(path, "rb").read()
    records, pos = [], 100
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
        records.append(rings)
    return records


def read_dbf(path):
    b = open(path, "rb").read()
    nrec, hl, rl = struct.unpack("<IHH", b[4:12])
    fields, p = [], 32
    while b[p] != 0x0D:
        fields.append((b[p:p + 11].split(b"\0")[0].decode(), b[p + 16]))
        p += 32
    rows = []
    for k in range(nrec):
        r, o, row = b[hl + k * rl + 1:hl + (k + 1) * rl], 0, {}
        for name, ln in fields:
            row[name] = r[o:o + ln].decode("utf-8", "replace").strip()
            o += ln
        rows.append(row)
    return rows


def simplify(ring):
    keep = [ring[0]]
    for pt in ring[1:-1]:
        if abs(pt[0] - keep[-1][0]) + abs(pt[1] - keep[-1][1]) > SIMPLIFY_DEG:
            keep.append(pt)
    keep.append(ring[-1])
    return [[round(float(x), 5), round(float(y), 5)] for x, y in keep]


def contains(rings, xs, ys):
    """Even-odd point-in-polygon cho nhiều điểm cùng lúc."""
    inside = np.zeros(xs.shape, bool)
    for ring in rings:
        x1, y1 = ring[:-1, 0], ring[:-1, 1]
        x2, y2 = ring[1:, 0], ring[1:, 1]
        for a, b_, c, d in zip(x1, y1, x2, y2):
            cross = ((b_ > ys) != (d > ys)) & (xs < (c - a) * (ys - b_) / (d - b_ + 1e-15) + a)
            inside ^= cross
    return inside


def main():
    with rasterio.open(os.path.join(LST_DIR, "ket_qua", "mean_LST_2017_C.tif")) as d:
        h, w = d.shape
        bounds = list(d.bounds)
        tr = d.transform
        mask = d.read(1) != -9999   # mặt nạ vùng Hà Nội
    idx = np.flatnonzero(mask.ravel())

    data = {"width": w, "height": h, "bounds": bounds, "scale": SCALE,
            "mask": b64(idx.astype("<u2")), "years": {}}

    for y in YEARS:
        days = []
        for f in sorted(glob.glob(os.path.join(LST_DIR, f"LST_{y}", "*.tif"))):
            date = re.search(r"_(\d{8})T", os.path.basename(f)).group(1)
            with rasterio.open(f) as d:
                a = d.read(1).ravel()[idx].astype("<u2")
            days.append({"date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                         "valid": int((a > 0).sum()), "px": b64(a)})
        data["years"][y] = {"days": days}
        print(f"LST {y}: {len(days)} ngày")

    # --- Ranh giới ---
    tinh = read_shp(os.path.join(AREA_DIR, "Ha_noi_tinh.shp"))
    data["tinh"] = [simplify(r) for rec in tinh for r in rec]

    xa_shapes = read_shp(os.path.join(AREA_DIR, "Ha_noi_xa.shp"))
    xa_attrs = read_dbf(os.path.join(AREA_DIR, "Ha_noi_xa.dbf"))
    data["xa"] = [{"ten": a["tenXa"], "danSo": a["danSo"], "dienTich": a["dienTich"],
                   "rings": [simplify(r) for r in rings]}
                  for rings, a in zip(xa_shapes, xa_attrs)]
    print(f"Ranh giới: tỉnh {len(data['tinh'])} vòng, xã {len(data['xa'])} đơn vị")

    # Pixel -> xã (theo tâm pixel), 255 = ngoài Hà Nội
    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    xs = tr.c + cols * tr.a
    ys = tr.f + rows * tr.e
    pix_xa = np.full((h, w), 255, np.uint8)
    for k, rings in enumerate(xa_shapes):
        pix_xa[contains(rings, xs, ys) & (pix_xa == 255)] = k
    data["pixXa"] = b64(pix_xa.ravel())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("window.LST_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("Đã ghi", OUT, f"({os.path.getsize(OUT) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
