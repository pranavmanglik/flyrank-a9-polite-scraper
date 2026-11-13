# W5 A9 — The polite scraper

This project collects book records from the first three catalogue pages of [Books to Scrape](https://books.toscrape.com/), a fictional bookstore in the [ToScrape practice sandbox](https://toscrape.com/). The sandbox describes the bookstore as a place that wants to be scraped and intended for beginner practice. The target's `robots.txt` returned HTTP 404 when checked on 2026-11-13; that means no robots file was found, not that a missing file grants permission. Keep this project limited to the named sandbox and re-check site rules and terms before using any scraper elsewhere.

The scraper sends an identifying user-agent, uses a 10-second timeout, waits at least 500 ms between real requests, checks HTTP status, caches downloaded HTML, discovers the next catalogue pages from their links, validates records with Pydantic, and writes a run report. The optional broken-URL switch exercises the per-page failure path against the sandbox itself.

## Run

Use Python 3.10 or newer from this folder:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Run the five offline parser checks with `python -m unittest discover -s tests -v`.

The first run may take around half a minute because it spaces out requests. It creates `cache/` and `output/books.json`, `output/errors.json`, and `output/run-report.json`. Re-running uses local HTML cache. Use `python main.py --refresh-cache` only when you intentionally want to download the pages again. Use `python main.py --inject-broken-url` to prove one missing detail page is skipped while the remaining records are saved.

## Record shape

Each validated record contains the eight raw fields (`title`, `product_url`, `price_text`, `availability_text`, `rating_text`, `description`, `source_page`, `fetched_at`) plus numeric `price_gbp`. The product URL is the identity, so duplicate books are written once. Records with invalid fields are sent to `output/errors.json` instead of `books.json`.

## Verification recorded on 2026-11-13

`python -m unittest discover -s tests -v` passes five offline parser checks: price normalization, relative URL resolution, missing description, duplicate URL removal, and a malformed product fixture.

The live run against the practice sandbox produced 3 catalogue pages, 60 discovered and unique URLs, 60 valid records, 0 invalid records, and 0 failed pages. The cached rerun again produced 60 valid records with 63 cache hits. `--inject-broken-url` preserved all 60 valid records and reported 1 failed page. The run output is in `output/run-report.json`; `output/books.json` contains the collected records.

## Evidence to add before submission

Add a genuine `curl -i` output (not applicable to this CLI project), one real record and one limitation you observed. Cache files are ignored by Git; publish a sample output, not the downloaded HTML cache. The sample output should be reviewed for size and data handling before publication.

This assignment needs no browser: the book data is already in the HTML returned by the server. A browser would add time and memory without helping this pipeline.

Ethics note: use an official API when one exists; do not bypass logins, paywalls, or blocks; collect only the data needed; and check the target's current rules and terms before reusing code.

## Assignment steps

Suggested commits: classify the target; fetch and cache HTML; discover pages; extract fields; normalize and validate; handle failures and report; document and publish. The bonus AI version should stay isolated and requires your own prompt, run comparison, and concrete findings. Add genuine results and make the public GitHub repo required by the assignment.
