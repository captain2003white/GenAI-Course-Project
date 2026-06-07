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
import uuid

from models.schemas import ChatRequest, ChatResponse, PaymentRequest, PaymentResponse, Product
from agents.chat_agent import ChatAgent
from tools.search import get_product_by_id, search_products
from tools.payment import create_payment_link
from langfuse_setup import get_langfuse, create_trace, update_trace_with_score
from evaluator import evaluate_response, get_evaluation_summary

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

# Initialize Langfuse
langfuse = get_langfuse()


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
    2. Create Langfuse trace
    3. ChatAgent processes the message (LLM intent understanding -> product search -> reply generation)
    4. Record trace information
    5. Return response
    """
    # Step 1: Session management
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = {
            "agent": ChatAgent(),
            "history": [],
        }

    # Step 2: Create Langfuse trace
    trace = create_trace(session_id, request.message)

    try:
        # Step 3: ChatAgent processing
        agent = sessions[session_id]["agent"]
        result = await agent.process_message(request.message)

        # Step 4: Record trace
        trace.update(output=result["reply"])
        trace.span(
            name="llm-call",
            input=request.message,
            output=result["reply"],
            metadata={
                "action": result.get("action"),
                "product_count": len(result.get("products", [])),
            }
        )
        langfuse.flush()

        # Step 5: Evaluate with Ragas (async, non-blocking)
        try:
            contexts = [f"{p.title}: {p.description}" for p in result.get("products", [])]
            scores = await evaluate_response(
                question=request.message,
                answer=result["reply"],
                contexts=contexts,
            )
            # Push scores to Langfuse trace
            for metric, score in scores.items():
                update_trace_with_score(trace, metric, score)
            langfuse.flush()
            print(f"[Evaluation] {get_evaluation_summary(scores)}")
        except Exception as eval_err:
            print(f"[Evaluation] Failed: {eval_err}")

        # Step 6: Return response
        return ChatResponse(
            reply=result["reply"],
            products=result.get("products", []),
            session_id=session_id,
        )

    except Exception as e:
        trace.update(output=f"Error: {str(e)}")
        langfuse.flush()  # Ensure errors are also recorded
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
