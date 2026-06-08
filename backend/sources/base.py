"""
Abstract base class for product data sources.

All product sources (FakeStore, DummyJSON, etc.) implement this interface.
The rest of the system only talks to ProductSource — not to individual APIs.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from models.schemas import Product


class ProductSource(ABC):
    """Abstract product data source.

    Every source must implement:
    - name: unique identifier (e.g. "fakestore", "dummyjson")
    - search(): keyword-based product lookup
    - get_by_id(): single product by ID
    - get_all(): full product catalog
    - categories: available category names
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique source identifier, e.g. 'fakestore'"""
        ...

    @property
    def enabled(self) -> bool:
        """Can be overridden to dynamically disable a source via config."""
        return True

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Search products by keyword. Returns top_k matches, each with source set."""
        ...

    @abstractmethod
    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Fetch a single product by its ID in this source's ID space."""
        ...

    @abstractmethod
    async def get_all(self) -> List[Product]:
        """Fetch the entire product catalog from this source."""
        ...

    @property
    @abstractmethod
    def categories(self) -> List[str]:
        """List of all category names this source provides."""
        ...
