# Cloudflare Pages: setup checklist

The repository is ready. These are the only steps that need a person, because they involve signing in and authorising GitHub.

## Before you start

- Repository: `z7z8nbry4t-glitch/usoda`, branch `main` (public).
- Nothing to build. The site is static files plus one Pages Function (`functions/api/[[path]].js`).
- Free plan limits are not a concern: about 150 files, largest under 1 MB.

## Steps (about 5 minutes)

1. Sign in to the Cloudflare dashboard.
2. *Workers and Pages*, *Create*, *Pages*, *Connect to Git*.
3. Authorise the Cloudflare GitHub app for **only** `z7z8nbry4t-glitch/usoda`.
4. Select the repository. Settings:

   | Setting | Value |
   |---|---|
   | Production branch | `main` |
   | Framework preset | None |
   | Build command | (empty) |
   | Build output directory | `.` |
   | Environment variables | none |

5. *Save and Deploy*. The site appears at `https://usoda.alphatedigital.co.uk` (or `usoda-xxx.pages.dev` if the name is taken).

## Verify

```
python3 scripts/verify_deploy.py https://usoda.alphatedigital.co.uk
```

Expected: PASS for the page, `data/meta.json`, window and boundary files, the Scotland files, and 32 council areas. The API proxy check and the "atlas up to date" check are warnings, not failures, if the proxy is not running. Then open the site and confirm that the Data status panel reads up to date.

## After the first deploy

1. In GitHub, go to *Actions*, then *Update USODA data*, then *Run workflow*, with *force* ticked. This proves the full rebuild. It commits `data/` to `main`, which redeploys the site.
2. Do not add branch protection on `main` that blocks the `usoda-bot` commits, or the hourly update will fail.
3. *Update Scotland layer* runs monthly and commits only when the Scottish data has changed.

## What is already prepared

- `_headers`: security headers (Content-Security-Policy tested against the site), and short caching for `data/` so refreshed data appears within five minutes.
- `functions/api/[[path]].js`: allow-listed, GET-only proxy to three police.uk endpoints, cached for an hour.
- `wrangler.toml`: lets you deploy by hand with `npx wrangler pages deploy .`.
- `scripts/verify_deploy.py`: the smoke test above.

## Known point

Because the output directory is the repository root, the scripts, tests and README are also served as static files. They contain no secrets (the repository is public). If you prefer to keep them off the site, the fix is to move the site into a `public/` folder and set the output directory to `public`; that needs changes to the data paths in the scripts and workflow, so it was left out.

## Cloudflare's direction

Cloudflare now recommends Workers with static assets for new projects. Pages remains supported. This site works on either, and a move later would not change the data pipeline.

## If you would rather not use Cloudflare

GitHub Pages works too: *Settings*, *Pages*, *Deploy from a branch*, `main`, `/ (root)`. The API proxy does not run there, and the site falls back to calling police.uk directly. `_headers` is ignored on GitHub Pages.
