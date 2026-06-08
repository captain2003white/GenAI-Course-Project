"""
ProductSource registry — manages multiple sources and aggregates results.

Typical usage:
    registry = ProductRegistry()
    registry.register(FakeStoreSource())
    registry.register(DummyJSONSource())

    products = await registry.search_merged("jacket", top_k=8)
"""

from typing import Dict, List, Optional

from models.schemas import Product
from sources.base import ProductSource


class ProductRegistry:
    """Registry of ProductSource instances with parallel-search aggregation."""

    def __init__(self):
        self._sources: Dict[str, ProductSource] = {}

    # ── registration ──────────────────────────────────────────────

    def register(self, source: ProductSource) -> None:
        """Register a product source by its .name."""
        self._sources[source.name] = source

    @property
    def source_names(self) -> List[str]:
        """Names of all registered (and enabled) sources."""
        return [n for n, s in self._sources.items() if s.enabled]

    def get_source(self, name: str) -> Optional[ProductSource]:
        """Look up a source by name."""
        return self._sources.get(name)

    # ── search ────────────────────────────────────────────────────

    async def search_all(self, query: str, top_k: int = 5) -> Dict[str, List[Product]]:
        """Search EVERY enabled source in parallel.

        Returns a dict keyed by source name so callers can see per-source results.
        """
        import asyncio

        tasks = {
            name: source.search(query, top_k=top_k)
            for name, source in self._sources.items()
            if source.enabled
        }

        results: Dict[str, List[Product]] = {}
        if not tasks:
            return results

        # Run all searches concurrently
        outcomes = await asyncio.gather(
            *tasks.values(),
            return_exceptions=True,
        )

        for (name, _), outcome in zip(tasks.items(), outcomes):
            if isinstance(outcome, Exception):
                print(f"[Registry] Source '{name}' search failed: {outcome}", flush=True)
                results[name] = []
            else:
                results[name] = outcome

        return results

    async def search_merged(self, query: str, top_k: int = 5) -> List[Product]:
        """Search all sources, merge, sort by rating, deduplicate by title.

        Merge strategy (by priority):
          1. Collect results from every enabled source
          2. Deduplicate: if two products have very similar titles, keep the one
             with the higher rating
          3. Sort by rating descending
          4. Return at most top_k
        """
        per_source = await self.search_all(query, top_k=max(top_k * 2, 10))

        # Flatten
        all_products: List[Product] = []
        for source_name, products in per_source.items():
            for p in products:
                all_products.append(p)

        if not all_products:
            return []

        # Deduplicate across sources by title similarity
        # (simple strategy: same lower-cased title → keep higher rated)
        seen_titles: Dict[str, Product] = {}
        for p in all_products:
            key = p.title.strip().lower()
            if key not in seen_titles:
                seen_titles[key] = p
            else:
                existing_rating = seen_titles[key].rating.get("rate", 0)
                new_rating = p.rating.get("rate", 0)
                if new_rating > existing_rating:
                    seen_titles[key] = p

        # Sort by rating desc, then by source name for stability
        deduped = sorted(
            seen_titles.values(),
            key=lambda p: (p.rating.get("rate", 0), p.source),
            reverse=True,
        )

        return deduped[:top_k]

    # ── single-product lookup ─────────────────────────────────────

    async def get_by_id(
        self,
        product_id: int,
        source_name: Optional[str] = None,
    ) -> Optional[Product]:
        """Look up a product by ID.

        If source_name is given, only query that source.
        Otherwise try every enabled source and return the first hit.
        """
        if source_name:
            src = self._sources.get(source_name)
            if src and src.enabled:
                return await src.get_by_id(product_id)
            return None

        for src in self._sources.values():
            if not src.enabled:
                continue
            try:
                product = await src.get_by_id(product_id)
                if product is not None:
                    return product
            except Exception:
                continue
        return None

    # ── categories ────────────────────────────────────────────────

    @property
    def all_categories(self) -> List[str]:
        """Union of categories across all enabled sources."""
        cats: set[str] = set()
        for src in self._sources.values():
            if src.enabled:
                cats.update(src.categories)
        return sorted(cats)

    async def get_products_by_category(
        self, category: str, top_k: int = 10
    ) -> List[Product]:
        """Get products matching a given category from all sources."""
        # Fetch all, filter by category
        all_products: List[Product] = []
        for src in self._sources.values():
            if not src.enabled:
                continue
            try:
                catalog = await src.get_all()
                all_products.extend(
                    [p for p in catalog if p.category == category]
                )
            except Exception as e:
                print(
                    f"[Registry] Source '{src.name}' get_all failed: {e}",
                    flush=True,
                )

        all_products.sort(
            key=lambda p: p.rating.get("rate", 0), reverse=True
        )
        return all_products[:top_k]


# Singleton convenience instance — populated at app startup
registry = ProductRegistry()
