"""
Product search tool — multi-source unified interface.

This module is the single entry point for ALL product lookups in the system.
It delegates to the ProductRegistry which queries every registered source
(FakeStore, DummyJSON, …) in parallel and merges results.

All exported function signatures are kept stable so that callers
(chat_agent.py, main.py, etc.) do not need to change.
"""

from typing import List, Optional, Set

from models.schemas import Product, ProductCategory
from sources import registry

# Stop words kept here for consumers that reference them directly
_STOP_WORDS: Set[str] = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "cheap", "good", "nice", "best", "top", "great",
}


async def search_products(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5,
) -> List[Product]:
    """Search all data sources and return merged, sorted results.

    Supports optional category filter (applied post-merge).
    The category match is flexible — "clothing" matches "men's clothing",
    "women's clothing" and "clothing".
    """
    # Let the registry handle multi-source search
    results = await registry.search_merged(query, top_k=top_k * 2 if category else top_k)

    if category:
        cat_lower = category.lower().strip()
        # Flexible category matching: exact OR partial
        filtered = [
            p for p in results
            if p.category == cat_lower
            or cat_lower in p.category
            or p.category in cat_lower
        ]
        # Only apply filter if it preserves some results
        if filtered:
            results = filtered
        # If the filter zeroed everything, ignore it (LLM may have guessed wrong)

    return results[:top_k]


async def get_product_by_id(product_id: int) -> Optional[dict]:
    """Get a single product by ID (dict form, for backward compat).

    Tries each registered source until a match is found.
    Returns a dict matching the Product model fields so that callers
    like main.py:/buy can do Product(**product).
    """
    product = await registry.get_by_id(product_id)
    if product is None:
        return None
    # Backward compat: return as dict so existing Product(**dict) calls work
    return product.model_dump()


async def get_products_by_category(category: str, top_k: int = 10) -> List[Product]:
    """Get products by category across all sources."""
    return await registry.get_products_by_category(category, top_k=top_k)


def get_display_fields(category: str) -> dict:
    """Return display field priorities based on product category.

    Unchanged — still works with the same ProductCategory enum.
    """
    if category == ProductCategory.ELECTRONICS.value:
        return {
            "primary": "image",
            "secondary": ["title", "price", "description"],
            "highlight": "specs",
        }
    elif category in (ProductCategory.CLOTHING.value, ProductCategory.JEWELRY.value):
        return {
            "primary": "image",
            "secondary": ["title", "price", "color", "material"],
            "highlight": "appearance",
        }
    else:
        return {
            "primary": "title",
            "secondary": ["price", "description"],
            "highlight": "overview",
        }
