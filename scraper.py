"""
Product Scraper -> Shopify CSV
Author: Sajawal Dastagir

Work sample: scrapes product data from books.toscrape.com (a public sandbox
site built for scraping practice) and converts it into a Shopify-ready
bulk-import CSV.

Usage:
    pip install requests beautifulsoup4
    python scraper.py --pages 3
"""

import argparse
import csv
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio-sample-scraper)"}
RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

SHOPIFY_COLUMNS = [
    "Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type",
    "Tags", "Published", "Variant SKU", "Variant Price",
    "Variant Inventory Qty", "Image Src", "SEO Title", "SEO Description",
    "Status",
]


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def scrape_product(url):
    soup = get_soup(url)
    title = soup.select_one("div.product_main h1").get_text(strip=True)
    price = soup.select_one("p.price_color").get_text(strip=True)
    price = float(re.sub(r"[^\d.]", "", price))
    stock_text = soup.select_one("p.instock.availability").get_text(strip=True)
    stock = int(re.search(r"\d+", stock_text).group()) if re.search(r"\d+", stock_text) else 0
    rating = RATING_MAP.get(soup.select_one("p.star-rating")["class"][1], 0)
    category = soup.select("ul.breadcrumb li a")[-1].get_text(strip=True)
    desc_tag = soup.select_one("#product_description + p")
    description = desc_tag.get_text(strip=True) if desc_tag else ""
    image = urljoin(url, soup.select_one("div.item.active img")["src"])
    upc = soup.select_one("table.table-striped td").get_text(strip=True)

    return {
        "title": title, "price": price, "stock": stock, "rating": rating,
        "category": category, "description": description, "image": image,
        "sku": upc, "url": url,
    }


def to_shopify_row(p):
    short_desc = p["description"][:300].rsplit(" ", 1)[0] + "..." if len(p["description"]) > 300 else p["description"]
    return {
        "Handle": slugify(p["title"]),
        "Title": p["title"],
        "Body (HTML)": f"<p>{short_desc}</p>",
        "Vendor": "Books To Scrape",
        "Product Category": "Media > Books",
        "Type": p["category"],
        "Tags": f"{p['category']}, {p['rating']}-star, books",
        "Published": "TRUE",
        "Variant SKU": p["sku"],
        "Variant Price": f"{p['price']:.2f}",
        "Variant Inventory Qty": p["stock"],
        "Image Src": p["image"],
        "SEO Title": f"{p['title'][:55]} | Buy Online",
        "SEO Description": short_desc[:155],
        "Status": "active" if p["stock"] > 0 else "draft",
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape products into a Shopify CSV")
    parser.add_argument("--pages", type=int, default=2, help="catalogue pages to scrape (20 products each)")
    parser.add_argument("--out", default="shopify_import.csv")
    args = parser.parse_args()

    products = []
    page_url = urljoin(BASE_URL, "catalogue/page-1.html")
    for page in range(1, args.pages + 1):
        print(f"[page {page}] {page_url}")
        soup = get_soup(page_url)
        for link in soup.select("article.product_pod h3 a"):
            product_url = urljoin(page_url, link["href"])
            try:
                products.append(scrape_product(product_url))
            except Exception as exc:  # keep going if one product fails
                print(f"  ! skipped {product_url}: {exc}")
            time.sleep(0.3)  # be polite to the server
        next_link = soup.select_one("li.next a")
        if not next_link:
            break
        page_url = urljoin(page_url, next_link["href"])

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHOPIFY_COLUMNS)
        writer.writeheader()
        for p in products:
            writer.writerow(to_shopify_row(p))

    print(f"Done: {len(products)} products -> {args.out}")


if __name__ == "__main__":
    main()
