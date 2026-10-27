# Data sources and how much weight each one carries

Last reviewed 26 October 2026. "Weight" says how far a source can be trusted for the question this atlas asks: where are reported sexual offences concentrated?

## Rule for combining sources

Sources are shown side by side and never merged into one number. Each has a different definition, geography and period. Adding them would produce a figure nobody could interpret.

## In the atlas now

| Source | Covers | Resolution | Definition | Weight | Notes |
|---|---|---|---|---|---|
| data.police.uk street-level archives | England, Wales, Northern Ireland, British Transport Police | Anonymised point, grouped here into ~4 km hexagons; monthly | *Violence and sexual offences* (sexual offences plus all other violence) | **High for where reports cluster; low for sexual offences alone** | Only open source with a map location. Counts match the live API exactly in sample checks. Gaps: Greater Manchester 35 of 120 months, BTP 89 of 120. |
| Scottish Government, *Recorded Crimes and Offences* (Police Scotland returns) | Scotland, 32 council areas | Council area; annual (April to March), 1996/97 to 2025/26 | Group 2 sexual crimes, with rape and attempted rape and sexual assault shown separately | **High for the Scottish definition; medium for place** | Official statistics, OGL v3.0. Council areas are large and uneven in size and population, so a big rural area can look as prominent as a dense city. Rates are published rounded to whole numbers per 10,000. Not comparable with the hexagons. |
| Home Office, *Police recorded crime open data tables* (Community Safety Partnership; updated 22 Oct 2026; England and Wales; quarterly, April 2020 to June 2026) | Optional green layer: sexual offences by partnership | Partnership (one or more local authorities); quarterly | Offence group *Sexual offences* only, with rape counted separately | **High for the Home Office definition; medium for place** | `scripts/fetch_csp.py` writes `data/csp.json` and `data/csp.geojson`. Shapes are ONS local authority boundaries (December 2024) joined to match each partnership; rates use Census 2021 residents. No British Transport Police. Five names (North Hampshire, South Nottinghamshire, South Warwickshire, North Worcestershire, South Worcester) cannot be placed from their names alone and are listed in the data as not drawn; "Unassigned" rows and Manchester Airport have no area. Never added to hexagon counts or to Scotland, and not ranked against either. |
| Home Office, *Police recorded crime open data tables* (Police Force Area; updated 22 Oct 2026; England and Wales; quarterly, to June 2026) | Validation and force-level context for England and Wales | Force and financial year; Violence against the person, Sexual offences (rape as a subgroup) | The same scope as the police.uk category once the two Home Office groups are added together | **Highest of all sources for force totals**, and the only one that separates sexual offences | Used for cross-checking, never added to police.uk counts and never applied to hexagons. Results in `data/crossref.json`. No Scotland or Northern Ireland. Does not give locations. |
| ONS Census 2021: usual residents (TS001) and workday population (WD002) by LSOA, with ONS population-weighted centroids | Denominators for rates per 1,000, England and Wales only (59.6 million residents; checks against the Census total) | LSOA (about 1,500 people) grouped into the same hexagons | People, not crimes | **High for denominators, but dated (census day 21 March 2021)** | `scripts/fetch_population.py` writes `data/population.json`. Residents understate busy centres (the City of London has 4,395 residents and 82,767 workday population); workday population misses visitors and nightlife (seaside towns such as Skegness show very high resident rates). Show both, never one alone. |
| police.uk *Known issues* page (official notices) | Reasons for gaps: Greater Manchester, British Transport Police, Gloucestershire, Avon and Somerset | Per force | n/a | **High as an explanation; adds no counts** | Curated in `data/annotations.json` with source links and a checked date. |
| ONS Open Geography Portal boundaries | Police force areas (E and W); local authority districts (Scotland) | Polygons | None (geometry only) | High | OGL v3.0, contains OS data (c) Crown copyright. |
| OpenStreetMap tiles | Base map | n/a | n/a | n/a | ODbL. Attribution shown on the map. |

## Assessed and not yet added

