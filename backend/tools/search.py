"""
Product search tool

Fetches product data from the FakeStore API. Supports keyword search and category filtering.
Free RESTful API - no authentication required.
"""

import httpx
from typing import List, Optional
from models.schemas import Product, ProductCategory

FAKESTORE_API_BASE = "https://fakestoreapi.com"


async def get_all_products() -> List[dict]:
    """Fetch all products from FakeStore API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FAKESTORE_API_BASE}/products")
        response.raise_for_status()
        return response.json()


async def get_product_by_id(product_id: int) -> Optional[dict]:
    """Get a single product by ID"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FAKESTORE_API_BASE}/products/{product_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


# Stop words filtered out from search queries
_STOP_WORDS = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "cheap", "good", "nice", "best", "top", "great",
}


async def search_products(query: str, category: Optional[str] = None, top_k: int = 5) -> List[Product]:
    """
    Search products by keyword

    Strategy:
    - If category specified, filter by category first
    - Extract keywords from query (removing stop words) and match individually
    - Sort by match count + rating, return Top-K
    - If no keywords remain, fall back to category-only search
    """
    all_products = await get_all_products()

    # Filter by category if specified
    if category:
        filtered = [p for p in all_products if p["category"] == category]
    else:
        filtered = all_products

    # Extract keywords
    query_lower = query.lower().strip()
    # First try exact phrase match
    matched = []
    for p in filtered:
        text = (p["title"] + " " + p["description"]).lower()
        if query_lower in text:
            matched.append(p)

    # If exact match fails, split into individual keywords
    if not matched:
        keywords = [w.strip(".,!?;:'\"") for w in query_lower.split()
                    if w.strip(".,!?;:'\"") not in _STOP_WORDS]

        if keywords:
            word_scores = {}
            for p in filtered:
                text = (p["title"] + " " + p["description"]).lower()
                hit_count = sum(1 for kw in keywords if kw in text)
                if hit_count > 0:
                    word_scores[p["id"]] = hit_count

            # Sort by match count desc, then by rating desc
            scored = [(p, word_scores.get(p["id"], 0)) for p in filtered if p["id"] in word_scores]
            scored.sort(key=lambda x: (x[1], x[0]["rating"]["rate"]), reverse=True)
            matched = [s[0] for s in scored]

    # If no matches, retry without color/attribute modifiers
    if not matched and keywords:
        # Color and attribute words that might over-filter
        _FILTER_WORDS = {
            "blue", "red", "black", "white", "green", "yellow", "purple",
            "pink", "orange", "gray", "grey", "brown", "gold", "silver",
            "cheap", "expensive", "affordable", "budget", "premium",
            "casual", "formal", "sport", "fashion", "trendy",
            "light", "dark", "bright",
        }
        fallback_kw = [w for w in keywords if w not in _FILTER_WORDS]
        if fallback_kw and fallback_kw != keywords:
            for p in filtered:
                text = (p["title"] + " " + p["description"]).lower()
                if all(kw in text for kw in fallback_kw):
                    matched.append(p)

    # Sort by rating and return Top-K
    matched.sort(key=lambda x: x["rating"]["rate"], reverse=True)
    return [Product(**p) for p in matched[:top_k]]


async def get_products_by_category(category: str, top_k: int = 10) -> List[Product]:
    """Get products by category"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FAKESTORE_API_BASE}/products/category/{category}")
        response.raise_for_status()
        products = response.json()
        return [Product(**p) for p in products[:top_k]]


def get_display_fields(category: str) -> dict:
    """
    Return display field priorities based on product category

    Core logic for our "different categories, different display" design.
    Apparel emphasizes appearance, electronics emphasizes specs.
    """
    if category == ProductCategory.ELECTRONICS.value:
        return {
            "primary": "image",
            "secondary": ["title", "price", "description"],
            "highlight": "specs"
        }
    elif category in [ProductCategory.CLOTHING.value, ProductCategory.JEWELRY.value]:
        return {
            "primary": "image",
            "secondary": ["title", "price", "color", "material"],
            "highlight": "appearance"
        }
    else:
        return {
            "primary": "title",
            "secondary": ["price", "description"],
            "highlight": "overview"
        }
