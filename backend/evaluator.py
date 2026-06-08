"""
Evaluation module — six metrics in two groups.

New Metrics (v2.0):
1. Search Precision (0.0-1.0) — keyword overlap, pure algorithmic
2. Source Coverage    (0.0-1.0) — unique sources / total registered
3. Response Accuracy  (0.0-1.0) — claim extraction + verification

Legacy Metrics (preserved for comparison, re-implemented with real logic):
4. Faithfulness      (0.0-1.0) — does the AI fabricate details not in product data?
5. Answer Relevancy  (0.0-1.0) — does the response directly address the user's question?
6. Context Recall    (0.0-1.0) — what fraction of available product info was reflected?
"""

import os
import json
import re
from typing import List, Optional, Set
from dotenv import load_dotenv
from openai import AsyncOpenAI

from models.schemas import Product

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── Stop words for keyword extraction ──
_STOP_WORDS: Set[str] = {
    "find", "me", "a", "an", "the", "for", "some", "i", "want",
    "looking", "need", "help", "get", "show", "tell", "about",
    "with", "and", "or", "in", "on", "at", "to", "is", "are",
    "please", "can", "could", "would", "do", "does", "has", "have",
    "this", "that", "these", "those", "it", "its", "my", "your",
    "cheap", "good", "nice", "best", "top", "great", "awesome",
    "any", "all", "very", "just", "also", "than", "then", "but",
}

# ── Total active data sources (for Source Coverage) ──
TOTAL_ACTIVE_SOURCES = 3  # FakeStore + DummyJSON + Platzi


async def evaluate_response(
    question: str,
    answer: str,
    products: List[Product],
    action: str = "",
) -> dict:
    """
    Evaluate a single chat interaction with six metrics.

    Search Precision only applies to "search" actions — for chat/compare/buy/show
    it is set to 0.0 since no keyword-based search was performed.

    Returns:
        {
            "search_precision": float (0.0-1.0),
            "source_coverage": float (0.0-1.0),
            "response_accuracy": float (0.0-1.0),
            "faithfulness": float (0.0-1.0),
            "answer_relevancy": float (0.0-1.0),
            "context_recall": float (0.0-1.0),
        }
    """
    # ── Build product context for LLM-based metrics ──
    has_product_context = len(products) > 0
    if has_product_context:
        context_texts = [f"{p.title}: {p.description}" for p in products[:5]]
        context_text = "\n".join(f"- {c}" for c in context_texts)
    else:
        context_text = ""

    # ── Metric 1: Search Precision (only for "search" actions) ──
    if action == "search":
        search_precision = _calculate_search_precision(question, products)
        print(f"[Evaluator] Search Precision: {len(products)} products, "
              f"keywords=[{_extract_keywords(question)}] -> {search_precision:.2f}", flush=True)
    else:
        search_precision = 0.0
        print(f"[Evaluator] Search Precision: skipped (action={action}) -> 0.0", flush=True)

    # ── Metric 2: Source Coverage ──
    source_coverage = _calculate_source_coverage(products)
    print(f"[Evaluator] Source Coverage: {source_coverage:.2f} "
          f"(sources used: {set(p.source for p in products)})", flush=True)

    # ── Metric 3: Response Accuracy ──
    if has_product_context:
        response_accuracy = await _evaluate_response_accuracy(answer, context_text)
    else:
        response_accuracy = 1.0  # No products to verify against
        print(f"[Evaluator] No products -- Response Accuracy defaulted to 1.0", flush=True)

    # ── Legacy Metrics: Faithfulness, Answer Relevancy, Context Recall ──
    legacy = await _calculate_legacy_metrics(question, answer, context_text if has_product_context else "No products retrieved.")

    scores = {
        "search_precision": round(search_precision, 2),
        "source_coverage": round(source_coverage, 2),
        "response_accuracy": round(response_accuracy, 2),
        "faithfulness": round(legacy["faithfulness"], 2),
        "answer_relevancy": round(legacy["answer_relevancy"], 2),
        "context_recall": round(legacy["context_recall"], 2),
    }
    print(f"[Evaluator] Scores: {scores}", flush=True)
    return scores


