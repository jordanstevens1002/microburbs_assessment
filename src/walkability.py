"""Walkability analysis utilities.

This module provides simple, extensible functions to compute a walkability
score from road and cadastre datasets. The implementations favor clarity
and testability over performance.

Functions:
 - load_gpkg(path, layer=None)
 - compute_road_length_density(roads_gdf, area_geom=None)
 - compute_intersection_density(roads_gdf, area_geom=None)
 - compute_parcel_density(cadastre_gdf, area_geom=None)
 - compute_walkability_score(roads_gdf, cadastre_gdf, area_geom=None, weights=None)

Notes:
 - Area units: geometries are assumed to be in a projected CRS with meters units.
 - Scales used for normalization are heuristic and should be tuned with real data.
"""
from typing import Optional, Dict

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
from shapely.ops import unary_union


def load_gpkg(path: str, layer: Optional[str] = None) -> gpd.GeoDataFrame:
    """Load a GeoPackage (or other vector file) into a GeoDataFrame.

    Args:
        path: path to the file
        layer: optional layer name for geopackage

    Returns:
        GeoDataFrame
    """
    return gpd.read_file(path, layer=layer)


def _apply_area_mask(gdf: gpd.GeoDataFrame, area_geom) -> gpd.GeoDataFrame:
    if area_geom is None:
        return gdf
    # ensure same CRS
    if gdf.crs is None:
        return gdf
    area = gpd.GeoSeries([area_geom], crs=gdf.crs)
    clipped = gpd.clip(gdf, area)
    return clipped


def compute_road_length_density(roads_gdf: gpd.GeoDataFrame, area_geom=None) -> float:
    """Compute road length density (km of road per km^2).

    Args:
        roads_gdf: GeoDataFrame of LineString roads in a projected CRS (meters)
        area_geom: optional polygon to clip to

    Returns:
        road density in km per km^2 (i.e., km / km^2)
    """
    if roads_gdf.empty:
        return 0.0
    gdf = _apply_area_mask(roads_gdf, area_geom)
    # total length in meters
    total_m = gdf.geometry.length.sum()
    # area in m^2
    if area_geom is None:
        area_m2 = gdf.total_bounds
        # compute convex hull area as fallback
        try:
            area_m2 = gpd.GeoSeries(unary_union(gdf.geometry)).unary_union.envelope.area
        except Exception:
            area_m2 = 1.0
    else:
        area_m2 = gpd.GeoSeries([area_geom], crs=gdf.crs).area.values[0]

    area_km2 = max(area_m2 / 1e6, 1e-9)
    total_km = total_m / 1000.0
    return total_km / area_km2


def compute_intersection_density(roads_gdf: gpd.GeoDataFrame, area_geom=None) -> float:
    """Estimate number of intersections per km^2.

    This is a straightforward (but O(n^2)) approach: pairwise intersection
    of road segments. For large networks, this should be replaced with
    a spatial index based method.
    """
    if roads_gdf.empty:
        return 0.0
    gdf = _apply_area_mask(roads_gdf, area_geom).reset_index(drop=True)
    points = []
    # include endpoints as potential intersections
    for geom in gdf.geometry:
        if geom is None:
            continue
        if isinstance(geom, LineString):
            pts = list(geom.coords)
            points.append(Point(pts[0]))
            points.append(Point(pts[-1]))

    # check pairwise intersections (naive)
    n = len(gdf)
    for i in range(n):
        gi = gdf.geometry.iloc[i]
        for j in range(i + 1, n):
            gj = gdf.geometry.iloc[j]
            try:
                inter = gi.intersection(gj)
            except Exception:
                inter = None
            if inter is None or inter.is_empty:
                continue
            # geometry could be point or linestring
            if inter.geom_type == "Point":
                points.append(inter)
            elif inter.geom_type in ("MultiPoint", "GeometryCollection"):
                for g in getattr(inter, 'geoms', []):
                    if g.geom_type == 'Point':
                        points.append(g)
                    else:
                        points.append(g.representative_point())
            else:
                # for LineString or other geometry, take a representative point
                try:
                    rp = inter.representative_point()
                    points.append(rp)
                except Exception:
                    continue

    if not points:
        return 0.0

    unique = gpd.GeoSeries(points).unary_union
    # count points: if MultiPoint or Point
    count = 0
    if unique.geom_type == "MultiPoint":
        count = len(unique.geoms)
    elif unique.geom_type == "Point":
        count = 1
    else:
        # fallback: attempt to count via conversion
        try:
            count = len(list(unique))
        except Exception:
            count = 0

    # compute area
    if area_geom is None:
        # approximate area via bounds envelope of roads
        area_m2 = gpd.GeoSeries(unary_union(gdf.geometry)).unary_union.envelope.area
    else:
        area_m2 = gpd.GeoSeries([area_geom], crs=gdf.crs).area.values[0]

    area_km2 = max(area_m2 / 1e6, 1e-9)
    return count / area_km2


def compute_parcel_density(cadastre_gdf: gpd.GeoDataFrame, area_geom=None) -> float:
    """Compute number of parcels per km^2.
    """
    if cadastre_gdf.empty:
        return 0.0
    gdf = _apply_area_mask(cadastre_gdf, area_geom)
    count = len(gdf)
    if area_geom is None:
        area_m2 = gdf.unary_union.envelope.area
    else:
        area_m2 = gpd.GeoSeries([area_geom], crs=gdf.crs).area.values[0]
    area_km2 = max(area_m2 / 1e6, 1e-9)
    return count / area_km2


def compute_walkability_score(roads_gdf: gpd.GeoDataFrame, cadastre_gdf: gpd.GeoDataFrame, area_geom=None, weights: Optional[Dict[str, float]] = None) -> float:
    """Compute a simple walkability score (0-100) combining metrics.

    Metrics used:
    - road density (km / km^2)
    - intersection density (count / km^2)
    - parcel density (count / km^2)

    We normalize each metric by a heuristic "high" value then compute a weighted
    average and scale to 0-100.
    """
    # compute metrics
    rd = compute_road_length_density(roads_gdf, area_geom)
    idens = compute_intersection_density(roads_gdf, area_geom)
    pdens = compute_parcel_density(cadastre_gdf, area_geom)

    # default weights
    if weights is None:
        weights = {"road": 0.4, "intersection": 0.4, "parcel": 0.2}

    # heuristic scales (values that represent a "high" score)
    scales = {"road": 5.0, "intersection": 100.0, "parcel": 500.0}

    road_score = min(rd / scales["road"], 1.0)
    int_score = min(idens / scales["intersection"], 1.0)
    parc_score = min(pdens / scales["parcel"], 1.0)

    score = (
        weights["road"] * road_score
        + weights["intersection"] * int_score
        + weights["parcel"] * parc_score
    )
    return float(max(0.0, min(score * 100.0, 100.0)))


if __name__ == "__main__":
    print("This module provides functions for walkability analysis. Import from code.")
