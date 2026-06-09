"""
eBay Browse API — real-time product search from eBay's global marketplace.

Provides live auction and fixed-price listings from eBay's inventory.
Uses OAuth 2.0 Client Credentials — no user context needed for search.

API:    https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
Auth:   OAuth 2.0 (client_credentials) — token cached for 2h
Free:   unlimited API calls (rate-limited, no credit card needed)
"""

import os
import time
import zlib
from typing import List, Optional

from dotenv import load_dotenv
import httpx

from models.schemas import Product
from sources.base import ProductSource

load_dotenv()

API_BASE = "https://api.ebay.com"
CLIENT_ID_ENV = "EBAY_CLIENT_ID"
CLIENT_SECRET_ENV = "EBAY_CLIENT_SECRET"


class EbaySource(ProductSource):
    """Real-time product search via eBay Browse API.

    Returns live listings from eBay US marketplace with prices,
    images, and direct purchase links.

    Requires ``EBAY_CLIENT_ID`` and ``EBAY_CLIENT_SECRET`` in the environment.
    Get them free at https://developer.ebay.com/
    (Create an app → get keys from the Application Keys section)
    """

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ── identity ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "ebay"

    @property
    def enabled(self) -> bool:
        return bool(os.getenv(CLIENT_ID_ENV)) and bool(os.getenv(CLIENT_SECRET_ENV))

    @property
    def categories(self) -> List[str]:
        return []  # eBay has thousands of dynamic categories

    async def get_all(self) -> List[Product]:
        # eBay's catalog is the entire marketplace — not enumerable
        return []

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        # eBay items are ephemeral listings, not stable IDs
        return None

    # ── OAuth token management ─────────────────────────────────────

    async def _ensure_token(self) -> Optional[str]:
        """Get a cached OAuth token or refresh one from eBay."""
        now = time.time()
        if self._token and now < self._token_expiry - 120:
            return self._token

        client_id = os.getenv(CLIENT_ID_ENV)
        client_secret = os.getenv(CLIENT_SECRET_ENV)
        if not client_id or not client_secret:
            return None

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{API_BASE}/identity/v1/oauth2/token",
                    auth=(client_id, client_secret),
                    data={
                        "grant_type": "client_credentials",
                        "scope": "https://api.ebay.com/oauth/api_scope/buy.browse",
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                body = resp.json()
                self._token = body["access_token"]
                self._token_expiry = now + body.get("expires_in", 7200)
                print(
                    f"[eBay] OAuth token acquired (expires in {body.get('expires_in', 7200)}s)",
                    flush=True,
                )
                return self._token
            except httpx.HTTPStatusError as e:
                print(
                    f"[eBay] OAuth error HTTP {e.response.status_code}: {e.response.text[:300]}",
                    flush=True,
                )
                return None
            except Exception as e:
                print(f"[eBay] OAuth token error: {e}", flush=True)
                return None

    # ── search ─────────────────────────────────────────────────────

    async def search(self, query: str, top_k: int = 5) -> List[Product]:
        """Search eBay US marketplace for products matching *query*."""
        token = await self._ensure_token()
        if not token:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }
        params = {
            "q": query,
            "limit": min(top_k, 20),
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{API_BASE}/buy/browse/v1/item_summary/search",
                    headers=headers,
                    params=params,
                    timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                print(
                    f"[eBay] Search HTTP {e.response.status_code}: {e.response.text[:300]}",
                    flush=True,
                )
                return []
            except Exception as e:
                print(f"[eBay] Search failed: {e}", flush=True)
                return []

        items = data.get("itemSummaries", [])
        products = []
        for item in items:
            # ── price ───────────────────────────────────────────────
            price_info = item.get("price", {})
            price_val = 0.0
            if isinstance(price_info, dict):
                price_val = float(price_info.get("value", 0))

            # ── image ───────────────────────────────────────────────
            image_obj = item.get("image", {})
            image_url = image_obj.get("imageUrl", "") if isinstance(image_obj, dict) else ""

            # ── url → stable-ish product id ─────────────────────────
            item_url = item.get("itemWebUrl", "")
            item_id_str = item.get("itemId", "")
            product_id = abs(zlib.crc32(item_id_str.encode())) if item_id_str else 0

            # ── description snippet ─────────────────────────────────
            short_desc = item.get("shortDescription", "")
            seller_info = item.get("seller", {})
            seller_name = seller_info.get("username", "") if isinstance(seller_info, dict) else ""
            condition = item.get("condition", "")

            desc_parts = []
            if short_desc:
                desc_parts.append(short_desc)
            if condition:
                desc_parts.append(f"Condition: {condition}")
            if seller_name:
                desc_parts.append(f"Seller: {seller_name}")
            description = " | ".join(desc_parts)

            products.append(Product(
                id=product_id if product_id else 0,
                title=item.get("title", "Unknown Product"),
                price=price_val,
                description=description,
                category="other",
                image=image_url,
                url=item_url,
                rating={"rate": 0.0, "count": 0},
                source=self.name,
            ))

        return products[:top_k]


# Module-level convenience instance
source = EbaySource()
