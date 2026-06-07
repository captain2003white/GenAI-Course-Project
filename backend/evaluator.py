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
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = "deepseek-chat"

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
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent scoring
            max_tokens=200,
        )

        output = response.choices[0].message.content.strip()

        # Extract JSON
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            output = output.split("```")[1].split("```")[0].strip()

        scores = json.loads(output)
        return {
            "faithfulness": round(float(scores.get("faithfulness", 0.0)), 2),
            "answer_relevancy": round(float(scores.get("answer_relevancy", 0.0)), 2),
        }

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
