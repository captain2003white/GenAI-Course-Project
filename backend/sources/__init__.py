"""
Product data source abstraction layer.

Provides a unified interface for searching products across multiple backends
(FakeStore, DummyJSON, Platzi, Brave Shopping, eBay, etc.) while keeping the rest
of the system agnostic to where the data comes from.

Each source is registered below on import. Web-shopping sources (Brave, eBay)
are automatically DISABLED if their API keys are not set — they simply return
empty results without errors.
"""

from sources.base import ProductSource
from sources.registry import ProductRegistry, registry
from sources.fakestore import FakeStoreSource
from sources.dummyjson import DummyJSONSource
from sources.platzi import PlatziSource
from sources.brave_shopping import BraveShoppingSource
from sources.ebay import EbaySource

__all__ = [
    "ProductSource",
    "ProductRegistry",
    "registry",
    "FakeStoreSource",
    "DummyJSONSource",
    "PlatziSource",
    "BraveShoppingSource",
    "EbaySource",
]

# ── Built-in product catalog sources (no API keys needed, always enabled) ──
registry.register(FakeStoreSource())     # 20 products
registry.register(DummyJSONSource())     # 194 products
registry.register(PlatziSource())        # ~47 products, includes "Shoes" category

# ── Web shopping sources (require API keys, auto-disable if missing) ──
registry.register(BraveShoppingSource()) # requires BRAVE_API_KEY
registry.register(EbaySource())          # requires EBAY_CLIENT_ID + SECRET
