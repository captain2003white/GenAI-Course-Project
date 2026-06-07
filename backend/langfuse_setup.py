"""
Langfuse observability configuration

This module handles:
1. Langfuse client initialization
2. LLM call tracing (Trace → Span structure)
3. Evaluation score recording

Trace structure example:
  trace: "session-session123"
    ├── span: "demand-understanding"
    ├── span: "product-search"
    ├── span: "llm-generation"
    └── span: "payment"
"""

from langfuse import Langfuse
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Initialize Langfuse with environment variables
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)


def get_langfuse():
    """Get the Langfuse instance"""
    return langfuse


def create_trace(session_id: str, user_message: str):
    """Create a new trace for a conversation"""
    return langfuse.trace(
        name="commerce-agent-session",
        session_id=session_id,
        input=user_message,
        metadata={"app": "Commerce Agents"}
    )


def update_trace_with_score(
    trace,
    evaluation_name: str,
    score: float,
    comment: Optional[str] = None
):
    """Add an evaluation score to a trace"""
    trace.score(
        name=evaluation_name,
        value=score,
        comment=comment
    )
