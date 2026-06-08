"""
Chat Agent — Core AI logic

Workflow:
1. Receive user message
2. Call DeepSeek LLM to understand intent
3. LLM outputs structured JSON instructions (search/show/pay)
4. Backend executes the action and returns results

LLM output format includes action field:
  {"action": "search", "query": "...", "category": "..."}
  {"action": "show", "product_ids": [...]}
  {"action": "compare", "product_ids": [...]}
  {"action": "buy", "product_id": 1, "quantity": 1}
  {"action": "chat", "message": "..."}
"""

import json
import os
import re
from openai import OpenAI
from typing import List, Optional
from dotenv import load_dotenv

from models.schemas import Product, ProductCategory
from tools.search import search_products, get_products_by_category, get_display_fields

load_dotenv()

# DeepSeek configuration (OpenAI-compatible API)
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """IMPORTANT: You must ALWAYS respond in English. Never use Chinese or any other language. This is critical.

You are Commerce Agents, an AI shopping assistant. You help users search, compare, and purchase products through chat.

## Your Capabilities

### 1. Demand Understanding
- If the user is vague ("I need a gift for a friend"), ask clarifying questions
- If the user is specific ("find Nike Air Force 1 size 42"), search directly
- Extract: product type, brand, price range, attributes

### 2. Search & Display
- Call the search tool based on user needs
- Different categories have different display focus:
  - Electronics: highlight specs, performance
  - Clothing/Jewelry: highlight appearance, color, material
  - Others: default title, price, description

### 3. IMPORTANT: Honesty Rules
- ONLY mention product attributes (color, size, brand) that you can actually see in the search results
- If the search returns products but you don't know their color, say "Here are some jackets I found" — NOT "here are blue jackets"
- Never make up attributes that aren't in the product data
- If the search can't filter by a specific attribute, acknowledge it honestly

### 4. Communication Style
- CRITICAL: Reply in English ONLY. Never use Chinese, never use any other language.
- Be concise and friendly
- Always include product information in your reply
- Explain why you're recommending a product
- Keep replies short — 1-2 sentences max

## Output Format
You must output ONLY a JSON object, no other text:

1. When user wants to search products:
{"action": "search", "query": "core keywords like jacket, shirt, backpack", "category": "optional category", "reply": "your message to user"}
   Note: query must be core product keywords only (jacket, shirt, electronics), NOT phrases like "find me a" or "looking for"

2. When showing search results:
{"action": "show", "product_ids": [1, 2, 3], "reply": "your recommendation"}

3. When user wants to compare:
{"action": "compare", "product_ids": [1, 2], "reply": "comparison explanation"}

4. When user wants to buy:
{"action": "buy", "product_id": 1, "quantity": 1, "reply": "confirmation message"}

5. For casual chat or when needing more info:
{"action": "chat", "reply": "your reply", "needs_info": ["info you need from user"]}
"""


class ChatAgent:
    def __init__(self):
        self.conversation_history = []

    @staticmethod
    def _parse_llm_output(text: str) -> Optional[dict]:
        """Robust JSON extraction from LLM output."""
        if not text:
            return None

        # Strategy 1: Try parsing the whole output as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code blocks
        blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', text)
        for block in blocks:
            block = block.strip()
            if block.startswith("{"):
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    continue

        # Strategy 3: Find any JSON object in the text
        m = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        return None

    async def process_message(self, user_message: str) -> dict:
        """
        Process a user message

        Returns:
        {
            "reply": str,              # Response text for user
            "products": List[Product],  # Related products
            "action": str,             # Action triggered
            "usage": dict,             # Token usage: prompt_tokens, completion_tokens, total_tokens
        }
        """
        # Build message history
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.conversation_history[-10:],  # Keep last 10 turns
            {"role": "user", "content": user_message},
        ]

        try:
            # Call DeepSeek API
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )

            llm_output = response.choices[0].message.content.strip()

            # Capture token usage from DeepSeek response
            usage_data = {}
            if hasattr(response, 'usage') and response.usage:
                usage_data = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) or 0,
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0) or 0,
                    "total_tokens": getattr(response.usage, 'total_tokens', 0) or 0,
                }
                print(f"[ChatAgent] Token usage: {usage_data}", flush=True)

            # Parse JSON output
            if "```json" in llm_output:
                llm_output = llm_output.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_output:
                llm_output = llm_output.split("```")[1].split("```")[0].strip()

            action_data = self._parse_llm_output(llm_output)
            if action_data is None:
                # LLM didn't output valid JSON — treat as plain chat
                print(f"[ChatAgent] LLM output was not valid JSON, treating as chat message", flush=True)
                action_data = {"action": "chat", "reply": llm_output}

            # Save conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": llm_output})

            # Execute the action
            result = await self._execute_action(action_data)
            result["usage"] = usage_data
            return result

        except Exception as e:
            return {
                "reply": f"Sorry, something went wrong: {str(e)}. Please try again.",
                "products": [],
                "action": "error",
            }

    async def _execute_action(self, action_data: dict) -> dict:
        """Execute the action determined by the LLM"""
        action = action_data.get("action", "chat")
        reply = action_data.get("reply", "")

        if action == "search":
            # Execute product search
            query = action_data.get("query", "")
            category = action_data.get("category")
            products = await search_products(query, category=category, top_k=5)

            if products:
                display_hints = get_display_fields(products[0].category)
                return {
                    "reply": reply or f"Here are some products I found:",
                    "products": products,
                    "action": "search",
                    "display_hints": display_hints,
                }
            else:
                return {
                    "reply": f"Sorry, I couldn't find any products matching '{query}'. Try a different keyword?",
                    "products": [],
                    "action": "search",
                }

        elif action == "show":
            # Display specific products
            from tools.search import get_product_by_id
            product_ids = action_data.get("product_ids", [])
            products = []
            for pid in product_ids:
                product = await get_product_by_id(pid)
                if product:
                    products.append(Product(**product))

            return {
                "reply": reply,
                "products": products,
                "action": "show",
            }

        elif action == "compare":
            # Compare products
            from tools.search import get_product_by_id
            product_ids = action_data.get("product_ids", [])
            products = []
            for pid in product_ids:
                product = await get_product_by_id(pid)
                if product:
                    products.append(Product(**product))

            return {
                "reply": reply or "Here's a comparison:",
                "products": products,
                "action": "compare",
            }

        elif action == "buy":
            # Trigger purchase flow
            return {
                "reply": reply or "OK, let me create a payment link for you.",
                "products": [],
                "action": "buy",
                "product_id": action_data.get("product_id"),
                "quantity": action_data.get("quantity", 1),
            }

        else:
            # Casual chat or follow-up questions
            needs_info = action_data.get("needs_info", [])
            return {
                "reply": reply,
                "products": [],
                "action": "chat",
                "needs_info": needs_info,
            }
