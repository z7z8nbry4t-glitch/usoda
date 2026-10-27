# If a source changes or stops

The atlas depends on four public sources. This note says what to watch, what breaks, and what to do. Last reviewed 27 October 2026.

## What watches for problems

- `monitor.yml` runs every day at about 07:17 UTC. It fails, and GitHub emails the repository owner, if the live atlas is behind the newest month on police.uk or if the last run of an update workflow failed.
- `update-data.yml` stops without publishing if a month looks wrong. The live site keeps the last good data.
- The tests in `tests/` check published totals against official figures, so a bad refresh fails the build.

## Dated copies

Every published aggregate is committed to Git by `usoda-bot`, so the history is the dated archive. To see the data as it stood on a date, check out the commit from that day. To keep a fixed copy, tag the commit (for example `git tag data-2026-10 <commit>` and push the tag). Raw police.uk archives are not kept in the repository; each can be downloaded again from data.police.uk for as long as police.uk offers it.

## By source

| Source | What could change | What breaks | What to do |
|---|---|---|---|
| data.police.uk street-level archives and API | A month is late, a force stops publishing, the file layout or column names change, or the site closes | The hourly update; the live-versus-upstream check; hexagons go stale | Leave the last good data live. Read the police.uk known-issues page and add a note to `data/annotations.json`. If a column changes, fix `scripts/ingest_archive.py` and add a test with a small sample. If the service closes, keep the last month, say so on the front page and in the About panel, and stop the update workflow. |
| Home Office police recorded crime open data tables | The page address or file name pattern changes; the offence classification changes; a quarter is revised | The force cross-check and the partnership layer | `scripts/fetch_csp.py` and `scripts/crossref_home_office.py` find the file through the gov.uk content API and fail loudly if no file is found. Check the new file by hand, then update the file pattern. The Home Office revises past quarters, so a refresh can change older numbers: that is expected. |
| Scottish Government, Recorded Crimes and Offences | A new year is published (next due 1 June 2027); the dataset address or groups change | The Scotland layer and its chart | `scripts/fetch_scotland.py` keeps every year. After a new release, check the totals against the published bulletin and update the test in `PublishedDataConsistencyTests`. |
| ONS boundaries and Census 2021 | New boundaries replace the December 2024 set; a Census 2031 rebuild | Partnership shapes and all rates | Update the boundary address in `scripts/fetch_csp.py` and `scripts/fetch_boundaries.py`, add any merged authorities to `GROUPS`, and re-run the tests. |
| PSNI bulletins | A new quarter is published | The Northern Ireland check only | Update `data/ni_validation.json` by hand from Table 1 of the newest bulletin and re-run the tests. |

## Rules that do not change when a source does

- Sources stay side by side and are never added into one number.
- Counts under 3 stay hidden.
- No news story or single incident moves a point.
- If a source cannot be kept to these rules, drop that source rather than bend the rules.
