from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import urlretrieve

import click
import geopandas as gpd
import requests
from dateutil.parser import parse as date_parse
from shapely.geometry import box

from grid import get_cells


@click.command()
@click.option(
    '--bbox',
    required=False,
    default=None,
    type=str,
    help='Bounding box to download data for. Should be west, south, east, north.'
)
@click.option(
    '--file',
    required=False,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    default=None,
    help=
    'Geospatial file with geometry to download data for. Will download all image tiles that intersect this geometry. Must be a file format that GeoPandas can read.'
)
@click.option(
    '-b',
    '--buffer-dist',
    required=False,
    type=float,
    default=None,
    show_default=True,
    help='Buffer to use around provided geometry. Only used with --file argument.'
)
@click.option(
    '--buffer-unit',
    required=False,
    show_default=True,
    type=click.Choice(['mile', 'meter', 'kilometer'], case_sensitive=False),
    default='mile',
    help='Units for buffer.')
@click.option(
    '--buffer-projection',
    required=False,
    show_default=True,
    type=int,
    default=3488,
    help=
    'EPSG code for projection used when creating buffer. Coordinates must be in meters.'
)
@click.option(
    '--overwrite',
    is_flag=True,
    default=False,
    help="Re-download and overwrite existing files.")
def main(bbox, file, buffer_dist, buffer_unit, buffer_projection, overwrite):
    """Download raw NAIP imagery for given geometry
    """
    if (bbox is None) and (file is None):
        raise ValueError('Either bbox or file must be provided')

    if (bbox is not None) and (file is not None):
        raise ValueError('Either bbox or file must be provided')

    geometries = None
    if bbox:
        geometries = [box(bbox)]

    if file:
        gdf = gpd.read_file(file).to_crs(epsg=4326)

        # Create buffer if arg is provided
        if buffer_dist is not None:
            from geom import buffer
            gdf = buffer(
                gdf,
                distance=buffer_dist,
                unit=buffer_unit,
                epsg=buffer_projection)

        geometries = list(get_cells(gdf.unary_union, cell_size=0.0625))

    if geometries is None:
        raise ValueError('Error while computing geometries')

    print('Downloading NAIP imagery for geometries:')
    for geometry in geometries:
        print(geometries[0].bounds)

    download_dir = Path('data/raw')
    download_dir.mkdir(parents=True, exist_ok=True)
    local_paths = download_naip(
        geometries, directory=download_dir, overwrite=overwrite)
    with open('paths.txt', 'w') as f:
        f.writelines(_paths_to_str(local_paths))


def download_naip(geometries, directory, overwrite):
    """
    Args:
        - geometries (list): list of bounding boxes (as shapely objects)
        - directory (pathlib.Path): directory to download files to
        - overwrite (bool): whether to re-download and overwrite existing files
    """
    urls = []
    for geometry in geometries:
        urls.extend(get_urls(geometry.bounds))

    local_paths = []
    counter = 1
    for url in urls:
        print(f'Downloading file {counter} of {len(urls)}')
        local_path = download_url(url, directory, overwrite=overwrite)
        if local_path is not None:
            local_paths.append(local_path)

        counter += 1

    return local_paths


def get_urls(bbox):
    """
    Args:
        - bbox (tuple): bounding box (west, south, east, north)
        - high_res (bool): If True, downloads high-res 1/3 arc-second DEM
    """
    url = 'https://viewer.nationalmap.gov/tnmaccess/api/products'
    product = 'USDA National Agriculture Imagery Program (NAIP)'
    extent = '3.75 x 3.75 minute'
    fmt = 'JPEG2000'

    params = {
        'datasets': product,
        'bbox': ','.join(map(str, bbox)),
        'outputFormat': 'JSON',
        'version': 1,
        'prodExtents': extent,
        'prodFormats': fmt}

    res = requests.get(url, params=params)
    res = res.json()

    # If I don't need to page for more results, return
    if len(res['items']) == res['total']:
        return select_results(res)

    # Otherwise, need to page
    all_results = [*res['items']]
    n_retrieved = len(res['items'])
    n_total = res['total']

    for offset in range(n_retrieved, n_total, n_retrieved):
        params['offset'] = offset
        res = requests.get(url, params=params).json()
        all_results.extend(res['items'])

    # Keep all results with best fit index >0
    return select_results(all_results)


def select_results(results):
    """Select relevant images from results

    Selects most recent image for location, and results with positive fit index.
    """
    # Select results with positive bestFitIndex
    results = [x for x in results['items'] if x['bestFitIndex'] > 0]

    # counter_dict schema:
    # counter_dict = {
    #     bounds: {
    #         'dateCreated': date,
    #         'downloadURL'
    #     }
    # }
    counter_dict = {}
    for result in results:
        bounds = result_to_bounds(result)

        # does something already exist with these bounds?
        existing = counter_dict.get(bounds)

        # If exists, check if newer
        if existing is not None:
            existing_date = existing['dateCreated']
            this_date = date_parse(result['dateCreated'])
            if this_date < existing_date:
                continue

        # Doesn't exist yet or is newer, so add to dict
        counter_dict[bounds] = {
            'dateCreated': date_parse(result['dateCreated']),
            'downloadURL': result['downloadURL']}

    return [x['downloadURL'] for x in counter_dict.values()]


def result_to_bounds(res_item):
    minx = str(res_item['boundingBox']['minX'])
    maxx = str(res_item['boundingBox']['maxX'])
    miny = str(res_item['boundingBox']['minY'])
    maxy = str(res_item['boundingBox']['maxY'])
    return ','.join((minx, miny, maxx, maxy))


def download_url(url, directory, overwrite=False):
    # Cache original download in self.raw_dir
    parsed_url = urlparse(url)
    filename = Path(parsed_url.path).name
    local_path = Path(directory) / filename
    if overwrite or (not local_path.exists()):
        try:
            urlretrieve(url, local_path)
        except HTTPError:
            print(f'File could not be downloaded:\n{url}')
            return None

    return local_path.resolve()


def _paths_to_str(paths):
    return [str(path) for path in paths]


if __name__ == '__main__':
    main()
