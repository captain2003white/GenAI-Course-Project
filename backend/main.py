"""
Commerce Agents — FastAPI backend entry point

This file is the central orchestrator:
1. Receives user messages from the frontend
2. Calls ChatAgent for processing (LLM + search)
3. Records all operations to Langfuse
4. Returns results to the frontend

Start command:
  uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uuid
import os

from models.schemas import ChatRequest, ChatResponse, PaymentRequest, PaymentResponse, Product
from agents.chat_agent import ChatAgent
from tools.search import get_product_by_id, search_products
from tools.payment import create_payment_link
from langfuse_setup import create_trace_api, post_score_via_api
from evaluator import evaluate_response, get_evaluation_summary
from evaluation_store import add_evaluation, get_evaluations, get_summary, get_evaluation_by_trace

app = FastAPI(title="Commerce Agents", version="1.0.0")

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions in memory
sessions: dict[str, dict] = {}

# Langfuse observability via REST API (bypasses SDK v2.55.0 bugs)


@app.get("/health")
async def health_check():
    """Health check endpoint — verify the service is running"""
    return {"status": "ok", "app": "Commerce Agents"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Core API: Chat + product search

    Flow:
    1. Create/get session
    2. Process message via ChatAgent (LLM intent -> product search -> reply)
    3. Create Langfuse trace (via REST API, bypassing SDK v2.55.0 bugs)
    4. Evaluate response (Faithfulness + Answer Relevancy)
    5. Push scores to Langfuse (via REST API)
    6. Store in local evaluation dashboard
    7. Return response
    """
    # Step 1: Session management
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = {
            "agent": ChatAgent(),
            "history": [],
        }

    try:
        # Step 2: Process message
        agent = sessions[session_id]["agent"]
        result = await agent.process_message(request.message)

        # Step 3: Create Langfuse trace via REST API (includes output + metadata
        # in one call, because Langfuse Public API does not support PATCH updates)
        products = result.get("products", [])
        sources_used = list(set(p.source for p in products))
        source_breakdown: dict = {}
        for p in products:
            source_breakdown[p.source] = source_breakdown.get(p.source, 0) + 1

        trace_id = await create_trace_api(
            session_id=session_id,
            user_message=request.message,
            output=result["reply"],
            metadata={
                "action": result.get("action"),
                "product_count": len(products),
                "sources": sources_used,
                "source_breakdown": source_breakdown,
            },
            usage=result.get("usage"),
        )

        # Step 4: Evaluate (async)
        try:
            scores = await evaluate_response(
                question=request.message,
                answer=result["reply"],
                products=products,
                action=result.get("action", ""),
            )
            # Push scores to Langfuse via REST API
            if trace_id:
                for metric, score in scores.items():
                    print(f"[Main] Recording score to Langfuse: {metric}={score} (trace_id={trace_id[:12]}...)", flush=True)
                    await post_score_via_api(
                        trace_id=trace_id,
                        name=metric,
                        value=score,
                    )
            # Store in local evaluation dashboard
            add_evaluation(
                question=request.message,
                answer=result["reply"],
                search_precision=scores.get("search_precision", 0.0),
                source_coverage=scores.get("source_coverage", 0.0),
                response_accuracy=scores.get("response_accuracy", 0.0),
                faithfulness=scores.get("faithfulness", 0.0),
                answer_relevancy=scores.get("answer_relevancy", 0.0),
                context_recall=scores.get("context_recall", 0.0),
                product_count=len(products),
                sources=sources_used,
                trace_id=trace_id or "",
                action=result.get("action", ""),
                prompt_tokens=(result.get("usage") or {}).get("prompt_tokens", 0),
                completion_tokens=(result.get("usage") or {}).get("completion_tokens", 0),
                total_tokens=(result.get("usage") or {}).get("total_tokens", 0),
            )
            print(f"[Evaluation] {get_evaluation_summary(scores)}", flush=True)
        except Exception as eval_err:
            print(f"[Evaluation] Failed: {eval_err}", flush=True)
            import traceback
            traceback.print_exc()

        # Step 7: Return response
        return ChatResponse(
            reply=result["reply"],
            products=result.get("products", []),
            session_id=session_id,
        )

    except Exception as e:
        # Try to record error in Langfuse
        try:
            await create_trace_api(
                session_id=session_id,
                user_message=request.message,
                output=f"Error: {str(e)}",
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/buy", response_model=PaymentResponse)
async def buy(request: PaymentRequest):
    """
    Purchase API: Generate Stripe payment link

    Flow:
    1. Get product info
    2. Call Stripe to create a payment link
    3. Return payment link to frontend
    4. User completes payment on Stripe's hosted page
    """
    product = await get_product_by_id(request.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_data = Product(**product)
    price_cents = int(product_data.price * 100)  # Stripe uses cents

    payment_url = await create_payment_link(
        product_name=product_data.title,
        price_cents=price_cents,
        quantity=request.quantity,
    )

    if not payment_url:
        raise HTTPException(status_code=500, detail="Failed to create payment link")

    return PaymentResponse(
        payment_url=payment_url,
        product_name=product_data.title,
        total_amount=product_data.price * request.quantity,
    )


# ═══════════════════════════════════════════
# Evaluation Dashboard
# ═══════════════════════════════════════════

@app.get("/api/evaluations")
async def get_evaluation_data(limit: int = 50):
    """API: Get recent evaluation scores for the dashboard."""
    return {
        "evaluations": get_evaluations(limit=limit),
        "summary": get_summary(),
    }


@app.get("/api/evaluations/{trace_id}")
async def get_evaluation_detail(trace_id: str):
    """API: Get a single evaluation by trace ID."""
    eval_data = get_evaluation_by_trace(trace_id)
    if not eval_data:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return eval_data


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Main chat interface."""
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


@app.get("/eval-dashboard", response_class=HTMLResponse)
async def evaluation_dashboard():
    """Evaluation Dashboard page — real-time metrics display."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "eval-dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
