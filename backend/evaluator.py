"""
Evaluation module — LLM-as-a-Judge

Computes Faithfulness and Answer Relevancy scores using DeepSeek as the evaluator LLM.
Mirrors Ragas methodology but avoids dependency conflicts.

Metrics:
- Faithfulness: Is the answer grounded in the retrieved product info? (0.0 - 1.0)
- Answer Relevancy: Is the answer relevant to the user's question? (0.0 - 1.0)
"""

import os
import json
import re
import sys
from typing import List
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

EVALUATION_SYSTEM_PROMPT = """You are an expert evaluator for AI shopping assistants.
Rate the assistant's response on two metrics from 0.0 to 1.0:

1. faithfulness: Does the response ONLY contain information that can be verified from the provided product context?
   - 1.0 = perfectly faithful, no invented information
   - 0.0 = completely made up, information not in context

2. answer_relevancy: Does the response actually address what the user asked?
   - 1.0 = perfectly relevant and complete
   - 0.0 = completely irrelevant

Return a JSON object with both scores and a brief reason."""


async def evaluate_response(
    question: str,
    answer: str,
    contexts: List[str],
) -> dict:
    """
    Evaluate a single chat interaction using LLM-as-a-Judge.

    Uses DeepSeek to compute Faithfulness and Answer Relevancy scores.
    These match the Ragas methodology conceptually.
    """
    if not contexts:
        contexts = ["No products were retrieved for this query."]

    context_text = "\n".join(f"- {c}" for c in contexts[:5])

    user_prompt = f"""User question: {question}
Assistant response: {answer}

Retrieved product context:
{context_text}

Evaluate this interaction. Return JSON only:
{{"faithfulness": 0.0-1.0, "answer_relevancy": 0.0-1.0, "reason": "brief explanation"}}"""

    try:
        print(f"[Evaluator] Sending evaluation request to DeepSeek model={MODEL}...", flush=True)
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent scoring
            max_tokens=500,
        )
        print(f"[Evaluator] Got response from DeepSeek", flush=True)
        finish_reason = response.choices[0].finish_reason
        output = (response.choices[0].message.content or "").strip()
        print(f"[Evaluator] finish_reason={finish_reason}, response length={len(output)}", flush=True)

        # If response is empty (token limit hit), retry with minimal prompt
        if not output:
            print(f"[Evaluator] Empty response, retrying with minimal prompt...", flush=True)
            minimal_prompt = f"Rate from 0-1:\nfaithfulness= (is answer based on context?)\nanswer_relevancy= (does answer address question?)\n\nQuestion: {question}\nAnswer: {answer}\nContext: {context_text}"
            response2 = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Output a JSON object with keys faithfulness (0-1) and answer_relevancy (0-1). No other text."},
                    {"role": "user", "content": minimal_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            output = (response2.choices[0].message.content or "").strip()
            print(f"[Evaluator] Retry response length={len(output)}", flush=True)

        # Try 1: Parse entire output as JSON directly
        scores = None
        try:
            scores = json.loads(output)
        except json.JSONDecodeError:
            # Try 2: Extract JSON from markdown code blocks
            if "```" in output:
                # Find content between backticks
                blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', output)
                for block in blocks:
                    block = block.strip()
                    if block.startswith("{"):
                        try:
                            scores = json.loads(block)
                            if scores and "faithfulness" in scores:
                                break
                        except json.JSONDecodeError:
                            continue

            # Try 3: Find a JSON-like object `{...}` anywhere in the text
            if scores is None:
                json_match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', output)
                if json_match:
                    try:
                        scores = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

        if scores and "faithfulness" in scores:
            print(f"[Evaluator] Parsed scores: faithfulness={scores['faithfulness']}, answer_relevancy={scores.get('answer_relevancy', 'N/A')}", flush=True)
            return {
                "faithfulness": round(float(scores.get("faithfulness", 0.0)), 2),
                "answer_relevancy": round(float(scores.get("answer_relevancy", 0.0)), 2),
            }
        else:
            print(f"[Evaluator] Could not extract valid JSON scores from response", flush=True)
            return {"faithfulness": 0.0, "answer_relevancy": 0.0}

    except Exception as e:
        print(f"[Evaluator] LLM evaluation failed: {e}")
        return {"faithfulness": 0.0, "answer_relevancy": 0.0}


def get_evaluation_summary(scores: dict) -> str:
    """Format evaluation scores for display/logging"""
    parts = []
    for metric, score in scores.items():
        status = "PASS" if score >= 0.7 else "LOW"
        parts.append(f"{metric}={score:.2f} ({status})")
    return " | ".join(parts)
