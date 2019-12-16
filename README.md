# NAIP

Generate high-resolution tiled imagery from USDA NAIP data

## Overview

I use [OpenMapTiles](https://github.com/openmaptiles/openmaptiles) to create
self-hosted vector map tiles. However, that doesn't provide aerial imagery.

### Source data

The US Department of Agriculture (USDA) captures high-resolution aerial imagery
for the continental US. The USGS's web portal allows for easy downloading of
NAIP imagery.

According to the [NAIP
website](https://www.fsa.usda.gov/programs-and-services/aerial-photography/imagery-programs/naip-imagery/):

> NAIP imagery is acquired at a one-meter ground sample distance (GSD) with a
> horizontal accuracy that matches within six meters of photo-identifiable
> ground control points, which are used during image inspection.


### Integration with `style.json`

The style JSON spec tells Mapbox GL how to style your map. Add the raster imagery
tiles as a source to overlay them with the other sources.

Within `sources`, each object key defines the name by which the later parts of
`style.json` should refer to the layer. Note the difference between a normal
raster layer and the terrain RGB layer.

```json
"sources": {
  "openmaptiles": {
    "type": "vector",
    "url": "https://api.maptiler.com/tiles/v3/tiles.json?key={key}"
  },
  "naip": {
    "type": "raster",
    "url": "https://example.com/url/to/tile.json",
  	"tileSize": 512
  }
}
```

Where the `tile.json` for a raster layer should be something like:

```json
{
    "attribution": "<a href=\"https://www.usgs.gov/\" target=\"_blank\">© USGS</a>",
    "description": "NAIP Imagery",
    "format": "png",
    "id": "naip",
    "maxzoom": 15,
    "minzoom": 11,
    "name": "naip",
    "scheme": "tms",
    "tiles": ["https://example.com/url/to/tiles/{z}/{x}/{y}.png"],
    "version": "2.2.0"
}
```

Later in the style JSON, refer to the raster to style it. This example shows the
raster layer between zooms 11 and 15 (inclusive), and sets the opacity to 0.2 at
zoom 11 and 1 at zoom 15, with a gradual ramp in between.
```json
{
  "id": "naip",
  "type": "raster",
  "source": "naip",
  "minzoom": 11,
  "maxzoom": 15,
  "paint": {
    "raster-opacity": {
      "base": 1.5,
      "stops": [
        [
          11,
          0.2
        ],
        [
          15,
          1
        ]
      ]
    }
  }
}
```

## Installation

Clone the repository:

```
git clone https://github.com/nst-guide/naip
cd naip
```

This is written to work with Python >= 3.6. To install dependencies:

```
pip install -r requirements.txt
```

This also has dependencies on some C/C++ libraries. If you have issues
installing with pip, try Conda:
```
conda env create -f environment.yml
source activate naip
```

## Code Overview

#### `download.py`

Downloads USGS elevation data for a given bounding box.

```
> python download.py --help
Usage: download.py [OPTIONS]

  Download raw NAIP imagery for given geometry

Options:
  --bbox TEXT  Bounding box to download data for. Should be west, south, east,
               north.
  --file FILE  Geospatial file with geometry to download data for. Will
               download all image tiles that intersect this geometry. Must be
               a file format that GeoPandas can read.
  --overwrite  Re-download and overwrite existing files.
  --help       Show this message and exit.
```

This script calls the [National Map
API](https://viewer.nationalmap.gov/tnmaccess/api/index) and finds all the
3.75'x3.75' NAIP imagery files that intersect the given bounding box or
geometry. By default, it only downloads the most recent image, if more than one
exist.

The script then downloads each of these files to `data/raw/`. By default,
it doesn't re-download and overwrite a file that already exists. If you wish to
overwrite an existing file, use `--overwrite`.

#### `gdal`

Use `gdalbuildvrt` to generate a virtual dataset of all image tiles and
`gdal2tiles` to cut the output raster into map tiles.

`gdal2tiles.py` options:

-   `--processes`: number of individual processes to use for generating the base
    tiles. Change this to a suitable number for your computer.
-   I also use my forked copy of `gdal2tiles.py` in order to generate high-res retina tiles

## Usage

First, download desired DEM tiles, unzip them, build a VRT (Virtual Dataset),
and optionally download my fork of `gdal2tiles` which allows for creating
512x512 pngs.

```bash
# Download for some geometry
python download.py --file example.geojson

# Create virtual raster:
# Use -srcnodata 0 so that areas without an image are transparent
gdalbuildvrt -srcnodata 0 data/naip.vrt data/raw/*.jp2

# Download my fork of gdal2tiles.py
# I use my own gdal2tiles.py fork for retina 2x 512x512 tiles
git clone https://github.com/nst-guide/gdal2tiles
cp gdal2tiles/gdal2tiles.py ./

# Generate tiled imagery
# --exclude excludes transparent tiles from output tileset
./gdal2tiles.py --processes 10 --exclude data/naip.vrt data/naip_tiles
```
