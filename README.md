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
Usage: download.py [OPTIONS] [FILE]...

  Download raw NAIP imagery for given geometry

Options:
  --bbox TEXT                     Bounding box to download data for. Should be
                                  west, south, east, north.
  -b, --buffer-dist FLOAT         Buffer to use around provided geometry. Only
                                  used with --file argument.
  --buffer-unit [mile|meter|kilometer]
                                  Units for buffer.  [default: mile]
  --buffer-projection INTEGER     EPSG code for projection used when creating
                                  buffer. Coordinates must be in meters.
                                  [default: 3488]
  --overwrite                     Re-download and overwrite existing files.
  --help                          Show this message and exit.
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
python download.py -b 2 example.geojson

# Create virtual raster:
# The -b flags take each of the RGB bands at full opacity.
# The -addalpha sets areas with no source raster as transparent.
# See https://github.com/nst-guide/naip/issues/1
gdalbuildvrt -b 1 -b 2 -b 3 -addalpha data/naip.vrt data/raw/*.jp2

# Download my fork of gdal2tiles.py
# I use my own gdal2tiles.py fork for retina 2x 512x512 tiles
git clone https://github.com/nst-guide/gdal2tiles
cp gdal2tiles/gdal2tiles.py ./

# Generate tiled imagery
# --exclude excludes transparent tiles from output tileset
# You may want to set max zoom level 15
./gdal2tiles.py --processes 10 --exclude data/naip.vrt data/naip_tiles
```

### Compression

Running this for a .5 mile buffer for the entire Pacific Crest Trail, with
512x512 pixel tiles and a max zoom of 16 generated ~60GB of png files. Around
~45GB of these tiles are in just zoom level 16, and while I'll probably
set a max zoom of 15 in the future, ~15GB is still more than I want to serve.

Note that these CLI commands worked on macOS, and some might need different syntax on Linux.

#### WebP

**Note**: It appears from limited inspection that Mapbox GL JS shows WebP images
slightly pixelated? See [#2](https://github.com/nst-guide/naip/issues/2).

Google's webp format is a great compressor of png images. Running the `cwebp`
cli (you can download from Google's site or through homebrew ) and setting the
quality to 80/100 reduces file size by about 85%
```
> cwebp 10299.png -q 80 -o 10299.webp
```

By default this is _lossy_ compression. You can set `-lossless` if you'd like,
but lossy is fine for my needs.

The docs for the `-q` option say:

> Specify the compression factor for RGB channels between 0 and 100. The default is 75.
>
> In case of lossy compression (default), a small factor produces a smaller file
> with lower quality. Best quality is achieved by using a value of 100.
>
> In case of lossless compression (specified by the -lossless option), a small
> factor enables faster compression speed, but produces a larger file. Maximum
> compression is achieved by using a value of 100.

I think this is really confusing because a higher `-q` value is less compressed
when running lossy and more compressed when running lossless!

To create a full hierarchy of webp images:
```bash
cd data/naip_tiles
for f in */*/*.png; do mkdir -p ../naip_tiles_webp/$(dirname $f); cwebp $f -q 80 -o ../naip_tiles_webp/$f ; done
```

Unfortunately, webp isn't supported everywhere, namely on older browsers and on
all iOS browsers.

#### Lossy PNG

Because WebP images aren't supported on all devices, I also need to serve a PNG
layer. Unlike the [terrain-rgb elevation
layer](https://github.com/nst-guide/hillshade), for which lossy compression
would erase all meaning of the encoded elevation values, for regular images
lossy compression won't make much of a visual difference.

From limited searching, the best open source, command line PNG compressor seems
to be [`pngquant`](https://pngquant.org/). This creates PNG images that can be
displayed on any device. You can install with `brew install pngquant`.

In order to create a directory of compressed images:
```bash
cd data/naip_tiles
find . -name '*.png' -print0 | xargs -0 -P8 -L1 pngquant --ext -comp.png --quality=70-80
```

Setting quality to `70-80` appears to create files that are about 25% of the
original size.

I couldn't figure out an easy way to write the output png files to a new
directory. By default they're written in the same directory as the original
file, with an added extension.

```bash
# in data/naip_tiles already
mkdir ../naip_tiles_png
# First move all tiles with extension -comp.png to the new directory
# Take out --remove-source-files if you want to copy, not move the files
# I use rsync because I couldn't figure out an easy way with `mv` to move while
# keeping the directory structure.
rsync -a --remove-source-files --include "*/" --include="*-comp.png" --exclude="*" . ../naip_tiles_png/
# Then rename all of the files, taking off the -comp suffix
cd ../naip_tiles_png
find . -type f -name "*-comp.png" -exec rename -s '-comp.png' '.png' {} +
```

When run on Halfmile's PCT track data with a .5 mile buffer (including
alternates), the resulting data after pngquant compression has file sizes:
```
> du -csh * | sort -h
```

| Directory size | Zoom level |
|----------------|------------|
| 8.0K           | 4          |
| 20K            | 5          |
| 36K            | 6          |
| 108K           | 7          |
| 348K           | 8          |
| 1.2M           | 9          |
| 4.1M           | 10         |
| 15M            | 11         |
| 60M            | 12         |
| 240M           | 13         |
| 979M           | 14         |
| 3.8G           | 15         |
| 15G            | 16         |
| 20G            | total      |

I'll probably serve up to zoom 15 through the web browser, and maybe up to zoom
14 for offline download.