# ═══════════════════════════════════════════════════════════════
# Metric 1: Search Precision — keyword overlap
# ═══════════════════════════════════════════════════════════════

def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from user query."""
    words = text.lower().split()
    return [w.strip(".,!?;:'\"") for w in words
            if w.strip(".,!?;:'\"") not in _STOP_WORDS
            and len(w.strip(".,!?;:'\"")) > 1]


def _calculate_search_precision(query: str, products: List[Product]) -> float:
    """
    Keyword-based search precision.

    For each returned product, check if any of the query's meaningful
    keywords appear in the product's title or category.
    Score = matching_products / total_products.

    Completely objective — no LLM calls.
    """
    keywords = _extract_keywords(query)

    if not keywords or not products:
        return 0.0

    relevant_count = 0
    for p in products:
        title_lower = p.title.lower()
        category_lower = p.category.lower()
        # Check if any query keyword appears in title or category
        for kw in keywords:
            if kw in title_lower or kw in category_lower:
                relevant_count += 1
                break

    precision = relevant_count / len(products)

    # Print per-product relevance for debugging
    for p in products:
        title_lower = p.title.lower()
        matches = [kw for kw in keywords if kw in title_lower or kw in p.category.lower()]
        status = "[OK]" if matches else "[--]"
        print(f"  [SearchPrecision] {status} '{p.title[:50]}...' -> matches: {matches}", flush=True)

    print(f"  [SearchPrecision] {relevant_count}/{len(products)} relevant = {precision:.2f}", flush=True)
    return precision


# ═══════════════════════════════════════════════════════════════
# Metric 2: Source Coverage — multi-source utilization
# ═══════════════════════════════════════════════════════════════

def _calculate_source_coverage(products: List[Product]) -> float:
    """
    What fraction of active data sources contributed to the results?

    Coverage = unique_sources_used / TOTAL_ACTIVE_SOURCES
    Capped at 1.0 (can't exceed total available sources).
    """
    if not products:
        return 0.0

    unique_sources = set(p.source for p in products)
    coverage = len(unique_sources) / TOTAL_ACTIVE_SOURCES
    return min(1.0, coverage)


# ═══════════════════════════════════════════════════════════════
# Metric 3: Response Accuracy — claim extraction + verification
# ═══════════════════════════════════════════════════════════════

_ACCURACY_PROMPT = """You are verifying whether a shopping assistant's claims are supported by product data.

Product context:
{context}

Assistant response:
"{answer}"

Task:
1. Extract every factual claim from the assistant's response.
   A factual claim = verifiable statement about product attributes (price, color, material, size, features, ratings, etc.)
   Do NOT include: opinions, suggestions, greetings, "here are some products", "I recommend"

2. For each claim, mark SUPPORTED if the product context EXPLICITLY confirms it,
   or UNSUPPORTED if the context doesn't mention it or contradicts it.

Return JSON only:
{{
  "total_claims": <int>,
  "supported_claims": <int>,
  "claims": [
    {{"claim": "...", "supported": true/false, "evidence": "..."}}
  ]
}}"""


async def _evaluate_response_accuracy(answer: str, context_text: str) -> float:
    """
    Response Accuracy via claim extraction + verification.

    Score = supported_claims / total_claims
    Returns 1.0 if no factual claims to check.
    """
    if not answer.strip():
        return 1.0

    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You extract and verify factual claims. Return JSON only."},
                {"role": "user", "content": _ACCURACY_PROMPT.format(context=context_text, answer=answer)},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        output = (resp.choices[0].message.content or "").strip()
        data = _parse_json(output)

        if data and "claims" in data and isinstance(data["claims"], list) and len(data["claims"]) > 0:
            supported = sum(1 for c in data["claims"] if c.get("supported", False))
            total = len(data["claims"])

            for i, c in enumerate(data["claims"]):
                status = "[OK]" if c.get("supported") else "[XX]"
                print(f"  [Accuracy] {status} ({i+1}/{total}) {c.get('claim', '?')}", flush=True)

            score = supported / total
            print(f"[Evaluator] Response Accuracy: {supported}/{total} claims verified = {score:.2f}", flush=True)
            return score

        print(f"[Evaluator] No factual claims extracted — returning Accuracy=1.0", flush=True)
        return 1.0

    except Exception as e:
        print(f"[Evaluator] Response Accuracy evaluation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return 0.0


# ═══════════════════════════════════════════════════════════════
# Legacy Metrics: Faithfulness + Answer Relevancy + Context Recall
# ═══════════════════════════════════════════════════════════════

_LEGACY_METRICS_PROMPT = """Evaluate the shopping assistant's response on three metrics (0.00-1.00).

User Question: {question}
Assistant Response: "{answer}"

Product Data Available:
{context}

---

1. faithfulness (0.00-1.00):
Does the response avoid fabricating details NOT present in the product data?
- 1.00 = Every claim (price, color, material, features) is explicitly supported
- 0.67 = Mostly faithful, one minor detail not found in data
- 0.33 = Several unsupported claims mixed with supported ones
- 0.00 = Response fabricates details not found anywhere in the product data

2. answer_relevancy (0.00-1.00):
Does the response directly address what the user asked?
- 1.00 = Directly answers the query with relevant product information
- 0.67 = Mostly relevant but includes some unnecessary or off-topic content
- 0.33 = Partially relevant, misses key aspects of the user's question
- 0.00 = Response is completely irrelevant to what the user asked

3. context_recall (0.00-1.00):
What fraction of the available product data did the response actually use?
- 1.00 = Referenced most products and their key attributes (price, features, etc.)
- 0.67 = Referenced some products but missed notable attributes
- 0.33 = Mentioned products without using their specific data
- 0.00 = Ignored all product information entirely

Return JSON only:
{{"faithfulness": 0.00, "answer_relevancy": 0.00, "context_recall": 0.00}}"""


async def _calculate_legacy_metrics(question: str, answer: str, context_text: str) -> dict:
    """
    Single LLM call to compute all three legacy metrics.
    Uses a detailed rubric to produce differentiated, realistic scores.
    """
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert evaluator for AI shopping assistants. Return JSON only."},
                {"role": "user", "content": _LEGACY_METRICS_PROMPT.format(
                    question=question, answer=answer, context=context_text
                )},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        output = (resp.choices[0].message.content or "").strip()
        data = _parse_json(output)

        if data and "faithfulness" in data:
            f = float(data.get("faithfulness", 0.0))
            a = float(data.get("answer_relevancy", 0.0))
            c = float(data.get("context_recall", 0.0))
            f = max(0.0, min(1.0, f))
            a = max(0.0, min(1.0, a))
            c = max(0.0, min(1.0, c))
            print(f"[Legacy] faithfulness={f:.2f}, answer_relevancy={a:.2f}, context_recall={c:.2f}", flush=True)
            return {"faithfulness": f, "answer_relevancy": a, "context_recall": c}

        print(f"[Legacy] Could not parse LLM output, using defaults", flush=True)
        return {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_recall": 0.5}

    except Exception as e:
        print(f"[Legacy] Evaluation failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_recall": 0.0}


# ═══════════════════════════════════════════════════════════════
# JSON parsing helper
# ═══════════════════════════════════════════════════════════════

def _parse_json(text: str) -> Optional[dict]:
    """Robust JSON extraction from LLM output."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try code blocks
    blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', text)
    for block in blocks:
        block = block.strip()
        if block.startswith("{"):
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    # Try any JSON object
    m = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def get_evaluation_summary(scores: dict) -> str:
    """Format evaluation scores for display/logging."""
    parts = []
    for metric, score in scores.items():
        # Target by metric
        targets = {
            "search_precision": 0.7,
            "source_coverage": 0.5,
            "response_accuracy": 0.9,
            "faithfulness": 0.7,
            "answer_relevancy": 0.7,
            "context_recall": 0.5,
        }
        target = targets.get(metric, 0.7)
        status = "PASS" if score >= target else "WARN" if score >= target * 0.7 else "LOW"
        parts.append(f"{metric}={score:.2f} ({status})")
    return " | ".join(parts)
