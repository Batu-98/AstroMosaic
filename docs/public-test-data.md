# Public Observation Test Data

The local library is under `data/public-test-data/`. The [source manifest](../tests/fixtures/public_test_data.json) records the original download URL, byte count, SHA-256, credit and usage for each file. The source images, extracted exposures, derived panels and reports are stored in the ignored data directory.

## Available datasets

| Directory | Observations and format | Candidate uses |
| --- | --- | --- |
| `nightscape-images` | Richard Tatti's Milky Way Tree, three Nikon D750 NEFs at 35 mm, and Dead Tree, four Nikon Z 6 NEFs at 20 mm. Seven full-size linear RGB UInt16 TIFFs are under `linear/`. | Wide-angle solving, sky masks, mixed layers, footprints and photo seams. [Workshop originals](https://www.nightscapeimages.com.au/workshops---online.html) |
| `moana` | 202 light FITS files in four archives across two overlapping Lagoon Nebula pointings. Ten master darks and flats in the calibration archive. Each frame is 4656 × 3520. | Independent RGB panel stacks, cross-session background comparisons, exposure metadata and visible-band calibration. [M8 mosaic data](https://erellaz.com/moana/open-datasets/lagoon-nebula/) |
| `originstack` | 180 Bayer FITS light frames across the NGC 253, NGC 2024, M13 and M24 sessions, with each session's calibration and capture records. | Extended structure, saturated stars, crowded stellar fields and limited usable background. [Sample sessions](https://originstack.site/sample-sessions.html) |
| `nocturne` | Four registered and integrated RGB Float32 FITS cubes for M16, M45, M8 and NGC 7000, with verified Float32 RGB TIFF derivatives under `linear/`. | RGB cube interchange, solving, previews, faint-signal controls and export. [Sample data](https://nocturneastro.com/sample-data.html) |
| `astrobackyard` | Three calibrated and integrated RGB TIFFs from Trevor Jones. Andromeda is 10404 × 6930 UInt16. The Tulip and Witch Head are 6248 × 4176 and 6072 × 4042 Float32. The Witch Head carries an embedded ICC profile. | Large TIFF reads, assigned and embedded profiles, preview and export. [Practice files](https://astrobackyard.com/your-astrophoto-skills/) |

The 20 original downloads occupy 6.35 GiB and contain 389 individual light exposures, 22 calibration files and seven integrated masters. The prepared Nightscape and Nocturne TIFFs take another 1.33 GiB. The local inventory records the expanded byte count of each archive member.

### MOANA Lagoon Nebula

| Archive | Pointing | Exposure per light | Light files |
| --- | --- | ---: | ---: |
| `M8_T1_300_RGB.zip` | Tile 1 | 300 s | 31 |
| `M8_T2_300_RGB.zip` | Tile 2 | 300 s | 20 |
| `M8_T1P1_RGB.zip` | Tile 1 | 120 s | 66 |
| `M8_T2P1_RGB.zip` | Tile 2 | 120 s | 85 |
| `Calibration_Masters_G90.zip` | Common detector | Match dark exposure and flat filter | 10 calibration files |

The FITS dates cover July 19–24, 2023 UTC. Tile 1's 120 s data use July 22 and 24. Tile 2's use July 20 and 21. Across the four archives, gain 90 is shared and the headers identify 61 blue, 65 green, 46 red and 30 luminance exposures. Compose independent color panels from disjoint exposures and select the matching master dark for 120 s or 300 s and the corresponding master flat for each channel. The 300 s data provide an additional saturation and exposure control. [Acquisition and calibration notes](https://erellaz.com/moana/open-datasets/lagoon-nebula/)

### OriginStack sessions

| Case | Exposure | Repeatable test target | Record |
| --- | --- | --- | --- |
| NGC 253 Sculptor | 45 × 10 s | Large bright galaxy and limited empty sky | [Zenodo 23896454](https://doi.org/10.5281/zenodo.23896454) |
| NGC 2024 Flame | 45 × 10 s | Faint emission next to bright Alnitak | [Zenodo 23896467](https://doi.org/10.5281/zenodo.23896467) |
| M13 Hercules | 45 × 15 s | Crowded stellar core | [Zenodo 23896480](https://doi.org/10.5281/zenodo.23896480) |
| M24 Sagittarius Star Cloud | 45 × 5 s | Dense wide field with weak empty-sky support | [Zenodo 23896487](https://doi.org/10.5281/zenodo.23896487) |

Each session has 3056 × 2048 Bayer lights. Keep the dark, bias, flat and capture records from the same archive with its lights. Credit OriginStack and the specific Zenodo record. Credit Moana Project and Nocturne for their respective datasets. All three use CC BY 4.0. For Nightscape Images and AstroBackyard, retain the author credit and source link and consult the practice-data terms before redistributing originals. [MOANA license and credit](https://erellaz.com/moana/open-datasets/) · [OriginStack license and credit](https://originstack.site/sample-sessions.html#licence-and-credit) · [Nocturne license and credit](https://nocturneastro.com/sample-data.html)

## Restore or verify the library

From the checkout root, use the locked AstroMosaic environment. The default command checks byte counts and SHA-256. `--fetch` retrieves missing original files and publishes each after it passes both checks. Use one or more `--dataset` options for selected sources. An existing file with a different checksum is reported and can be inspected in place.

```powershell
.\.venv\Scripts\python.exe -m tools.public_test_data
.\.venv\Scripts\python.exe -m tools.public_test_data --dataset nightscape-images --fetch
```

The local `inventory.json` lists archive members and FITS acquisition headers. Run the standard Python ZIP extractor into a new working folder to prepare an archive for calibration or stacking. The original ZIP continues to identify the frozen source.

```powershell
.\.venv\Scripts\python.exe -m zipfile -e data/public-test-data/moana/M8_T1_300_RGB.zip output/moana-m8-tile1-300
.\.venv\Scripts\python.exe -m astromosaic inspect data/public-test-data/nocturne/linear/M45_300x10s_50min.tiff
```

## Prepare the wide-angle TIFFs

| Case | Camera and focal length | Native raster | Nominal horizontal field | Capture settings |
| --- | --- | --- | ---: | --- |
| Milky Way Tree | Nikon D750, 35 mm | 6032 × 4032 | 54° | 10 s, f/2.2, ISO 2500 |
| Dead Tree | Nikon Z 6, 20 mm | 6064 × 4040 | 84° | 15 s, f/2.2, ISO 6400 |

The nominal fields use a 36 mm sensor-width approximation. The TIFF preparation reads one capture at a time with RawPy 0.28.0 and LibRaw 0.22.2. It applies AHD demosaicing, the same daylight white balance and white level within each series, and a linear sRGB conversion. The original detector orientation and geometric distortion are preserved. The preparation JSON records the conversion settings, source and derived checksums, acquisition times and dimensions. Assign `linear-srgb` when loading these untagged test TIFFs into the photo workflow. [RawPy conversion parameters](https://letmaik.github.io/rawpy/api/rawpy.Params.html) · [Photo profile assignment](phase-8.md#assign-a-profile)

Install the pinned decoder in a separate local tooling directory. Run the preparation with a fresh destination. The script can reconstruct the four extracted NEFs from the pinned ZIP when they are missing.

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps --only-binary=:all: --target '.tooling/phase8d-wide-angle' rawpy==0.28.0
$env:PYTHONPATH = (Resolve-Path '.tooling/phase8d-wide-angle').Path
$env:OMP_NUM_THREADS = '2'
.\.venv\Scripts\python.exe -m tools.prepare_nightscape_test_panels data/public-test-data/nightscape-images output/nightscape-linear
```

The first strict Gaia check used the full unmasked images and a 30 s attempt limit. The first 35 mm frame returned a solution candidate with held-out positional P95 of 5.17 px. It exceeded the 1 px solve limit. The other six attempts timed out. The local reports are in `nightscape-images/geometry/`. Test sky masks and pointing hints before using the panoramas for native overlap photometry.

## Prepare the Nocturne RGB TIFFs

The published masters store RGB as three FITS planes. Use the Float32 TIFF derivatives in AstroMosaic, where primary FITS input accepts a two-dimensional monochrome plane. The preparation preserves channel order and sample values and records a binary validity raster from finite samples. Reopening with tifffile matched every covered RGB value and coverage code for 30,820,300 pixels. The originals and derived checksums are recorded in `nocturne/linear/preparation.json`.

```powershell
.\.venv\Scripts\python.exe -m tools.prepare_rgb_fits_test_panels data/public-test-data/nocturne output/nocturne-linear
```

## Local verification

All 20 original byte counts and SHA-256 values passed, and all ten ZIP archives passed member CRC checks. The four OriginStack archives also matched the publisher's SHA-256 values. A fresh download of the four Nightscape originals verified against the manifest. Fresh preparations reproduced all seven Nightscape and all four Nocturne TIFF checksums.

AstroMosaic's panel reader reopened a 64 × 64 center tile from each of the fourteen available RGB TIFFs. The thirteen uncompressed TIFFs passed with a 64 MiB read budget. The Tulip TIFF uses Deflate with 223 rows per strip. Its center tile required 87.80 MiB of decode reservation, reported the limit at 64 MiB and passed at 128 MiB. The sample results are in local `panel-read-check.json`.

## Choose data by test purpose

Use original exposures, calibrated derivatives or independently integrated panel stacks for brightness matching. Record the processing chain and retain a known common response and the measured sky variation. Per-panel gradient removal, local tone edits and uncharacterized color changes move a dataset to preview, import or geometry tests. Completed single stacks are useful for those tests and for export. The [8D acceptance procedure](phase-8d.md#selection-and-acceptance) applies to a full-scene Advanced reference.

The existing SDSS, ESO ALPACA and MAST controls cover independent overlap, mixed wide-angle geometry and detector flats, respectively. The source checksums and reproduction instructions are in the phase records. [SDSS comparisons](phase-8d.md#independent-calibrated-sdss-panels) · [ESO ALPACA reference](phase-6.md#calibrated-alpaca-mixed-reference) · [NIRCam flat references](phase-8d.md#optical-calibration-intake)

Telescope Live's landscape collection uses member access. Deep Sky West's practice archive uses a sign-up form. Their public catalogs are additional leads for future observations. [Telescope Live landscape datasets](https://telescope.live/blog/free-access-landscape-astrophotography-datasets-telescope-live-and-stellarxperiences) · [Deep Sky West data access](https://www.deepskywest.com/free-downloads-v2)
