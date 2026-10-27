# UK Sexual Offence Density Atlas (USODA)

An interactive map of reported violence and sexual offences in the UK. It uses official open police data, pre-aggregated into a rolling ten-year window.

**Read this first.** The map shows the police category *Violence and sexual offences*. That category combines sexual offences with all other violence. The open data cannot separate them. The map shows counts of reports, not rates and not prevalence. Many sexual offences are never reported.

## What the site does

The front page (`index.html`) explains the atlas, its limits and its uses. The map itself is `atlas.html`.

- Shows a zoomable, pannable map (touch and keyboard supported) with a density heat layer and clickable hexagonal cells.
- Marks hotspots with a dark outline (the top 3% of cells in the selected window).
- Shows the count, time window and source note when you click or tap a cell.
- Offers windows of 10 years, 5 years, 3 years, 12 months, or any single month.
- Colours cells by count or, in England and Wales, by reports a year per 1,000 residents or per 1,000 workday population (grey where no reliable rate exists).
- Offers a police force area layer with totals. It greys out areas with incomplete data.
- Shows the data status: latest month, newest month upstream, coverage and the last successful ingest.
- Lists the top 15 cells as buttons, as a keyboard-friendly alternative to the map.

## Data sources

| Source | Used for | Licence |
|---|---|---|
| [data.police.uk](https://data.police.uk/) monthly archives (`/data/archive/YYYY-MM.zip`) and availability API (`/api/crimes-street-dates`) | Street-level records, category `violent-crime` | Open Government Licence v3.0 |
| Home Office, [police recorded crime open data tables](https://www.gov.uk/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables) (Police Force Area, England and Wales) | Cross-check of force totals; sexual-offence share by force | Open Government Licence v3.0 |
| ONS Census 2021 (usual residents, workday population) and population-weighted LSOA centroids | Rates per 1,000 for England and Wales cells | Open Government Licence v3.0 |
| ONS Open Geography Portal, Police Force Areas (December 2023) EW BUC | Force area boundaries | Open Government Licence v3.0; contains OS data (c) Crown copyright |
| Scottish Government, [Recorded Crimes and Offences](https://data.gov.scot/dataset/recorded_crimes_and_offences) (Police Scotland returns) | Scotland layer: sexual crimes by council area, annual | Open Government Licence v3.0 |
| ONS Open Geography Portal, Local Authority Districts (December 2024) UK BUC | Scottish council boundaries | Open Government Licence v3.0 |
| OpenStreetMap | Base map | ODbL |

The police publish about 36 months in each archive. A 120-month window therefore needs four archives (L, L-36, L-72, L-108, where L is the newest month). The pipeline downloads them one at a time.

### Scotland

Scotland appears as 32 council-area shapes (purple), annual, from `scripts/fetch_scotland.py` into `data/scotland_la.json` and `data/scotland_la.geojson`. It uses the Scottish definition of sexual crimes (rape and attempted rape and sexual assault are also listed in the popup). That definition is narrower than the police.uk category, so Scotland must not be added to, or ranked against, the hexagons. A monthly workflow refreshes it. Every year since 1996/97 is kept so the Scotland popup can chart the full history.

An optional green layer shows Home Office *Sexual offences* by community safety partnership for England and Wales (quarterly, from April 2020, rate per 1,000 residents), from `scripts/fetch_csp.py` into `data/csp.json` and `data/csp.geojson`. It is a different measure from the hexagons and from Scotland, is off by default, and is never added to or ranked against either. A monthly workflow checks for a new quarterly release.

For how each source is weighted, and what was assessed and left out, see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

### Not yet included

- **Scotland below council-area level.** There is no open street-level or small-area feed for Scotland.
- **Rates per 1,000.** The force layer shows raw counts. Population rates need ONS mid-year estimates.

## Known data gaps

The pipeline measures coverage in every build and writes it to `data/meta.json`. At the 2026-08 build:

- Greater Manchester Police has street-level data for only 35 of 120 months. Almost nothing appears after June 2019.
- British Transport Police has 89 of 120 months.
- Devon and Cornwall (110 of 120) and Gloucestershire (113 of 120) have gaps.
- Overall force-month coverage is 97.41%. 97.93% of category records carry a location.

The site warns about these gaps in a banner and in cell popups. Do not read a quiet area in a gappy force as a safe area.

## How the data is processed

1. `scripts/poll_availability.py` reads the newest published month. It ingests only when that month is newer than `data/meta.json`.
2. `scripts/ingest_archive.py` reads each `*-street.csv`, keeps rows with `Crime type = Violence and sexual offences`, drops rows without a coordinate or outside UK bounds, and counts them into hexagons. It keeps no crime IDs, street names or LSOA names.
3. `scripts/build_aggregates.py` sums months into windows, hides cells with fewer than 3 records, and writes the static files in `data/`.
4. `scripts/run_pipeline.py` runs steps 1 to 3 end to end and statelessly (download, ingest, delete the ZIP, build).
5. `scripts/crossref_home_office.py` compares each force's police.uk total with the Home Office tables (violence against the person plus sexual offences) for complete financial years and writes `data/crossref.json`. It is validation only.

Also in step 2: exact duplicate rows (same crime ID and coordinates in one file) are counted once, and British Transport Police points inside Scotland are left out of the cells. Both counts are published in `data/meta.json` and the data status panel. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for results and weighting.

**Hex grid.** The plane is `x = longitude * K`, `y = latitude`, with `K = cos(54.5 deg)`. Cells are pointy-top hexagons with a circumradius of 0.02 deg of latitude (about 2.2 km, or about 4 km across). Cells are addressed by axial coordinates (q, r). `scripts/usoda_common.py` and `assets/app.js` implement the same maths. The grid is deliberately coarse so that it never resolves individual streets.

**Output files** (all under `data/`):

| File | Content |
|---|---|
| `meta.json` | Window, hex definition, quality metrics, force gaps, timestamps |
| `windows/{10y,5y,3y,12m}.json` | `[q, r, count]` per cell |
| `months/YYYY-MM.json` | The same, for one month |
| `force_totals.json` | Monthly category count per force. A missing month is a gap, not a zero |
| `pfa.geojson` | Force area boundaries (run `scripts/fetch_boundaries.py` to refresh) |
| `population.json` | Residents and workday population per hexagon and force (England and Wales, Census 2021). Refresh with `scripts/fetch_population.py` |
| `national_context.json` | Curated survey and official-total figures, each with a source link (shown in the National context panel) |
| `annotations.json` | Curated notes on known data problems, with source links |
| `crossref.json` | Home Office comparison per force and financial year, with agreement bands |
| `scotland_la.json`, `scotland_la.geojson` | Scotland council-area layer |
| `csp.json`, `csp.geojson` | England and Wales partnership layer (Home Office sexual offences, quarterly) |

## Update cycle

`.github/workflows/update-data.yml` polls hourly. When a new month appears, it rebuilds the window, commits `data/` to `main` and so triggers a Cloudflare Pages redeploy. You can also run it by hand (*Actions*, *Run workflow*, tick *force*). The site itself checks upstream once an hour and shows when a newer month exists than the atlas holds.

Police data lags by one to three months, and recent months can still change.

## Run it locally

```
python3 scripts/run_pipeline.py            # about 7 GB of downloads, one ZIP on disk at a time
python3 scripts/fetch_boundaries.py        # only if boundaries need refreshing
python3 -m http.server 8000                # then open http://localhost:8000
python3 -m unittest discover -s tests -v   # offline tests
python3 scripts/validate_samples.py work/archives/2026-08.zip 2026-08   # needs the ZIP kept (--keep-archives)
```

Set `USODA_WORK` to choose where temporary files go. The default is `work/` (ignored by Git). Python 3.10 or later, standard library only.

## Testing and validation

- `tests/test_pipeline.py` uses a synthetic archive. It checks the category filter, coordinate handling, hexagon maths, suppression, gap detection, window fall-back, and that no street names or IDs reach the output.
- `scripts/validate_samples.py` compares archive counts with the live API for four city-centre boxes. On 26 October 2026 all four matched exactly for 2026-08 (Birmingham 289, Leeds 217, Cardiff 218, Belfast 141).
- `scripts/crossref_home_office.py` validates force totals against the Home Office tables: 297 of 396 force-years agree within 5% (see `docs/DATA_SOURCES.md`).

## Deployment (Cloudflare Pages)

Full checklist: [docs/CLOUDFLARE.md](docs/CLOUDFLARE.md). Smoke test: `python3 scripts/verify_deploy.py https://usoda.alphatedigital.co.uk`.

1. In the Cloudflare dashboard, choose *Workers and Pages*, *Create*, *Pages*, *Connect to Git*.
2. Select `z7z8nbry4t-glitch/usoda`, branch `main`.
3. Build command: leave empty (or `exit 0`). Output directory: `.` (the repository root).
4. Save. The site appears at `https://usoda.pages.dev` (or the name Cloudflare assigns). The main address is `https://usoda.alphatedigital.co.uk`, and `functions/_middleware.js` redirects the old address to it. Every push to `main` redeploys.

`functions/api/[[path]].js` is a Pages Function. It proxies three fixed, read-only police.uk endpoints with a one-hour edge cache. It is not an open proxy. The site works without it (it falls back to calling police.uk directly).

`wrangler.toml` supports `npx wrangler pages deploy .` for manual deploys.

## Privacy and responsible use

- The police anonymise locations by snapping them to a map point. This project does not try to reverse that, and nobody should use it to identify a victim, an offender or an address.
- Cells with fewer than 3 records are hidden. Cells are about 4 km across.
- The site shows no street names and keeps no record-level data.
- Counts follow population, footfall and recording practice. Do not use cell counts to compare how safe areas are.

## Extension points

- **Scotland.** Do not extrapolate point data. Add finer data only if an official open source appears.
- **Rates.** Join ONS mid-year population estimates to the force layer to show rates per 1,000.
- **Vector tiles** if the number of cells grows beyond what canvas rendering handles well.
- **Year-on-year comparison** using the per-month files.

## Licence

Code: add a licence file of your choice (none is set yet). Data: Open Government Licence v3.0. Vendored libraries (Leaflet, leaflet.heat) are BSD-2-Clause; their licences are in `assets/vendor/`.


## Trend charts

Popups for cells, force areas, partnerships and Scottish council areas include a small inline SVG bar chart (no chart library). Cell charts load every `data/months/*.json` file on first use; the others use data already loaded. Charts ignore the time-window control and never combine sources.

## Licence

Code: MIT (`LICENSE`). Data and third-party material: see `DATA-LICENCE.md`; the data is Open Government Licence v3.0 and stays with its publishers.

## Downloads, monitoring and upstream changes

`scripts/export_downloads.py` writes CSV copies of the published aggregates to `data/downloads/` (linked from the front page). `monitor.yml` checks daily that the live atlas is level with police.uk. `docs/UPSTREAM_CHANGES.md` says what to do if a source changes or stops.

## Force pages and view links

`force.html?f=<slug>` shows one force: Home Office sexual offences, rate, monthly police.uk records, gaps and notes (`force.html` alone lists every force). On the map, the address after `#` records the window, colour mode, layers and position, so "Copy link to this view" reopens the same view; `atlas.html#f=<slug>` zooms to a force. Charts are shared in `assets/charts.js`.

## Domain and contact

The main address is `https://usoda.alphatedigital.co.uk`, a CNAME to `usoda.pages.dev` set at the DNS host (Mythic Beasts) and added as a custom domain on the Pages project. The old `usoda.pages.dev` address redirects to it with a permanent redirect that keeps the path and query string. Preview deployments are not redirected. Contact: usoda@alphatedigital.co.uk (forwarded; there is no visitor tracking).
