"""
In-memory evaluation store — records all evaluation data for the dashboard.
"""

from datetime import datetime
from typing import List, Dict, Optional
import threading

_lock = threading.Lock()
_evaluations: List[Dict] = []
_MAX_RECORDS = 200


def add_evaluation(
    question: str,
    answer: str,
    search_precision: float = 0.0,
    source_coverage: float = 0.0,
    response_accuracy: float = 0.0,
    faithfulness: float = 0.0,
    answer_relevancy: float = 0.0,
    context_recall: float = 0.0,
    product_count: int = 0,
    sources: Optional[List[str]] = None,
    trace_id: str = "",
    action: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
):
    """Store an evaluation result with timestamp."""
    with _lock:
        _evaluations.append({
            "timestamp": datetime.now().isoformat(),
            "question": question[:150],
            "answer": answer[:200],
            "search_precision": search_precision,
            "source_coverage": source_coverage,
            "response_accuracy": response_accuracy,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_recall": context_recall,
            "product_count": product_count,
            "sources": sources or [],
            "trace_id": trace_id,
            "action": action,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        })
        if len(_evaluations) > _MAX_RECORDS:
            _evaluations[:] = _evaluations[-_MAX_RECORDS:]


def get_evaluations(limit: int = 50) -> List[Dict]:
    """Get recent evaluations (newest first)."""
    with _lock:
        return list(reversed(_evaluations[-limit:]))


def get_evaluation_by_trace(trace_id: str) -> Optional[Dict]:
    """Get a single evaluation by trace ID."""
    with _lock:
        for e in reversed(_evaluations):
            if e.get("trace_id") == trace_id:
                return e
    return None


def get_summary() -> Dict:
    """Get aggregated metrics (new + legacy)."""
    with _lock:
        if not _evaluations:
            return {
                "total": 0,
                "avg_search_precision": 0.0,
                "avg_source_coverage": 0.0,
                "avg_response_accuracy": 0.0,
                "avg_faithfulness": 0.0,
                "avg_answer_relevancy": 0.0,
                "avg_context_recall": 0.0,
                "pass_rate_search_precision": 0.0,
                "pass_rate_source_coverage": 0.0,
                "pass_rate_response_accuracy": 0.0,
            }
        recent = _evaluations[-50:]
        # Only "search" actions count toward Search Precision / Source Coverage
        search_evals = [e for e in recent if e.get("action") == "search"]
        sp = [e.get("search_precision", 0) for e in search_evals]
        sc = [e.get("source_coverage", 0) for e in search_evals]
        ra = [e.get("response_accuracy", 0) for e in recent]
        ft = [e.get("faithfulness", 0) for e in recent]
        ar = [e.get("answer_relevancy", 0) for e in recent]
        cr = [e.get("context_recall", 0) for e in recent]

        def avg(vals):
            return sum(vals) / len(vals) if vals else 0

        def pass_rate(vals, threshold):
            return sum(1 for s in vals if s >= threshold) / len(vals) if vals else 0

        return {
            "total": len(_evaluations),
            "avg_search_precision": round(avg(sp), 2),
            "avg_source_coverage": round(avg(sc), 2),
            "avg_response_accuracy": round(avg(ra), 2),
            "avg_faithfulness": round(avg(ft), 2),
            "avg_answer_relevancy": round(avg(ar), 2),
            "avg_context_recall": round(avg(cr), 2),
            "pass_rate_search_precision": round(pass_rate(sp, 0.7) * 100, 1),
            "pass_rate_source_coverage": round(pass_rate(sc, 0.5) * 100, 1),
            "pass_rate_response_accuracy": round(pass_rate(ra, 0.9) * 100, 1),
            "pass_rate_faithfulness": round(pass_rate(ft, 0.7) * 100, 1),
            "pass_rate_answer_relevancy": round(pass_rate(ar, 0.7) * 100, 1),
            "pass_rate_context_recall": round(pass_rate(cr, 0.5) * 100, 1),
        }
