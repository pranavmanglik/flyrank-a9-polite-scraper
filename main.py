"""Polite, cached scraper for the Books to Scrape practice sandbox (W5 A9)."""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError, field_validator

BASE_URL = "https://books.toscrape.com/"
MAX_CATALOGUE_PAGES = 3
REQUEST_TIMEOUT_SECONDS = 10
MIN_REQUEST_INTERVAL_SECONDS = 0.5
USER_AGENT = "FlyrankInternship-A9/1.0 (educational scraper; Books to Scrape sandbox)"
ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"


class BookRecord(BaseModel):
    # These are the fields we trust after cleaning a page; Pydantic checks every record.
    title: str = Field(min_length=1)
    product_url: str
    price_text: str = Field(min_length=1)
    price_gbp: float = Field(ge=0)
    availability_text: str = Field(min_length=1)
    rating_text: str = Field(min_length=1)
    description: str | None
    source_page: str
    fetched_at: str = Field(min_length=1)

    @field_validator("product_url", "source_page")
    @classmethod
    def require_absolute_https_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("must be an absolute HTTPS URL")
        return value


class PoliteScraper:
    def __init__(self, refresh_cache: bool = False) -> None:
        self.refresh_cache = refresh_cache
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_real_request_at: float | None = None
        self.pages_fetched = 0
        self.cache_hits = 0

    def cache_path(self, url: str, cache_name: str | None) -> Path:
        if cache_name:
            return CACHE_DIR / cache_name
        # Detail pages don't have a fixed name, so use their URL as a stable cache key.
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"detail-{digest}.html"

    def _wait_before_request(self) -> None:
        # Space out live requests; cached pages never pass through this delay.
        if self.last_real_request_at is None:
            return
        elapsed = time.monotonic() - self.last_real_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)

    def get_html(self, url: str, cache_name: str | None = None) -> str:
        path = self.cache_path(url, cache_name)
        if path.exists() and not self.refresh_cache:
            # Reusing saved HTML makes reruns faster and avoids needless site traffic.
            html = path.read_text(encoding="utf-8")
            self.cache_hits += 1
            print(f"CACHE HIT {url} bytes={len(html.encode('utf-8'))}")
            return html

        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            self._wait_before_request()
            try:
                self.last_real_request_at = time.monotonic()
                response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.status_code == 200:
                    self.pages_fetched += 1
                    path.write_text(response.text, encoding="utf-8")
                    print(f"FETCH {url} bytes={len(response.content)}")
                    return response.text
                if response.status_code >= 500 and attempt == 0:
                    # A temporary server problem gets one retry; client errors do not.
                    time.sleep(1)
                    continue
                response.raise_for_status()
            except requests.Timeout:
                self.last_real_request_at = time.monotonic()
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise
        raise RuntimeError(f"Could not fetch {url}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def discover_books(scraper: PoliteScraper) -> tuple[int, list[dict[str, str]]]:
    page_url = BASE_URL
    discovered: dict[str, str] = {}
    catalogue_pages = 0

    for page_number in range(1, MAX_CATALOGUE_PAGES + 1):
        cache_name = f"catalogue-page-{page_number}.html"
        html = scraper.get_html(page_url, cache_name)
        soup = BeautifulSoup(html, "html.parser")
        catalogue_pages += 1

        for link in soup.select("article.product_pod h3 a"):
            # Catalogue links are relative, so resolve each against its current page.
            product_url = urljoin(page_url, link.get("href", ""))
            discovered.setdefault(product_url, page_url)

        next_link = soup.select_one("li.next a")
        if page_number == MAX_CATALOGUE_PAGES or next_link is None:
            break
        # Follow the site's own next link instead of guessing page URLs.
        page_url = urljoin(page_url, next_link.get("href", ""))

    return catalogue_pages, [
        {"product_url": url, "source_page": source_page}
        for url, source_page in discovered.items()
    ]


def extract_raw_record(scraper: PoliteScraper, item: dict[str, str]) -> dict[str, Any]:
    url = item["product_url"]
    soup = BeautifulSoup(scraper.get_html(url), "html.parser")
    product = soup.select_one("div.product_main")
    if product is None:
        raise ValueError("product page is missing div.product_main")

    title_node = product.select_one("h1")
    price_node = product.select_one("p.price_color")
    availability_node = product.select_one("p.instock.availability")
    rating_node = product.select_one("p.star-rating")
    if not all((title_node, price_node, availability_node, rating_node)):
        raise ValueError("product page is missing one or more required fields")

    description_heading = soup.select_one("#product_description")
    description_node = description_heading.find_next_sibling("p") if description_heading else None
    rating_classes = rating_node.get("class", [])
    rating_text = next((name for name in rating_classes if name != "star-rating"), "")

    return {
        "title": title_node.get_text(" ", strip=True),
        "product_url": url,
        "price_text": price_node.get_text(" ", strip=True),
        "availability_text": availability_node.get_text(" ", strip=True),
        "rating_text": rating_text,
        "description": description_node.get_text(" ", strip=True) if description_node else None,
        "source_page": item["source_page"],
        "fetched_at": utc_now(),
    }


def normalize_and_validate(raw: dict[str, Any]) -> dict[str, Any]:
    price_text = raw["price_text"]
    try:
        # Strip the currency symbol before converting the displayed price to a number.
        price = float(Decimal(re.sub(r"[^0-9.]", "", price_text)))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"could not parse price {price_text!r}") from exc
    record = {**raw, "price_gbp": price}
    return BookRecord.model_validate(record).model_dump(mode="json")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(refresh_cache: bool = False, inject_broken_url: bool = False) -> dict[str, Any]:
    started_at = utc_now()
    start_clock = time.monotonic()
    scraper = PoliteScraper(refresh_cache=refresh_cache)
    errors: list[dict[str, str]] = []
    records_by_url: dict[str, dict[str, Any]] = {}
    invalid_records = 0
    failed_pages = 0

    try:
        catalogue_pages, items = discover_books(scraper)
    except Exception as exc:
        errors.append({"url": BASE_URL, "reason": str(exc)})
        report = {
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - start_clock, 3),
            "catalogue_pages": 0,
            "discovered_urls": 0,
            "unique_urls": 0,
            "pages_fetched": scraper.pages_fetched,
            "cache_hits": scraper.cache_hits,
            "valid_records": 0,
            "invalid_records": 0,
            "failed_pages": 1,
        }
        write_json(OUTPUT_DIR / "books.json", [])
        write_json(OUTPUT_DIR / "errors.json", errors)
        write_json(OUTPUT_DIR / "run-report.json", report)
        print(f"Catalogue discovery failed: {exc}", file=sys.stderr)
        print(json.dumps(report, indent=2))
        return report

    print(
        f"catalogue_pages={catalogue_pages} discovered={len(items)} "
        f"unique_urls={len({item['product_url'] for item in items})}"
    )

    detail_items = list(items)
    if inject_broken_url:
        detail_items.append(
            {
                "product_url": urljoin(BASE_URL, "not-a-real-book/index.html"),
                "source_page": BASE_URL,
            }
        )

    for item in detail_items:
        url = item["product_url"]
        try:
            raw = extract_raw_record(scraper, item)
            record = normalize_and_validate(raw)
            records_by_url[url] = record
        except (requests.RequestException, RuntimeError) as exc:
            # One unavailable product should not stop the other books from being saved.
            failed_pages += 1
            errors.append({"url": url, "reason": str(exc)})
            print(f"SKIP {url}: {exc}", file=sys.stderr)
        except (ValueError, ValidationError) as exc:
            invalid_records += 1
            errors.append({"url": url, "reason": str(exc)})
            print(f"INVALID {url}: {exc}", file=sys.stderr)

    duration = time.monotonic() - start_clock
    records = list(records_by_url.values())
    report = {
        "started_at": started_at,
        "duration_seconds": round(duration, 3),
        "catalogue_pages": catalogue_pages,
        "discovered_urls": len(items),
        "unique_urls": len({item["product_url"] for item in items}),
        "pages_fetched": scraper.pages_fetched,
        "cache_hits": scraper.cache_hits,
        "valid_records": len(records),
        "invalid_records": invalid_records,
        "failed_pages": failed_pages,
    }
    write_json(OUTPUT_DIR / "books.json", records)
    write_json(OUTPUT_DIR / "errors.json", errors)
    write_json(OUTPUT_DIR / "run-report.json", report)
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape the first three Books to Scrape pages politely.")
    parser.add_argument(
        "--refresh-cache", action="store_true", help="fetch pages again instead of using cached HTML"
    )
    parser.add_argument(
        "--inject-broken-url",
        action="store_true",
        help="exercise per-page error handling with one deliberately missing sandbox URL",
    )
    args = parser.parse_args()
    run(refresh_cache=args.refresh_cache, inject_broken_url=args.inject_broken_url)


if __name__ == "__main__":
    main()
