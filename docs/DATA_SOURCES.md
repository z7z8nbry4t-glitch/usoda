# Data sources and how much weight each one carries

Last reviewed 26 October 2026. "Weight" says how far a source can be trusted for the question this atlas asks: where are reported sexual offences concentrated?

## Rule for combining sources

Sources are shown side by side and never merged into one number. Each has a different definition, geography and period. Adding them would produce a figure nobody could interpret.

## In the atlas now

| Source | Covers | Resolution | Definition | Weight | Notes |
|---|---|---|---|---|---|
| data.police.uk street-level archives | England, Wales, Northern Ireland, British Transport Police | Anonymised point, grouped here into ~4 km hexagons; monthly | *Violence and sexual offences* (sexual offences plus all other violence) | **High for where reports cluster; low for sexual offences alone** | Only open source with a map location. Counts match the live API exactly in sample checks. Gaps: Greater Manchester 35 of 120 months, BTP 89 of 120. |
| Scottish Government, *Recorded Crimes and Offences* (Police Scotland returns) | Scotland, 32 council areas | Council area; annual (April to March), 1996/97 to 2025/26 | Group 2 sexual crimes, with rape and attempted rape and sexual assault shown separately | **High for the Scottish definition; medium for place** | Official statistics, OGL v3.0. Council areas are large and uneven in size and population, so a big rural area can look as prominent as a dense city. Rates are published rounded to whole numbers per 10,000. Not comparable with the hexagons. |
| ONS Open Geography Portal boundaries | Police force areas (E and W); local authority districts (Scotland) | Polygons | None (geometry only) | High | OGL v3.0, contains OS data (c) Crown copyright. |
| OpenStreetMap tiles | Base map | n/a | n/a | n/a | ODbL. Attribution shown on the map. |

## Assessed and not yet added

| Source | What it would add | Why it is not in | Weight if added |
|---|---|---|---|
| Home Office *Police recorded crime open data tables* (by force area and community safety partnership; .ods, one financial year per sheet) | England and Wales local-authority-sized counts by offence group, with rape reported separately from 2016/17 | The guide confirms rape tables; I could not confirm a separate sexual offences group. It also excludes BTP at partnership level. Needs a parser and a check of the offence-group codes before use. | **Highest available for validating police.uk totals** and the nearest thing to a sexual-offence-only count for E and W. Next step. |
| Police Scotland quarterly council-area management reports (PDF) | More recent Scottish figures than the annual release | PDFs with changing layouts; unofficial status; the annual release already covers the same ground | Medium; use only for a "latest quarter" note, with a caveat |
| PSNI / NISRA police recorded crime bulletins | Northern Ireland sexual offences by district, with official definitions | NI points are already in police.uk. Bulletins are PDFs. Worth adding as a validation total, not a layer | Medium to high for validation |
| Scottish Index of Multiple Deprivation, crime domain | Small-area (data zone) crime context for Scotland | The domain combines several crime types and is not sexual-offence specific. Shows relative rank, not counts. Using it as a proxy for sexual offences would mislead | **Low** for this question. Do not use. |
| Scottish Crime and Justice Survey (SCJS) | National estimate of how much is *not* reported | National only, with no local breakdown; sexual victimisation items have wide confidence intervals | High for national context; unusable for a map |
| ONS Crime Survey for England and Wales (sexual offences prevalence and trends) | National prevalence, to show the gap between survey estimates and police-recorded counts | Same: national or regional only | High for context; unusable for a map |
| FOI disclosures (for example gov.scot and PSNI FOI logs) | Occasional finer breakdowns | One-off, inconsistent definitions, not reproducible by a schedule | Low; reference only |

## What I could not reach

- Scottish data below council area (data zone, police division, point level). No open sexual-crime feed exists at that level that I could find. The atlas does not guess it.
- statistics.gov.scot's SPARQL service and the older gov.scot spreadsheet links were unreachable from the build environment on 26 October 2026. The `data.gov.scot` CSV worked and is what the pipeline uses.

## Known limits that matter for weighting

1. **Different crime definitions.** Hexagon counts include non-sexual violence. Scottish counts are sexual crimes only, and include non-contact offences (for example communicating indecently and indecent photographs of children). Neither is "rape" alone.
2. **Reporting is not prevalence.** The surveys above show that most sexual offences are never reported to the police.
3. **Recording practice changes.** Rises and falls can reflect police recording and public willingness to report, not underlying events.
4. **Population and footfall.** Both layers are driven partly by where people live and visit. Only Scotland has a rate; hexagons are raw counts.
5. **Edge effects at the border.** About 220 hexagons (roughly 11,000 records over ten years) fall north of the border in the police.uk data. I have not established which force recorded them (British Transport Police is the likely cause). They overlap the Scotland layer and are a point to investigate.

## Next steps, in order of value

1. Parse the Home Office open data tables to cross-check force totals (validation, and rates per 1,000 with ONS population).
2. Add NISRA bulletin totals as an NI validation figure.
3. Resolve the Scottish border cells.
4. Add the national survey figures as a text panel, not a map layer.
