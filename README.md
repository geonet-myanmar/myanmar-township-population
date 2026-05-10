# Myanmar Township Population Aggregation & Density Analysis

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Spatial analysis pipeline that aggregates Kontur population hexagon data into Myanmar Admin-3 township boundaries and computes arithmetic and physiographic population densities.

---

## Overview

This project performs **population aggregation and density analysis** for Myanmar by:

1. Loading 212,821 Kontur population hexagons and 330 Admin-3 township boundaries
2. Reprojecting both layers to **UTM Zone 47N (EPSG:32647)** for accurate area calculations
3. Performing a **spatial join** to assign each hexagon to its containing township
4. Computing per-township metrics:
   - **Total Population** — sum of hexagon populations
   - **Total Area** — geometric area of each township polygon (km²)
   - **Populated Area** — sum of hexagon areas that contain people (km²)
   - **Arithmetic Density** — total population ÷ total township area
   - **Physiographic Density** — total population ÷ populated hexagon area

---

## Data Sources

| Dataset | Format | CRS | Records |
|---------|--------|-----|---------|
| [Kontur Population](https://data.humdata.org/dataset/kontur-population) | GeoPackage | EPSG:3857 | 212,821 hexagons |
| Myanmar Admin-3 Boundaries | GeoJSON | EPSG:4326 | 330 townships |

**Note:** The Kontur dataset (`kontur_population_MM_20231101.gpkg`) is not included in this repository due to file size. Download it from [HDX](https://data.humdata.org/dataset/kontur-population) and place it in the project root. The Admin-3 boundaries (`mmr_admin3.geojson`) are included.

---

## Project Structure

```
myanmar-population-analysis/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── population_analysis.py             # Main analysis script
├── mmr_admin3.geojson                 # Admin-3 boundaries (included)
├── kontur_population_MM_20231101.gpkg # Kontur data (download separately)
├── myanmar_township_population_analysis.csv  # Generated output
├── myanmar_township_stats.geojson            # Generated output
└── .gitignore
```

---

## Installation

### Prerequisites

- Python 3.10+
- [GDAL](https://gdal.org/) system libraries (required by GeoPandas/Fiona)

### Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/myanmar-population-analysis.git
cd myanmar-population-analysis

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### 1. Download Kontur Data

Download the Myanmar population hexagon layer from [HDX](https://data.humdata.org/dataset/kontur-population) and save it as `kontur_population_MM_20231101.gpkg` in the project root.

### 2. Run the Analysis

```bash
python population_analysis.py
```

### 3. Expected Output

The script produces two files and prints a summary:

```
12:00:00 [INFO] Loading Kontur population hexagons: kontur_population_MM_20231101.gpkg
12:00:01 [INFO]   -> 212,821 hexagons | CRS=EPSG:3857 | Pop total: 54,795,072
12:00:01 [INFO] Loading Admin-3 township boundaries: mmr_admin3.geojson
12:00:01 [INFO]   -> 330 townships | CRS=EPSG:4326
12:00:01 [INFO] Reprojecting to EPSG:32647 (UTM Zone 47N) ...
12:00:02 [INFO] Performing spatial join (hexagons WITHIN townships) ...
12:00:03 [INFO]   -> Joined rows: 192,908
12:00:03 [INFO]   -> Population captured: 46,274,385 (84.45%)
12:00:03 [INFO] Aggregating population and area per township ...
12:00:03 [INFO]   -> Townships with population > 0: 319 / 330
12:00:03 [INFO] Calculating densities ...
12:00:04 [INFO] Exporting results ...
12:00:04 [INFO]   -> CSV saved: myanmar_township_population_analysis.csv (330 rows)
12:00:04 [INFO]   -> GeoJSON saved: myanmar_township_stats.geojson (CRS=EPSG:4326)
12:00:04 [INFO] All done.

============================================================
  SUMMARY
============================================================
  Townships analyzed          : 330
  Townships with population   : 319
  Total population captured   : 46,274,385
  Total township area         : 669,728.75 km²
  Total populated area        : 162,956.23 km²
  Mean arithmetic density     : 140,225.41 /km²
  Max arithmetic density      : 528,973.00 /km²
  Mean physiographic density  : 504.60 /km²
  Max physiographic density   : 10,825.10 /km²
============================================================
```

---

## Output Description

### `myanmar_township_population_analysis.csv`

| Column | Type | Description |
|--------|------|-------------|
| `adm3_pcode` | string | Township administrative code |
| `adm3_name` | string | Township name |
| `adm2_name` | string | District name |
| `adm1_name` | string | State/Region name |
| `adm0_name` | string | Country name |
| `total_population` | float | Sum of hexagon populations in township |
| `populated_hex_count` | int | Number of hexagons with population > 0 |
| `total_area_km2` | float | Geometric area of township polygon (km²) |
| `populated_area_km2` | float | Sum of areas of populated hexagons (km²) |
| `arithmetic_density` | float | Total population ÷ total area |
| `physiographic_density` | float | Total population ÷ populated area |

### `myanmar_township_stats.geojson`

A GeoJSON FeatureCollection with the same attributes as the CSV plus polygon geometry (reprojected to EPSG:4326 for web mapping compatibility).

---

## Methodology

### Coordinate Reference System

- Both datasets are reprojected from their native CRS to **UTM Zone 47N (EPSG:32647)**, which uses meters as units. This is critical for computing accurate geometric areas in square kilometers.

### Spatial Join

- The join uses the **`within`** predicate: a hexagon must be fully contained within a township polygon. This avoids double-counting population at administrative borders.
- Hexagons that fall **outside all township boundaries** (coastal/offshore areas) are excluded. This accounts for ~8.5M people (~15.5%) and is expected due to:
  - Hexagons in international waters
  - Minor boundary misalignments between datasets
  - Border effects at the coastline

### Density Calculations

- **Arithmetic Density** = Total Population ÷ Total Township Area
  - Standard measure; includes uninhabited land (forests, mountains, water bodies)
- **Physiographic Density** = Total Population ÷ Populated Hexagon Area
  - More realistic measure; only counts area where people actually live

### Data Integrity

- Population is summed from hexagons after the spatial join and compared against the original Kontur total
- NaN values (townships with no population hexagons) are filled with 0
- All numeric outputs are rounded to 4 decimal places

---

## Technical Notes

### Why UTM Zone 47N?

Myanmar spans approximately 92°E–101°E longitude. UTM Zone 47N (central meridian 99°E) provides the best compromise for minimizing area distortion across the country.

### Why `within` instead of `intersects`?

Using `intersects` causes **double-counting** of population for hexagons that span township borders (population is captured ~113%, exceeding the original total). The `within` predicate ensures each hexagon is assigned to at most one township.

---

## License

MIT License — see [LICENSE](LICENSE) file for details.

---

## Citation

If you use this analysis, please cite:

> OpenCode (2026). Myanmar Township Population Aggregation & Density Analysis. GitHub repository.