"""
Payment processing tool

Creates Stripe payment links using the Stripe SDK.
Uses Stripe test mode for demo — test card 4242 4242 4242 4242.
"""

import stripe
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Test card numbers for demo
TEST_CARDS = {
    "success": "4242424242424242",       # Payment succeeds
    "decline": "4000000000000002",       # Payment declined
    "insufficient_funds": "4000000000009995",  # Insufficient funds
}


async def create_payment_link(
    product_name: str,
    price_cents: int,
    quantity: int = 1,
    currency: str = "usd"
) -> Optional[str]:
    """
    Create a Stripe payment link

    Flow:
    1. Create a Product in Stripe
    2. Create a Price for that product
    3. Generate a Payment Link

    Returns the payment URL for the user to complete payment on Stripe's hosted page.
    """
    try:
        # Step 1: Create product in Stripe
        product = stripe.Product.create(
            name=product_name,
            description=f"Commerce Agents demo product: {product_name}",
        )

        # Step 2: Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_cents,
            currency=currency,
        )

        # Step 3: Generate payment link
        payment_link = stripe.PaymentLink.create(
            line_items=[{
                "price": price.id,
                "quantity": quantity,
            }],
        )

        return payment_link.url

    except stripe.error.StripeError as e:
        print(f"Stripe error: {e}")
        return None


def get_test_card_info() -> dict:
    """Return test card info for demo display"""
    return {
        "success_card": TEST_CARDS["success"],
        "decline_card": TEST_CARDS["decline"],
        "message": "Use 4242 4242 4242 4242 to test payment"
    }