| Source | What it would add | Why it is not in | Weight if added |
|---|---|---|---|
| Police Scotland quarterly council-area management reports (PDF) | More recent Scottish figures than the annual release | PDFs with changing layouts; unofficial status; the annual release already covers the same ground | Medium; use only for a "latest quarter" note, with a caveat |
| PSNI / NISRA police recorded crime bulletins | Northern Ireland sexual offences by district, with official definitions | NI points are already in police.uk. Bulletins are PDFs. Worth adding as a validation total, not a layer | Medium to high for validation |
| Scottish Index of Multiple Deprivation, crime domain | Small-area (data zone) crime context for Scotland | The domain combines several crime types and is not sexual-offence specific. Shows relative rank, not counts. Using it as a proxy for sexual offences would mislead | **Low** for this question. Do not use. |
| Scottish Crime and Justice Survey (SCJS) | National estimate of how much is *not* reported | National only, with no local breakdown; sexual victimisation items have wide confidence intervals | High for national context; unusable for a map |
| ONS Crime Survey for England and Wales (sexual offences prevalence and trends) | National prevalence, to show the gap between survey estimates and police-recorded counts | Same: national or regional only | High for context; unusable for a map |
| FOI disclosures (for example gov.scot and PSNI FOI logs) | Occasional finer breakdowns | One-off, inconsistent definitions, not reproducible by a schedule | Low; reference only |

## Cross-reference results (26 October 2026)

- 396 force-years compared (financial years 2017/18 to 2025/26): **297 within 5%, 59 within 10%, 23 differ by more than 10%**, 17 cannot be checked because police.uk has gaps. The median ratio of police.uk to Home Office is 1.00.
- Differences are consistent with timing and revisions: police.uk is a monthly snapshot of data as first published, while the Home Office series is revised each quarter.
- Persistent shortfalls (about 6 to 10% lower in police.uk): Dorset and Kent. Treat the police.uk counts for those forces as a slight undercount.
- **Greater Manchester** has no police.uk street-level rows for the last two years. The Home Office recorded 138,223 violence and sexual offences there in 2025/26 (similar in scale to the West Midlands). The popup shows that official total. It is not drawn into the hexagons, because the Home Office gives no locations and an estimate would be invented data.
- **British Transport Police** has street rows for only part of the series. The Home Office total is shown the same way.
- **Sexual offences share.** Across England and Wales in 2025/26, sexual offences were 10.0% of violence plus sexual offences, ranging by force from about 8% to 13%. The popups show each force's share. It is a force-wide figure and is not applied to cells.

### Northern Ireland and force rates (27 October 2026)

