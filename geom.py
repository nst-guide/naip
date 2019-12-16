import geopandas as gpd
import pint

ureg = pint.UnitRegistry()


def buffer(
        gdf: gpd.GeoDataFrame, distance: float, unit: str,
        epsg=3488) -> gpd.GeoSeries:
    """Create buffer around GeoDataFrame

    Args:
        gdf: dataframe with geometry to take buffer around
        distance: distance for buffer
        unit: units for buffer distance, either ['mile', 'meter', 'kilometer']
        epsg: local projection for creating buffer, should have meter projection

    Returns:
        GeoDataFrame with buffer polygon
    """

    # Reproject to EPSG 3488 (meter accuracy)
    # https://epsg.io/3488
    gdf = gdf.to_crs(epsg=epsg)

    # Find buffer distance in meters
    unit_dict = {
        'mile': ureg.mile,
        'meter': ureg.meter,
        'kilometer': ureg.kilometer, }
    pint_unit = unit_dict.get(unit)
    if pint_unit is None:
        raise ValueError(f'unit must be one of {list(unit_dict.keys())}')

    distance_m = (distance * pint_unit).to(ureg.meters).magnitude
    buffer = gdf.buffer(distance_m)

    # Reproject back to EPSG 4326 for saving
    buffer = buffer.to_crs(epsg=4326)

    return buffer
