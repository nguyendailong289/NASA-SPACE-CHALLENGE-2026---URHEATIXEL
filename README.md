# UrHeatixel

Monitoring the spatial dynamics of high land surface temperature zones to identify urban expansion trends in Hanoi, Vietnam.
A project for **NASA Space Apps Challenge 2026** (Hanoi) by team **Long Geo – Geomatics**.

**Website:** https://nguyendailong289.github.io/NASA-SPACE-CHALLENGE-2026---URHEATIXEL/

## Website

| Part | Page | Content |
| --- | --- | --- |
| – | `index.html` | Cover page |
| 01 | `daily.html` | Daily land surface temperature (LST), 2017 and 2025, and annual mean LST |
| 02 | `normalized.html` | Normalized LST classes and class change |
| 03 | `builtup.html` | Built-up area 2017, 2025 and change (10 m) |
| 04 | `ndvi.html` | NDVI classes 2017, 2025 and class change |
| 05 | `hotspot.html` | LST – NDVI relationship and hotspots for intervention |

## Data

- NASA MODIS Terra MOD11A1 v061, LST_Day_1km (1 km, daily)
- Esri Sentinel-2 Land Cover, Built Area class (10 m)
- NASA MODIS Terra MOD13A2 v061, NDVI (1 km, 16-day composite)
- Administrative boundaries of Hanoi and its 126 communes/wards (2025), source: GIS.vn

## Updating the data

The `build_*.py` scripts read the raw data from the project folder (`1_Study area`, `2_Data`, `4_Results`, not included in this repository)
and rewrite the files in `data/` and `assets/maps/`:

```bash
python build_data.py
python build_normalized.py
python build_builtup.py
python build_builtup_tiles.py
python build_ndvi.py
python build_hotspot.py
```

Preview locally: `python -m http.server 8765`, then open http://localhost:8765
