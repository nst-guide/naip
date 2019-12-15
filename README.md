# Hillshade

Generate high-resolution tiled imagery from USGS/USDA NAIP data

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

----------

This hasn't been updated to refer to NAIP yet...

## Installation

Clone the repository:

```
git clone https://github.com/nst-guide/hillshade
cd hillshade
```

This is written to work with Python >= 3.6. To install dependencies:

```
pip install click requests
```

This also has a dependency on GDAL. I find that the easiest way of installing
GDAL is through Conda:

```
conda create -n hillshade python gdal -c conda-forge
source activate hillshade
pip install click requests
```

You can also install GDAL via Homebrew on MacOS

```
brew install gdal
```

## Code Overview

#### `download.py`

Downloads USGS elevation data for a given bounding box.

```
> python download.py --help
Usage: download.py [OPTIONS]

Options:
  --bbox TEXT  Bounding box to download data for. Should be west, south, east,
               north.  [required]
  --overwrite  Re-download and overwrite existing files.
  --high_res   Download high-res 1/3 arc-second DEM.
  --help       Show this message and exit.
```

This script calls the [National Map API](https://viewer.nationalmap.gov/tnmaccess/api/index)
and finds all the 1x1 degree elevation products that intersect the given bounding
box. Right now, this uses 1 arc-second data, which has about a 30 meter
resolution. It would also be possible to use the 1/3 arc-second seamless data,
which is the best seamless resolution available for the continental US, but
those file sizes are 9x bigger, so for now I'm just going to generate from the 1
arc-second.

The script then downloads each of these files to `data/raw/`. By default,
it doesn't re-download and overwrite a file that already exists. If you wish to
overwrite an existing file, use `--overwrite`.

#### `unzip.sh`

Takes downloaded DEM data from `data/raw/`, unzips it, and places it in `data/unzipped/`.

#### `gdaldem`

Use `gdalbuildvrt` to generate a virtual dataset of all DEM tiles, `gdaldem` to
generate a hillshade, and `gdal2tiles` to cut the output raster into map tiles.

`gdaldem` options:

-   `-multidirectional`:

    > multidirectional shading, a combination of hillshading illuminated from 225 deg, 270 deg, 315 deg, and 360 deg azimuth.

-   `s` (scale):

    > Ratio of vertical units to horizontal. If the horizontal unit of the
    > source DEM is degrees (e.g Lat/Long WGS84 projection), you can use
    > scale=111120 if the vertical units are meters (or scale=370400 if they are
    > in feet)

    Note that this won't be exact, since those scale conversions are only really
    valid at the equator, but I had issues warping the VRT to a projection in
    meters, and it's good enough for now.

`gdal2tiles.py` options:

-   `--processes`: number of individual processes to use for generating the base tiles. Change this to a suitable number for your computer.
-   I also use my forked copy of `gdal2tiles.py` in order to generate high-res retina tiles

## Usage

First, download desired DEM tiles, unzip them, build a VRT (Virtual Dataset),
and optionally download my fork of `gdal2tiles` which allows for creating
512x512 pngs.

```bash
# Download for Washington state
python download.py --bbox="-126.7423, 45.54326, -116.9145, 49.00708"
# Or, download high-resolution 1/3 arc-second tiles
python download.py --bbox="-126.7423, 45.54326, -116.9145, 49.00708"
bash unzip.sh
# Create seamless DEM:
gdalbuildvrt data/dem.vrt data/unzipped/*.img
gdalbuildvrt data/dem_hr.vrt data/unzipped_hr/*.img
# Download my fork of gdal2tiles.py
# I use my own gdal2tiles.py fork for retina 2x 512x512 tiles
git clone https://github.com/nst-guide/gdal2tiles
cp gdal2tiles/gdal2tiles.py ./
```

**Terrain RGB:**

```bash
# Create a new VRT specifically for the terrain RGB tiles, manually setting the
# nodata value to be -9999
gdalbuildvrt -vrtnodata -9999 data/dem_hr_9999.vrt data/unzipped_hr/*.img
gdalwarp -r cubicspline -s_srs EPSG:4269 -t_srs EPSG:3857 -dstnodata 0 -co COMPRESS=DEFLATE data/dem_hr_9999.vrt data/dem_hr_9999_epsg3857.vrt
rio rgbify -b -10000 -i 0.1 --min-z 6 --max-z 13 -j 15 --format webp data/dem_hr_9999_epsg3857.vrt data/terrain_webp.mbtiles
rio rgbify -b -10000 -i 0.1 --min-z 6 --max-z 13 -j 15 --format png data/dem_hr_9999_epsg3857.vrt data/terrain_png.mbtiles
mb-util data/terrain_webp.mbtiles data/terrain_webp
mb-util data/terrain_png.mbtiles data/terrain_png
```

**Hillshade:**

```bash
# Generate hillshade
gdaldem hillshade -multidirectional -s 111120 data/dem.vrt data/hillshade.tif
gdaldem hillshade -igor -compute_edges -s 111120 data/dem_hr.vrt data/hillshade_igor_hr.tif

# Cut into tiles
./gdal2tiles.py --processes 10 data/hillshade.tif data/hillshade_tiles
./gdal2tiles.py --processes 10 data/hillshade_igor_hr.tif data/hillshade_igor_hr_tiles
```

**Slope angle shading:**

Note, the `data/slope_hr.tif` file in this example, comprised of the bounding boxes at the bottom, is a 70GB file itself. Make sure you have enough

```bash
# Generate slope
gdaldem slope -s 111120 data/dem.vrt data/slope.tif
gdaldem slope -s 111120 data/dem_hr.vrt data/slope_hr.tif

# Generate color ramp
gdaldem color-relief -alpha -nearest_color_entry data/slope.tif color_relief.txt data/color_relief.tif
gdaldem color-relief -alpha -nearest_color_entry data/slope_hr.tif color_relief.txt data/color_relief_hr.tif

# Cut into tiles
./gdal2tiles.py --processes 10 data/color_relief.tif data/color_relief_tiles
./gdal2tiles.py --processes 10 data/color_relief_hr.tif data/color_relief_hr_tiles
```

### Bboxes used:

For personal reference:

- `-120.8263,32.7254,-116.0826,34.793`
- `-122.4592,35.0792,-117.0546,36.9406`
- `-123.4315,37.0927,-118.0767,37.966`
- `-124.1702,38.0697,-118.5426,38.9483`
- `-124.1702,38.0697,-119.0635,38.9483`
- `-124.5493,39.0475,-120.0647,42.0535`
- `-124.6791,42.0214,-117.0555,46.3334`
- `-124.9103,46.0184,-117.0593,49.0281`