- **Northern Ireland check.** The Police Service of Northern Ireland bulletin for the year to March 2026 gives 4,459 sexual offences (1,267 rape) and 39,891 violence against the person. Together that is 44,350. police.uk holds 42,535 Northern Ireland records for the same 12 months, 95.9% of the police figure and inside the 5% band used elsewhere. The figures are in `data/ni_validation.json` and shown in the Northern Ireland force popup. Sexual offences cannot be mapped on their own for Northern Ireland, because police.uk does not separate them. Source: [PSNI bulletin](https://www.psni.police.uk/system/files/2026-05/525903612/Police%20Recorded%20Crime%20Bulletin%20Period%20Ending%2031st%20March%202026.pdf).
- **Force rates.** Force popups now show Home Office sexual offences for 2025-26 per 1,000 residents, using Census 2021 residents already in `data/population.json`. The City of London is left out because its resident population is about 4,400. Census 2021 is older than the offence year, so growing areas read slightly high. Mid-2025 estimates from ONS were considered and not used, to keep one set of denominators across the atlas.

### Partnership layer checks (27 October 2026)

- For 2025/26 the partnership rows add to 215,076 sexual offences (rape 74,628). The force tables give 217,271 (rape 74,697). The gap of 2,195 is British Transport Police, which the partnership table leaves out. `PublishedDataConsistencyTests` asserts that the drawn total plus unassigned rows never exceeds the force total and stays above 95% of it.
- Counts under 3 in a window are shown as "fewer than 3" and given no colour, in line with the hexagons.
- The partnership names are of mixed age. Some use districts that have since merged into unitary authorities (for example Allerdale, Carlisle and Copeland now sit in Cumberland). `GROUPS` in `scripts/fetch_csp.py` adds such partnerships together and uses the current authority's shape. Each entry needs the authorities' own names to support it.

## Duplicates and double counting

- **Exact duplicate rows** (same crime ID and same coordinates in one force-month file) are counted once: 160,923 rows (0.84% of 19.19 million) across the ten-year window. Northern Ireland is excluded from this check, because 93% of its rows reuse a crime ID, so IDs cannot identify duplicates there.
- **Months are never ingested twice.** The four overlapping archives are cut so that each month comes from one archive only.
- **Police.uk and the Scottish Government** do not overlap: one covers England, Wales, Northern Ireland and British Transport Police; the other covers Police Scotland returns.
- **British Transport Police in Scotland.** All 3,327 BTP points that fall inside Scottish council boundaries in the window are kept out of the hexagons, since BTP is not part of the Scottish Government's Police Scotland figures and a few rail points would make Scotland look covered. The count is published in the data status panel.
- Cross-month repeats of the same crime ID (about 0.02% of rows) are left in, because a record can legitimately reappear with changed details.

## News and other secondary sources

- **News stories are not used to move or add points.** Matching reports to individual incidents would be locating specific offences, which the project's privacy rules exclude (the police anonymise locations on purpose). They are not an official record either.
- News and official notices are used only to explain *aggregate* gaps (for example Greater Manchester's IT move). For that, police.uk's own known-issues page is a better and more stable source, so that is what the atlas cites.
- **Survey figures (now pulled).** The ONS pages could be fetched directly. `data/national_context.json` holds the Crime Survey for England and Wales results for the years ending March 2026 and March 2025 (prevalence, reporting, the effect of new offences on recorded counts), each with its source link. They appear in the "National context" panel and are not combined with map counts. The March 2026 survey used redeveloped questions and is not comparable with earlier years.
- **Scottish survey: only an older figure.** The gov.scot Scottish Crime and Justice Survey 2023/24 and 2024/25 pages, the data.gov.scot dataset search, and the ONS-style bulletins were blocked or returned empty. The only Scottish survey figure read is the 2019/20 one (3.6% of adults; women 6.1%, men 0.8%, since age 16), second-hand through Rape Crisis Scotland. It is labelled as older and second-hand.
- **Still not pulled:** PSNI/NISRA Northern Ireland tables (the one document I could open held no counts; the series is in a PSNI spreadsheet, Table 14).

### Cross-checks between sources (26 October 2026)

| Check | Result |
|---|---|
| ONS recorded sexual offences, England and Wales, year ending March 2026 (217,567) against the Home Office force tables summed (217,271) | 0.14% apart; consistent |
| Rape offences: ONS 74,727 against Home Office force tables 74,697 | 0.04% apart |
| Scottish Government sexual crimes 2024/25 (14,892; rape and attempted rape 2,897; sexual assault 5,124) against this atlas's Scotland layer | Exact match |
| Survey estimate (about 900,000 victims, year ending March 2025) against recorded offences (209,079) | Roughly four victims for each recorded offence, consistent with ONS's statement that most are not reported |

These are asserted by tests (`PublishedDataConsistencyTests`), so a future data refresh that breaks them fails the build.

## What "fine tuning the location data" means here

Cell counts are not moved, smoothed or re-assigned. Fine tuning is limited to checks that make the existing locations easier to read: duplicates removed; rail points inside Scotland left out; rates per 1,000 using small-area population; force-level location completeness (Avon and Somerset, Gloucestershire and City of London publish 9 to 10% of records without a location) shown in popups; and known-issue notes. Scaling counts up to make up for missing coordinates was considered and rejected, because it would assume missing records fall in the same places as located ones.

## What I could not reach

- Scottish data below council area (data zone, police division, point level). No open sexual-crime feed exists at that level that I could find. The atlas does not guess it.
- statistics.gov.scot's SPARQL service and the older gov.scot spreadsheet links were unreachable from the build environment on 26 October 2026. The `data.gov.scot` CSV worked and is what the pipeline uses.

## Known limits that matter for weighting

1. **Different crime definitions.** Hexagon counts include non-sexual violence. Scottish counts are sexual crimes only, and include non-contact offences (for example communicating indecently and indecent photographs of children). Neither is "rape" alone.
2. **Reporting is not prevalence.** The surveys above show that most sexual offences are never reported to the police.
3. **Recording practice changes.** Rises and falls can reflect police recording and public willingness to report, not underlying events.
4. **Population and footfall.** Both layers are driven partly by where people live and visit. Only Scotland has a rate; hexagons are raw counts.
5. **Different time bases.** The Home Office series is quarterly and revised; police.uk is monthly as first published. Comparisons use complete financial years only.

## Next steps, in order of value

1. Force-level rates per 1,000 using the Home Office numerators (the population totals per force are already in `data/population.json`).
2. Add NISRA bulletin totals as a Northern Ireland validation figure.
3. Add the national survey figures (Crime Survey for England and Wales, Scottish Crime and Justice Survey) as a text panel, not a map layer.
