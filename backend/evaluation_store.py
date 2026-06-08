"""
In-memory evaluation store — records all evaluation scores for the dashboard.
"""

from datetime import datetime
from typing import List, Dict
import threading

# Thread-safe in-memory store
_lock = threading.Lock()
_evaluations: List[Dict] = []
_MAX_RECORDS = 200


def add_evaluation(
    question: str,
    answer: str,
    faithfulness: float,
    answer_relevancy: float,
    product_count: int = 0,
):
    """Store an evaluation result with timestamp."""
    with _lock:
        _evaluations.append({
            "timestamp": datetime.now().isoformat(),
            "question": question[:100],
            "answer": answer[:100],
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "product_count": product_count,
        })
        # Keep only last N records
        if len(_evaluations) > _MAX_RECORDS:
            _evaluations[:] = _evaluations[-_MAX_RECORDS:]


def get_evaluations(limit: int = 50) -> List[Dict]:
    """Get recent evaluations (newest first)."""
    with _lock:
        return list(reversed(_evaluations[-limit:]))


def get_summary() -> Dict:
    """Get aggregated metrics."""
    with _lock:
        if not _evaluations:
            return {
                "total": 0,
                "avg_faithfulness": 0.0,
                "avg_answer_relevancy": 0.0,
                "pass_rate_faithfulness": 0.0,
                "pass_rate_relevancy": 0.0,
                "trend": [],
            }
        recent = _evaluations[-50:]
        faithfulness_scores = [e["faithfulness"] for e in recent]
        relevancy_scores = [e["answer_relevancy"] for e in recent]
        avg_f = sum(faithfulness_scores) / len(faithfulness_scores)
        avg_r = sum(relevancy_scores) / len(relevancy_scores)
        pass_f = sum(1 for s in faithfulness_scores if s >= 0.7) / len(faithfulness_scores)
        pass_r = sum(1 for s in relevancy_scores if s >= 0.7) / len(relevancy_scores)
        # Trend: last 10 records for sparkline
        trend = [
            {"seq": i + 1, "faithfulness": e["faithfulness"], "answer_relevancy": e["answer_relevancy"]}
            for i, e in enumerate(recent[-10:])
        ]
        return {
            "total": len(_evaluations),
            "avg_faithfulness": round(avg_f, 2),
            "avg_answer_relevancy": round(avg_r, 2),
            "pass_rate_faithfulness": round(pass_f * 100, 1),
            "pass_rate_relevancy": round(pass_r * 100, 1),
            "trend": trend,
        }
