"""
sentiment/scraper.py
────────────────────
Scrapes venue reviews from 2GIS for NU campus locations.
Uses Selenium to handle the JS-rendered page, then extracts
review text + star ratings for sentiment label generation.

Usage:
    python -m sentiment.scraper --query "Nazarbayev University café" --max 500
"""

import time
import json
import argparse
import random
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from loguru import logger
from fake_useragent import UserAgent

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed – scraper will run in mock mode")

# ─── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Review:
    text: str
    rating: int          # 1–5 stars
    venue_name: str
    venue_category: str  # cafe / library / classroom / facility
    date: str
    source: str = "2gis"

    @property
    def sentiment_label(self) -> str:
        """Convert star rating → coarse sentiment label."""
        if self.rating >= 4:
            return "positive"
        if self.rating == 3:
            return "neutral"
        return "negative"


# ─── Scraper ───────────────────────────────────────────────────────────────────

class TwoGISScraper:
    BASE_URL = "https://2gis.kz/astana/search/{query}"

    # CSS selectors (update if 2GIS changes its markup)
    SEL_REVIEW_CARD   = "[class*='_1k2wr96']"
    SEL_REVIEW_TEXT   = "[class*='_49x36f']"
    SEL_REVIEW_RATING = "[class*='_y10azs']"   # star icons container
    SEL_REVIEW_DATE   = "[class*='_1w9o2igt']"
    SEL_LOAD_MORE     = "button[class*='_1v4xnqi']"
    SEL_VENUE_NAME    = "[class*='_oqoid']"

    def __init__(self, headless: bool = True, delay: float = 1.5):
        self.headless = headless
        self.delay = delay
        self.driver: Optional[object] = None

    # ── driver lifecycle ──────────────────────────────────────────────────────

    def _build_driver(self):
        if not SELENIUM_AVAILABLE:
            return None
        ua = UserAgent()
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_argument(f"user-agent={ua.random}")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    def start(self):
        self.driver = self._build_driver()
        return self

    def stop(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()

    # ── page helpers ──────────────────────────────────────────────────────────

    def _wait(self, selector: str, timeout: int = 10):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def _human_delay(self):
        time.sleep(self.delay + random.uniform(0, 0.8))

    def _count_filled_stars(self, card) -> int:
        """Count aria-label or filled star elements to extract numeric rating."""
        try:
            # Try aria-label first ("4 из 5")
            for el in card.find_elements(By.CSS_SELECTOR, "[aria-label]"):
                label = el.get_attribute("aria-label")
                if "из 5" in label:
                    return int(label.split()[0])
            # Fallback: count filled star icons
            filled = card.find_elements(By.CSS_SELECTOR, "[class*='_star'][class*='_filled']")
            if filled:
                return len(filled)
        except Exception:
            pass
        return 0  # unknown

    def _parse_cards(self, venue_name: str, venue_category: str) -> list[Review]:
        reviews: list[Review] = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, self.SEL_REVIEW_CARD)
        for card in cards:
            try:
                text_el = card.find_element(By.CSS_SELECTOR, self.SEL_REVIEW_TEXT)
                text = text_el.text.strip()
                if len(text) < 10:
                    continue
                rating = self._count_filled_stars(card)
                if rating == 0:
                    continue
                try:
                    date = card.find_element(By.CSS_SELECTOR, self.SEL_REVIEW_DATE).text.strip()
                except NoSuchElementException:
                    date = ""
                reviews.append(Review(
                    text=text,
                    rating=rating,
                    venue_name=venue_name,
                    venue_category=venue_category,
                    date=date,
                ))
            except NoSuchElementException:
                continue
        return reviews

    # ── main scrape ───────────────────────────────────────────────────────────

    def scrape_venue(
        self,
        query: str,
        venue_category: str = "general",
        max_reviews: int = 300,
    ) -> list[Review]:
        """Scrape reviews for a single 2GIS search query."""
        if not SELENIUM_AVAILABLE or not self.driver:
            logger.warning("Running in mock mode – returning synthetic reviews")
            return _mock_reviews(query, venue_category, n=50)

        url = self.BASE_URL.format(query=query.replace(" ", "%20"))
        logger.info(f"Loading: {url}")
        self.driver.get(url)
        self._human_delay()

        # Try to click the first result and navigate to reviews tab
        try:
            first_result = self._wait("[class*='_1h3cgic']", timeout=8)
            first_result.click()
            self._human_delay()
            venue_name_el = self._wait(self.SEL_VENUE_NAME, timeout=6)
            venue_name = venue_name_el.text.strip()
        except TimeoutException:
            logger.warning("Could not find venue listing")
            return []

        # Click the reviews tab
        try:
            reviews_tab = self.driver.find_element(
                By.XPATH, "//a[contains(., 'Отзыв') or contains(., 'Review')]"
            )
            reviews_tab.click()
            self._human_delay()
        except NoSuchElementException:
            logger.warning("Reviews tab not found")
            return []

        all_reviews: list[Review] = []
        last_count = 0
        stale_rounds = 0

        while len(all_reviews) < max_reviews:
            batch = self._parse_cards(venue_name, venue_category)
            all_reviews = _deduplicate(batch)

            # Try clicking "load more"
            try:
                load_more = self.driver.find_element(By.CSS_SELECTOR, self.SEL_LOAD_MORE)
                self.driver.execute_script("arguments[0].click();", load_more)
                self._human_delay()
            except NoSuchElementException:
                logger.info("No 'load more' button – reached end")
                break

            if len(all_reviews) == last_count:
                stale_rounds += 1
                if stale_rounds >= 3:
                    break
            else:
                stale_rounds = 0
                last_count = len(all_reviews)

        logger.info(f"Scraped {len(all_reviews)} reviews for '{venue_name}'")
        return all_reviews[:max_reviews]

    def scrape_all_targets(self, targets: list[dict], max_per_venue: int = 300) -> list[Review]:
        """Scrape multiple venues and return combined corpus."""
        all_reviews: list[Review] = []
        for target in targets:
            reviews = self.scrape_venue(
                query=target["query"],
                venue_category=target.get("category", "general"),
                max_reviews=max_per_venue,
            )
            all_reviews.extend(reviews)
            time.sleep(random.uniform(2, 4))   # polite inter-venue delay
        return all_reviews


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _deduplicate(reviews: list[Review]) -> list[Review]:
    seen: set[str] = set()
    out: list[Review] = []
    for r in reviews:
        key = r.text[:80]
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _mock_reviews(query: str, category: str, n: int = 50) -> list[Review]:
    """Return synthetic reviews for testing without a browser."""
    templates = [
        ("Очень удобное место, всегда чисто и тихо.", 5),
        ("Нормально, но иногда шумно во время перерывов.", 3),
        ("Кофе вкусный, персонал приветливый.", 4),
        ("Слишком мало розеток для ноутбуков.", 2),
        ("Отличный вид, приятная атмосфера для учёбы.", 5),
        ("Очереди в обед огромные, нужно больше кассиров.", 2),
        ("Хорошая еда по разумным ценам.", 4),
        ("Столики часто заняты, сложно найти место.", 3),
        ("Отличный Wi-Fi и кондиционер работает хорошо.", 5),
        ("Еда остывает быстро, хотелось бы теплее.", 2),
    ]
    reviews = []
    for i in range(n):
        text, rating = templates[i % len(templates)]
        reviews.append(Review(
            text=text,
            rating=rating,
            venue_name=query,
            venue_category=category,
            date="2024-01-01",
        ))
    return reviews


def save_reviews(reviews: list[Review], path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in reviews], f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(reviews)} reviews → {path}")


def load_reviews(path: str) -> list[Review]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Review(**d) for d in data]


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query",    default="Nazarbayev University café")
    parser.add_argument("--category", default="cafe")
    parser.add_argument("--max",      type=int, default=300)
    parser.add_argument("--out",      default="data/raw_reviews.json")
    parser.add_argument("--mock",     action="store_true", help="Use mock data (no browser)")
    args = parser.parse_args()

    if args.mock:
        reviews = _mock_reviews(args.query, args.category, n=args.max)
    else:
        with TwoGISScraper(headless=True) as scraper:
            reviews = scraper.scrape_venue(args.query, args.category, args.max)

    save_reviews(reviews, args.out)
