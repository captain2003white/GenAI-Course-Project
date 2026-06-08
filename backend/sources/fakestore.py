"""
FakeStore API product source.

API: https://fakestoreapi.com/products  (20 products, 4 categories, no auth)
Maps directly to the Product model — field names already match.
"""

from typing import List, Optional, Set

import httpx

from models.schemas import Product
from sources.base import ProductSource

API_BASE = "https://fakestoreapi.com"

# Stop words filtered from user search queries
_STOP_WORDS: Set[str] = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "cheap", "good", "nice", "best", "top", "great",
}


class FakeStoreSource(ProductSource):
    """Product source backed by the FakeStore API."""

    @property
    def name(self) -> str:
        return "fakestore"

    @property
    def categories(self) -> List[str]:
        return ["electronics", "jewelery", "men's clothing", "women's clothing"]

    async def get_all(self) -> List[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products")
            resp.raise_for_status()
            raw = resp.json()
        return [Product(**item, source=self.name) for item in raw]

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products/{product_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return Product(**resp.json(), source=self.name)

    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Keyword search over title + description with local matching."""
        all_products = await self.get_all()
        query_lower = query.lower().strip()

        # 1) Exact sub-string match in title or description
        matched: List[Product] = []
        for p in all_products:
            text = (p.title + " " + p.description).lower()
            if query_lower in text:
                matched.append(p)

        # 2) Fall back to individual keyword matching
        if not matched:
            keywords = [
                w.strip(".,!?;:'\"")
                for w in query_lower.split()
                if w.strip(".,!?;:'\"") not in _STOP_WORDS
            ]
            if keywords:
                scored = []
                for p in all_products:
                    text = (p.title + " " + p.description).lower()
                    hits = sum(1 for kw in keywords if kw in text)
                    if hits > 0:
                        scored.append((p, hits))
                scored.sort(key=lambda x: (x[1], x[0].rating.get("rate", 0)), reverse=True)
                matched = [s[0] for s in scored]

        # 3) Sort by rating and return top_k
        matched.sort(key=lambda p: p.rating.get("rate", 0), reverse=True)
        return matched[:top_k]


# Module-level convenience instance
source = FakeStoreSource()
