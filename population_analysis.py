#!/usr/bin/env python3
"""
Myanmar Township Population Aggregation & Density Analysis
==========================================================

Loads Kontur population hexagon data and Myanmar Admin-3 township boundaries,
reprojects to UTM Zone 47N, performs spatial joins, and calculates population
metrics (arithmetic & physiographic density) per township.

Author : opencode
Date   : 2026-05-10
License: MIT

Outputs
-------
- myanmar_township_population_analysis.csv
- myanmar_township_stats.geojson
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

TARGET_CRS = "EPSG:32647"  # UTM Zone 47N (meters) — suitable for Myanmar

KONTUR_FILE = "kontur_population_MM_20231101.gpkg"
ADMIN3_FILE = "mmr_admin3.geojson"

OUTPUT_CSV = "myanmar_township_population_analysis.csv"
OUTPUT_GEOJSON = "myanmar_township_stats.geojson"

ADMIN3_DISPLAY_COLS = [
    "adm3_pcode",
    "adm3_name",
    "adm2_name",
    "adm1_name",
    "adm0_name",
]

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Core Functions ───────────────────────────────────────────────────────────


def load_datasets(kontur_path: str, admin_path: str) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load both source datasets and log their properties."""
    logger.info("Loading Kontur population hexagons: %s", kontur_path)
    kontur = gpd.read_file(kontur_path)
    logger.info(
        "  -> %s hexagons | CRS=%s | Pop total: %s",
        len(kontur),
        kontur.crs,
        f"{kontur['population'].sum():,.0f}",
    )

    logger.info("Loading Admin-3 township boundaries: %s", admin_path)
    admin = gpd.read_file(admin_path)
    logger.info("  -> %s townships | CRS=%s", len(admin), admin.crs)

    return kontur, admin


def reproject(kontur: gpd.GeoDataFrame, admin: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Reproject both layers to the target UTM CRS."""
    logger.info("Reprojecting to %s (UTM Zone 47N) for accurate area calculations ...", TARGET_CRS)
    kontur_utm = kontur.to_crs(TARGET_CRS)
    admin_utm = admin.to_crs(TARGET_CRS)
    logger.info("  -> Kontur CRS: %s", kontur_utm.crs)
    logger.info("  -> Admin3 CRS: %s", admin_utm.crs)
    return kontur_utm, admin_utm


def spatial_join(
    kontur_utm: gpd.GeoDataFrame, admin_utm: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Perform spatial join and verify population retention."""
    logger.info("Performing spatial join (hexagons WITHIN townships) ...")
    admin_subset = admin_utm[ADMIN3_DISPLAY_COLS + ["geometry"]].copy()
    joined = gpd.sjoin(kontur_utm, admin_subset, how="inner", predicate="within")
    logger.info("  -> Joined rows: %s", len(joined))

    original_pop = kontur_utm["population"].sum()
    joined_pop = joined["population"].sum()
    logger.info("  -> Original population : %s", f"{original_pop:,.0f}")
    logger.info("  -> Captured population: %s (%.2f%%)", f"{joined_pop:,.0f}", joined_pop / original_pop * 100)
    return joined


def aggregate_per_township(joined: gpd.GeoDataFrame, admin_utm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Aggregate population and area metrics per township."""
    logger.info("Aggregating population and area per township ...")

    # Population aggregates from hexagons
    pop_agg = joined.groupby("adm3_pcode").agg(
        total_population=("population", "sum"),
        populated_hex_count=("population", "count"),
        populated_area_km2=("geometry", lambda g: g.area.sum() / 1e6),
    ).reset_index()

    # Township geometry and total area
    admin_agg = admin_utm[ADMIN3_DISPLAY_COLS + ["geometry"]].copy()
    admin_agg["total_area_km2"] = admin_agg["geometry"].area / 1e6

    # Merge — outer to keep all townships
    result = admin_agg.merge(pop_agg, on="adm3_pcode", how="left")

    # Fill NaN for townships with no population hexagons
    for col in ["total_population", "populated_hex_count", "populated_area_km2"]:
        result[col] = result[col].fillna(0)
    result["populated_hex_count"] = result["populated_hex_count"].astype(int)

    logger.info("  -> Townships with population > 0: %s / %s", (result["total_population"] > 0).sum(), len(result))
    return result


def compute_densities(result: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Calculate arithmetic and physiographic density."""
    logger.info("Calculating densities ...")

    # Arithmetic density: total population / total township area
    result["arithmetic_density"] = result["total_population"] / result["total_area_km2"]

    # Physiographic density: total population / populated hexagon area
    result["physiographic_density"] = result.apply(
        lambda r: r["total_population"] / r["populated_area_km2"] if r["populated_area_km2"] > 0 else 0,
        axis=1,
    )

    # Round for readability
    for col in ["total_area_km2", "populated_area_km2", "arithmetic_density", "physiographic_density"]:
        result[col] = result[col].round(4)

    logger.info("  -> Arithmetic density range : %s - %s", result["arithmetic_density"].min(), result["arithmetic_density"].max())
    logger.info("  -> Physiographic density range: %s - %s", result["physiographic_density"].min(), result["physiographic_density"].max())
    return result


def export_results(result: gpd.GeoDataFrame) -> None:
    """Write CSV and GeoJSON output files."""
    logger.info("Exporting results ...")

    # CSV (drop geometry)
    csv_cols = ADMIN3_DISPLAY_COLS + [
        "total_population",
        "populated_hex_count",
        "total_area_km2",
        "populated_area_km2",
        "arithmetic_density",
        "physiographic_density",
    ]
    result[csv_cols].to_csv(OUTPUT_CSV, index=False)
    logger.info("  -> CSV saved: %s (%s rows)", OUTPUT_CSV, len(result))

    # GeoJSON (reproject to EPSG:4326 for compatibility)
    result_4326 = result.to_crs("EPSG:4326")
    result_4326.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    logger.info("  -> GeoJSON saved: %s (CRS=EPSG:4326)", OUTPUT_GEOJSON)


def print_summary(result: gpd.GeoDataFrame) -> None:
    """Print final summary statistics."""
    total_area = result["total_area_km2"].sum()
    pop_area = result["populated_area_km2"].sum()
    total_pop = result["total_population"].sum()

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Townships analyzed          : {len(result)}")
    print(f"  Townships with population   : {(result['total_population'] > 0).sum()}")
    print(f"  Total population captured   : {total_pop:,.0f}")
    print(f"  Total township area         : {total_area:,.2f} km²")
    print(f"  Total populated area        : {pop_area:,.2f} km²")
    print(f"  Mean arithmetic density     : {result['arithmetic_density'].mean():.2f} /km²")
    print(f"  Max arithmetic density      : {result['arithmetic_density'].max():.2f} /km²")
    print(f"  Mean physiographic density  : {result['physiographic_density'].mean():.2f} /km²")
    print(f"  Max physiographic density   : {result['physiographic_density'].max():.2f} /km²")
    print("=" * 60)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    try:
        kontur, admin = load_datasets(KONTUR_FILE, ADMIN3_FILE)
        kontur_utm, admin_utm = reproject(kontur, admin)
        joined = spatial_join(kontur_utm, admin_utm)
        result = aggregate_per_township(joined, admin_utm)
        result = compute_densities(result)
        export_results(result)
        print_summary(result)
        logger.info("All done.")
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
