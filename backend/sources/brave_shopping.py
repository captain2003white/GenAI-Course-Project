"""
Brave Search API — real-time shopping results from across the web.

Provides live product search results from across thousands of merchants
via Brave's independent search index.

API:    https://api.search.brave.com/res/v1/shopping/search
Docs:   https://brave.com/search/api/
Free:   2 000 queries / month (no credit card needed)
Pro:    $5/mo for 20 000 queries
"""

import os
import zlib
from typing import List, Optional

from dotenv import load_dotenv
import httpx

from models.schemas import Product
from sources.base import ProductSource

load_dotenv()

API_BASE = "https://api.search.brave.com"
API_KEY_ENV = "BRAVE_API_KEY"


class BraveShoppingSource(ProductSource):
    """Real-time shopping search powered by Brave Search API.

    Returns live product listings from across the web with prices,
    images, ratings, and direct merchant links.

    Requires ``BRAVE_API_KEY`` in the environment.
    Get one free at https://brave.com/search/api/
    """

    @property
    def name(self) -> str:
        return "brave_shopping"

    @property
    def enabled(self) -> bool:
        return bool(os.getenv(API_KEY_ENV))

    @property
    def categories(self) -> List[str]:
        # Web search results are category-agnostic
        return []

    async def get_all(self) -> List[Product]:
        # Web search has no fixed catalog to enumerate
        return []

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        # Search results are ephemeral — no stable ID space
        return None

    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Search products across the web via Brave Shopping."""
        api_key = os.getenv(API_KEY_ENV)
        if not api_key:
            print("[BraveShopping] No BRAVE_API_KEY set — source disabled", flush=True)
            return []

        headers = {
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        }
        params = {"q": query, "count": min(top_k, 20)}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{API_BASE}/res/v1/shopping/search",
                    headers=headers,
                    params=params,
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                print(
                    f"[BraveShopping] HTTP {e.response.status_code}: {e.response.text[:200]}",
                    flush=True,
                )
                return []
            except Exception as e:
                print(f"[BraveShopping] Search failed: {e}", flush=True)
                return []

        raw_results = data.get("results", [])

        products = []
        for item in raw_results:
            # ── price ───────────────────────────────────────────────
            price_raw = item.get("price", {})
            price_val = 0.0
            if isinstance(price_raw, dict):
                price_val = float(price_raw.get("value", 0))
            elif isinstance(price_raw, (int, float)):
                price_val = float(price_raw)

            # ── rating ──────────────────────────────────────────────
            rating_val = item.get("rating", 0)
            review_count = item.get("review_count", 0)

            # ── url → stable-ish product id ─────────────────────────
            product_url = item.get("url", "")
            product_id = abs(zlib.crc32(product_url.encode())) if product_url else 0

            # ── image ───────────────────────────────────────────────
            image_url = item.get("image_url") or item.get("thumbnail") or ""

            products.append(Product(
                id=product_id if product_id else 0,
                title=item.get("title", "Unknown Product"),
                price=price_val,
                description=item.get("description", ""),
                category="other",
                image=image_url,
                url=product_url,
                rating={
                    "rate": float(rating_val) if rating_val else 0.0,
                    "count": int(review_count) if review_count else 0,
                },
                source=self.name,
            ))

        return products[:top_k]


# Module-level convenience instance
source = BraveShoppingSource()
