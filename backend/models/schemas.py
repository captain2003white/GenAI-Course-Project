"""
Data models (Pydantic Schemas)

Defines the shape of all data used in the system.
Pydantic validates data at runtime, catching errors early.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ProductCategory(str, Enum):
    """Product category enum — determines display focus"""
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    JEWELRY = "jewelery"  # FakeStore API uses this spelling
    OTHER = "other"


class Product(BaseModel):
    """Product model — matches FakeStore API response structure"""
    id: int
    title: str
    price: float
    description: str
    category: str
    image: str
    rating: dict = Field(default_factory=lambda: {"rate": 0.0, "count": 0})


class ChatRequest(BaseModel):
    """User chat message request"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """AI response"""
    reply: str
    products: List[Product] = []
    session_id: str


class PaymentRequest(BaseModel):
    """Purchase request"""
    product_id: int
    quantity: int = 1
    session_id: str


class PaymentResponse(BaseModel):
    """Payment link response"""
    payment_url: str
    product_name: str
    total_amount: float
