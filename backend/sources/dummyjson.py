"""
DummyJSON API product source.

API: https://dummyjson.com/products?limit=200  (194 products, 24 categories, no auth)

Field mapping (DummyJSON → Product model):
  title       → title
  price       → price
  description → description
  category    → category  (mapped to ProductCategory values)
  thumbnail   → image
  rating      → {"rate": rating_float, "count": 0}
"""

from typing import Dict, List, Optional, Set

import httpx

from models.schemas import Product
from sources.base import ProductSource

API_BASE = "https://dummyjson.com"

# DummyJSON category → ProductCategory mapping
_CATEGORY_MAP: Dict[str, str] = {
    # Electronics
    "smartphones": "electronics",
    "laptops": "electronics",
    "tablets": "electronics",
    "mobile-accessories": "electronics",
    # Clothing
    "mens-shirts": "clothing",
    "mens-shoes": "clothing",
    "mens-watches": "clothing",
    "tops": "clothing",
    "womens-dresses": "clothing",
    "womens-shoes": "clothing",
    "womens-watches": "clothing",
    "womens-bags": "clothing",
    # Jewelry
    "womens-jewellery": "jewelery",
    # Everything else → other
}

# Stop words filtered from user search queries
_STOP_WORDS: Set[str] = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "cheap", "good", "nice", "best", "top", "great",
}


def _map_product(raw: dict) -> Product:
    """Convert a DummyJSON product dict to a unified Product."""
    dj_cat = raw.get("category", "")
    mapped_cat = _CATEGORY_MAP.get(dj_cat, "other")

    # rating is a float in DummyJSON
    rating_val = raw.get("rating", 0)
    if isinstance(rating_val, (int, float)):
        rating_dict = {"rate": float(rating_val), "count": 0}
    else:
        rating_dict = raw.get("rating", {"rate": 0.0, "count": 0})

    return Product(
        id=raw["id"],
        title=raw["title"],
        price=float(raw["price"]),
        description=raw.get("description", ""),
        category=mapped_cat,
        image=raw.get("thumbnail", ""),
        rating=rating_dict,
        source="dummyjson",
    )


class DummyJSONSource(ProductSource):
    """Product source backed by the DummyJSON API (194 products)."""

    @property
    def name(self) -> str:
        return "dummyjson"

    @property
    def categories(self) -> List[str]:
        return sorted(set(_CATEGORY_MAP.values()))

    async def get_all(self) -> List[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products", params={"limit": 200})
            resp.raise_for_status()
            body = resp.json()
        return [_map_product(item) for item in body.get("products", [])]

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products/{product_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _map_product(resp.json())

    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Search via DummyJSON's built-in search endpoint, then map results."""
        query_lower = query.lower().strip()

        # Delegate to DummyJSON's own search API — faster than fetching all 194
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_BASE}/products/search",
                params={"q": query_lower, "limit": top_k},
            )
            resp.raise_for_status()
            body = resp.json()
            raw_results = body.get("products", [])

        if raw_results:
            return [_map_product(item) for item in raw_results]

        # Fallback: fetch all and do local keyword matching
        all_products = await self.get_all()
        keywords = [
            w.strip(".,!?;:'\"")
            for w in query_lower.split()
            if w.strip(".,!?;:'\"") not in _STOP_WORDS
        ]
        if not keywords:
            return []

        scored = []
        for p in all_products:
            text = (p.title + " " + p.description).lower()
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                scored.append((p, hits))
        scored.sort(key=lambda x: (x[1], x[0].rating.get("rate", 0)), reverse=True)
        return [s[0] for s in scored[:top_k]]


# Module-level convenience instance
source = DummyJSONSource()
