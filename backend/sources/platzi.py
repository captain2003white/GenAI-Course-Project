"""
Platzi Fake Store API — free product catalog, no registration required.

API: https://api.escuelajs.co/api/v1/products  (~47 products, 6 categories)
Auth: None needed
Docs: https://docs.escuelajs.co/

Field mapping (Platzi → Product model):
  title       → title
  price       → price
  description → description
  category    → category (mapped to ProductCategory values)
  images[0]   → image
  rating      → N/A (set to 0)
"""

from typing import Dict, List, Optional, Set

import httpx

from models.schemas import Product
from sources.base import ProductSource

API_BASE = "https://api.escuelajs.co/api/v1"

# Platzi category → unified category mapping
_CATEGORY_MAP: Dict[str, str] = {
    "clothes": "clothing",
    "electronics": "electronics",
    "shoes": "clothing",
    "furniture": "other",
    "miscellaneous": "other",
}

# Stop words for local keyword search
_STOP_WORDS: Set[str] = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "cheap", "good", "nice", "best", "top", "great",
}


def _map_product(raw: dict) -> Product:
    """Convert a Platzi product dict to a unified Product."""
    cat_obj = raw.get("category", {})
    platzi_cat = (cat_obj.get("name", "") if isinstance(cat_obj, dict) else "").lower().strip()
    mapped_cat = _CATEGORY_MAP.get(platzi_cat, "other")

    # images is an array — use first
    images = raw.get("images", [])
    image_url = images[0] if isinstance(images, list) and images else ""

    return Product(
        id=raw["id"],
        title=raw.get("title", ""),
        price=float(raw.get("price", 0)),
        description=raw.get("description", ""),
        category=mapped_cat,
        image=image_url,
        rating={"rate": 0.0, "count": 0},
        source="platzi",
    )


class PlatziSource(ProductSource):
    """Product source backed by the Platzi Fake Store API (~47 products)."""

    @property
    def name(self) -> str:
        return "platzi"

    @property
    def categories(self) -> List[str]:
        return sorted(set(_CATEGORY_MAP.values()))

    async def get_all(self) -> List[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products", timeout=10.0)
            resp.raise_for_status()
            raw = resp.json()
        return [_map_product(item) for item in raw]

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/products/{product_id}", timeout=10.0)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _map_product(resp.json())

    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Keyword search over title + description with local matching."""
        query_lower = query.lower().strip()

        # Platzi has no search endpoint — fetch all and match locally
        all_products = await self.get_all()

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
                scored.sort(key=lambda x: (x[1], x[0].price), reverse=True)
                matched = [s[0] for s in scored]

        return matched[:top_k]


# Module-level convenience instance
source = PlatziSource()
