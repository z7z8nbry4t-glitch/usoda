# UK Sexual Offence Density Atlas (USODA)

Interactive heatmap prototype for reported violence and sexual offences density in the UK.

## Data Sources
- Primary: data.police.uk API (category: violent-crime = Violence and sexual offences). Street-level anonymised lat/lng. Monthly releases.
- Supplementary: ONS / Home Office Police Force Area and CSP tables for rates.
- Scotland: Aggregated local authority data only (gov.scot).

## Features
- Zoomable/pannable OpenStreetMap base.
- Load density for current map view by querying the public API for selected month.
- Heat layer + clickable approximate grid markers showing reported counts.
- Rolling 10-year full national aggregation requires offline processing of archive ZIPs (data.police.uk/data/archive/).

## Limitations
- Locations anonymised (not exact).
- "violent-crime" bundles sexual offences with other violence.
- Monthly lag; hourly polls would only detect new monthly drops.
- API rate limits; production would pre-aggregate.
- Scotland not covered at street level in this feed.

## Cloudflare Deployment (recommended free domain)

1. Install Wrangler: `npm i -g wrangler`
2. Authenticate: `wrangler login`
3. From the usoda directory: `npx wrangler pages deploy . --project-name=usoda`
4. Site will be live at `usoda.pages.dev` (or similar). Custom domain can be attached later in Cloudflare dashboard.

The included wrangler.toml configures static output. Optional Pages Function in functions/api/ provides a caching proxy for the police API (hourly cache) if you route fetches through /api/... to avoid any client-side rate limits.

Open Government Licence applies to source data.
