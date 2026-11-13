"""Offline parser checks for the Books to Scrape pipeline."""

import unittest
from pathlib import Path
from unittest.mock import patch

from main import (
    PoliteScraper,
    discover_books,
    extract_raw_record,
    normalize_and_validate,
)


class ScraperTests(unittest.TestCase):
    def test_price_normalization(self):
        raw = {
            "title": "Example book",
            "product_url": "https://books.toscrape.com/catalogue/example_1/index.html",
            "price_text": "£51.77",
            "availability_text": "In stock",
            "rating_text": "Three",
            "description": None,
            "source_page": "https://books.toscrape.com/",
            "fetched_at": "2026-01-01T00:00:00Z",
        }
        self.assertEqual(normalize_and_validate(raw)["price_gbp"], 51.77)

    def test_relative_product_url_becomes_absolute(self):
        html = '<article class="product_pod"><h3><a href="catalogue/example_1/index.html">Book</a></h3></article>'
        with patch.object(PoliteScraper, "get_html", return_value=html):
            _, items = discover_books(PoliteScraper())
        self.assertEqual(
            items[0]["product_url"],
            "https://books.toscrape.com/catalogue/example_1/index.html",
        )

    def test_missing_description_is_allowed(self):
        html = '''<div class="product_main"><h1>Example</h1><p class="price_color">£10.00</p>
        <p class="instock availability">In stock</p><p class="star-rating Three"></p></div>'''
        item = {
            "product_url": "https://books.toscrape.com/catalogue/example_1/index.html",
            "source_page": "https://books.toscrape.com/",
        }
        with patch.object(PoliteScraper, "get_html", return_value=html):
            self.assertIsNone(extract_raw_record(PoliteScraper(), item)["description"])

    def test_duplicate_product_urls_are_removed(self):
        pages = [
            '<article class="product_pod"><h3><a href="catalogue/example_1/index.html">Book</a></h3></article><li class="next"><a href="page-2.html">next</a></li>',
            '<article class="product_pod"><h3><a href="catalogue/example_1/index.html">Book</a></h3></article><li class="next"><a href="page-3.html">next</a></li>',
            '<article class="product_pod"><h3><a href="catalogue/example_2/index.html">Other</a></h3></article>',
        ]
        with patch.object(PoliteScraper, "get_html", side_effect=pages):
            page_count, items = discover_books(PoliteScraper())
        self.assertEqual(page_count, 3)
        self.assertEqual(len(items), 2)

    def test_malformed_product_fixture_is_rejected(self):
        fixture = Path(__file__).parent / "fixtures" / "malformed_product.html"
        item = {
            "product_url": "https://books.toscrape.com/catalogue/broken/index.html",
            "source_page": "https://books.toscrape.com/",
        }
        with patch.object(PoliteScraper, "get_html", return_value=fixture.read_text(encoding="utf-8")):
            with self.assertRaisesRegex(ValueError, "product_main"):
                extract_raw_record(PoliteScraper(), item)


if __name__ == "__main__":
    unittest.main()
