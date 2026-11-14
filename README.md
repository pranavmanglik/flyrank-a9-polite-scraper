# My polite book scraper

For this assignment, I built a small scraper for the first three catalogue pages on [Books to Scrape](https://books.toscrape.com/), a practice site from the [ToScrape sandbox](https://toscrape.com/). I wanted to collect a small, useful set of book details while keeping requests slow and predictable.

## What I built

- A scraper that follows catalogue links to find the next pages
- A clear user-agent, request timeout, and delay between real requests
- A local HTML cache so reruns don’t need to download the same pages again
- Pydantic validation for the book records
- Duplicate removal based on each book’s product URL
- JSON output for valid books, invalid records, and a run summary
- A switch for checking how the scraper handles a missing product page

Each valid book record has its title, product URL, price, availability, rating, description, source page, fetch time, and numeric GBP price. The description is optional because some product pages don’t have one.

## How I run it

From this project folder, I create a virtual environment, install the requirements, and run the offline checks:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Then I run the scraper:

```bash
python main.py
```

The results are written to `output/books.json`, `output/errors.json`, and `output/run-report.json`. The downloaded HTML is kept in `cache/`, which is ignored by Git. I can use `python main.py --refresh-cache` when I intentionally want to fetch the pages again. The optional failure-path check is `python main.py --inject-broken-url`.

## What I tested

On 14 November 2026, all five offline parser checks passed. They covered duplicate URLs, malformed product markup, a missing description, price normalization, and relative product URLs.

My regular run used the existing HTML cache. It processed 3 catalogue pages and 60 unique book URLs, wrote 60 valid records, and reported 0 invalid records and 0 failed pages. The report showed 63 cache hits and 0 pages fetched during that run.

I also ran `python main.py --inject-broken-url`. The deliberately invalid product URL returned a 404 and was skipped; the run still kept all 60 valid records and reported 1 failed page. These results are recorded in `output/run-report.json`.

The normal run command is:

```bash
python main.py
```

The offline tests don’t need network access. A fresh scrape does. I’ve limited this project to the Books to Scrape practice sandbox, and I’ll check a target’s rules and terms before reusing this scraper elsewhere.

## Test screenshot

I’ll add my terminal screenshot showing the passing parser checks and scraper summary here.

<!-- Add the screenshot here as assets/a9-scraper-test.png when it is available in this project folder. -->

## What I learned

This project gave me practice turning HTML into validated records and keeping a scraper polite and recoverable. Caching made repeated checks much faster, and the broken-URL run helped me see what happens when one product page can’t be fetched.

