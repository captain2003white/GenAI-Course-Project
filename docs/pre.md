# Commerce Agents — Presentation Script

---

## 1. System Overview

Commerce Agents is an AI-powered shopping assistant that helps users search, compare, and purchase products through natural conversation.

```
User: "find me a jacket for winter"
Agent: searches 3 data sources → returns 5 
```

**Key components:**
- **Chat interface** — pure HTML/CSS/JS frontend
- **LLM backend** — DeepSeek (OpenAI-compatible) interprets user intent, outputs structured JSON actions
- **Multi-source product search** — 3 free data sources, parallel querying
- **Evaluation system** — 6 metrics measuring search quality, response accuracy, and data coverage
- **Observability** — Langfuse for latency, token usage, full trace tracking
- **Payment** — Stripe test environment

---

## 2. Architecture

```
    User (Chat UI)
       │ POST /chat
       ▼
 ┌─────────────────────────────────┐
 │  FastAPI Backend                │
 │                                 │
 │  ChatAgent                      │
 │    → DeepSeek LLM               │
 │    → Output: {"action",         │
 │       "query", "reply"}         │
 │                                 │
 │  ProductRegistry                │
 │    → FakeStore    (~20 items)   │
 │    → DummyJSON   (~194 items)   │
 │    → Platzi       (~47 items)   │
 │    → [Brave/eBay]  (⏸ pending) │
 │                                 │
 │  Evaluator (6 metrics)          │
 │  Langfuse REST API (traces)     │
 │  Stripe (payment links)         │
 └─────────────────────────────────┘
```

**Data flow per user message:**
1. LLM understands intent → outputs JSON (search/show/compare/buy/chat)
2. Backend executes action → searches all data sources in parallel
3. Results merged, deduplicated, sorted → returned to user
4. Evaluator scores the interaction (async)
5. Trace + scores pushed to Langfuse (There is some latency in this step,but let’s take a look at the test I submitted 10 minutes ago)
6. Results stored in local evaluation dashboard

---

## 3. Data Sources — Why Can't I Search "All the Internet"?

> "I typed 'shoes' and expected to see every shoe in the world. Why did I only get 5?"

**The reality:** We are using 3 static, free APIs:

| Source | Items | Auth | Status |
|--------|-------|------|--------|
| FakeStore | ~20 | None | ✅ Active |
| DummyJSON | ~194 | None | ✅ Active |
| Platzi | ~47 | None | ✅ Active |

That's it. ~260 products total. When you search "shoes", the system searches **only these 3 sources**. It cannot reach Amazon, Walmart, or any real e-commerce platform.

**Why no real web shopping sources?**

We attempted to integrate:
- **Brave Search API** — requires credit card for signup (not available)
- **eBay Developer API** — application still under review (takes weeks)
- **Amazon PA-API** — requires an active Amazon Associate account

So for this demo, we work within the data we have. The architecture is designed to plug in real sources when they become available (see §Future Work).

**How the search works:**
```
User says "shoes"
  → LLM extracts query="shoes"
  → ProductRegistry searches ALL 3 sources in parallel
  → Results merged, deduplicated by title
  → Top 5 returned to user
```

---

## 4. Problems Encountered & Decisions Made

### 4.1 LLM Output: "I Only Speak JSON — Sometimes"

**Problem:** DeepSeek is instructed to output JSON like `{"action": "search", "query": "shoes", "reply": "..."}`. But sometimes it outputs plain text — especially when the user makes a vague request or continues a conversation.

**Crash:** `json.loads()` throws `json.JSONDecodeError` → server returns 500 → chat breaks.

**Fix — 3-layer fallback:**
```python
# Strategy 1: Try parsing the whole output as JSON
# Strategy 2: Extract from markdown code blocks ```json ... ```
# Strategy 3: Find any { ... } object with regex
# If all fail → default to {"action": "chat", "reply": llm_output}
```

No more 500 errors. Any non-JSON output is treated as a chat message.

### 4.2 Langfuse SDK: Things Went Missing

**Problem:** Langfuse Python SDK v2.55.0 has two bugs:

1. `trace.span()` creates **broken observation IDs** — the Langfuse UI shows "Observation not found" for every trace
2. `trace.score()` creates **orphaned scores** — scores appear in the Scores tab but when clicked, show "Trace not found"

This means: traces exist, scores exist, but they are disconnected and unviewable.

**Fix — Ditch the SDK, use REST API directly:**
```python
# POST /api/public/traces  → creates trace with full payload (200 OK)
# POST /api/public/scores  → posts score with traceId (200 OK)
# HTTP Basic Auth with public_key + secret_key
```

No SDK bugs to worry about. REST API is stable, documented, and versioned.

### 4.3 The Evaluation That Wasn't Evaluating

**Problem 1 — Binary scores:** Faithfulness was always 0.0 or 1.0. Never 0.75, never 0.5. Because the LLM prompt was a simple "rate from 0 to 1" with no rubric.

**Problem 2 — JSON parsing crash:** The evaluator called DeepSeek with max_tokens=200. DeepSeek uses ~1200 tokens for reasoning before generating output. So the response was always empty → parsing failed → default 0.0.

**Fix — Complete redesign:**

| Before (Ragas-style) | After (Custom) |
|----------------------|----------------|
| Faithfulness: 0 or 1 | **Search Precision** — keyword overlap, no LLM needed |
| Answer Relevancy: 0 or 1 | **Source Coverage** — unique sources used / total, no LLM needed |
| — | **Response Accuracy** — claim extraction + verification via LLM (max_tokens=1500) |
| — | **Faithfulness** — 4-level LLM rubric (0.00/0.33/0.67/1.00) |
| — | **Answer Relevancy** — 4-level LLM rubric |
| — | **Context Recall** — 4-level LLM rubric |

**Key insight:** We only need **2 LLM calls** for all 6 metrics (Response Accuracy is one call, 3 legacy metrics are another call). The other 2 metrics (Search Precision, Source Coverage) are pure algorithms — zero cost, zero latency.

### 4.4 Windows GBK: The Unicode Nightmare

**Problem:** `print("✓ 3/5 claims verified")` crashes on Windows terminal because `✓` (U+2713) cannot be encoded in GBK.

**Fix:** Replace all Unicode symbols with ASCII: `[OK]`, `[XX]`, `[--]`, `->`.

### 4.5 Evaluation Scores — Real Data

```
✅ PASS — "find me a jacket"
   Search Precision = 0.80  (4/5 products contain "jacket" in title)
   Source Coverage  = 0.67  (products from 2 of 3 sources)
   Response Accuracy = 1.00 (all AI claims verified against product data)

✅ FAIL — "find electronics"  
   Search Precision = 0.00  (no products match — honest)
   Source Coverage  = 0.00
   Response Accuracy = 1.00 (AI said "nothing found" — that's true)
```

The low scores are not bugs — they are **honest signals** about data limitations. When no products match, the AI says "I couldn't find anything" and gets full marks for accuracy.

---

## 5. Live Demo

### 5.1 Startup

```bash
cd backend
source venv/Scripts/activate
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` (chat) and `http://localhost:8000/eval-dashboard` (developer console).

### 5.2 Demo Script

#### 5.2.1 Basic Functions (one session)

> Demonstrate core features: search, favorite, compare, detail view, purchase

```
User: "find me a shirt"
       → Products returned as cards with source badges (fakestore / dummyjson / platzi)
       → Hover shows action buttons: ⭐ Favorite / 🔍 Detail

      Click ⭐ star → product is favorited
      Click product → detail modal with full info
      Select two products → Compare button → side-by-side comparison panel
      Click buy button → Confirm Purchase → Pay with Stripe → redirected to Stripe checkout

User: "i want to buy the first one"
       → Stripe payment modal opens
       → Enter test card 4242 4242 4242 4242 → payment succeeds
```

#### 5.2.2 Multi-turn Conversation (new session)

> 新建一个 session，连续输入以下 5 条消息

```
User: "find me some jewelery"
User: "I need a jacket for winter, any recommendations?"
User: "great! now i also need women's clothing for my mom"
User: "perfect. can you search for laptops or electronics?"
User: "also show me some electronics"
```

> 第 2 条不是简单重复搜索，而是追问"推荐"——LLM 理解这是在上一轮结果基础上的追问。第 3 条换了品类（jacket → backpack），LLM 识别为新搜索。

#### 5.2.3 After Demo — eval-dashboard

> 演示完后打开 `/eval-dashboard`，展示刚刚所有交互的记录

**Recent Traces 页面:**
```
- 表格列: Time | Action | Query | Precision | Coverage | Accuracy | Products | Langfuse
- 刚刚输入的 6-7 条消息全部在这里，按时间倒序排列
- 绿色 = 达标，黄色 = 警告，红色 = 未达标
- 点击任意行 → 底部展开 Detail 面板: 完整 query、reply、6 个分数、目标值、Langfuse 链接
```

**Metrics 页面:**
```
┌─ v2.0 New Metrics ───────────────────────────────────┐
│  ● Search Precision   0.57    50% pass               │
│  ● Source Coverage    0.49    62% pass               │
│  ● Response Accuracy  1.00   100% pass               │
├─ v1.0 Legacy Metrics ────────────────────────────────┤
│  ● Faithfulness       1.00   100% pass               │
│  ● Answer Relevancy   0.51    19% pass               │
│  ● Context Recall     0.15    15% pass               │
└──────────────────────────────────────────────────────┘
```

**Langfuse (if time permits):**
```
打开 Langfuse → 搜索 sessionId
→ trace 详情: input (用户消息)、output (AI 回复)、metadata (action、product_count、sources)
→ Scores 标签页: 6 个评估分数
```

---

## 6. Evaluation Metrics

| Metric | Method | Target | LLM Cost |
|--------|--------|--------|---------|
| Search Precision | Keyword overlap (algorithmic) | ≥ 0.70 | Free |
| Source Coverage | Unique sources / total (algorithmic) | ≥ 0.50 | Free |
| Response Accuracy | Claim extraction + verification | ≥ 0.90 | 1 call |
| Faithfulness | 4-level rubric (0.00/0.33/0.67/1.00) | ≥ 0.70 | 1 call (all 3 legacy) |
| Answer Relevancy | 4-level rubric | ≥ 0.70 | same call |
| Context Recall | 4-level rubric | ≥ 0.50 | same call |

**Why these 6?**
- **Search Precision** — If the search returns irrelevant products, the AI's response is built on garbage
- **Source Coverage** — We have 3 data sources; this metric proves the multi-source architecture is actually being used
- **Response Accuracy** — Prevents AI hallucination (claiming a product has features it doesn't)
- **Faithfulness** — Did the AI fabricate details not in the product data?
- **Answer Relevancy** — Did the AI answer what the user actually asked?
- **Context Recall** — Did the AI utilize the available product information?

---

## 7. Future Work

### 7.1 "Show More" Button
Currently limited to top 5 results per query. A "Show More" button would let users browse deeper results without changing their search.

### 7.2 Web Shopping Sources
If the eBay API review passes, or if we can set up Brave Search API payment, we would connect to real e-commerce data:
- eBay Browse API — real-time product listings
- Brave Search API — web-scale product search
- Amazon PA-API — affiliate product data

This would transform Commerce Agents from a "demo with static data" to a "real shopping assistant."

### 7.3 Other Improvements
| Feature | Why |
|---------|-----|
| User feedback loop (thumbs up/down) | Tune evaluation weights based on real user preference |
| A/B testing framework | Compare two agent versions side-by-side |
| Regression test suite | 50+ test cases run automatically on every prompt update |
| Multi-modal search | Image-based product search |

---

## Appendix: Q&A Preparation

### Q: Why not just use GPT-4?
A: DeepSeek costs ~1/10 of GPT-4 and is OpenAI API-compatible — we can switch models with one line of config. For this project's scale (demo + evaluation), DeepSeek is more than sufficient.

### Q: How do you prevent LLM JSON parsing failures?
A: 3-layer fallback: direct parse → markdown extraction → regex scan. If all fail, treat as chat message (action="chat"). Never 500 error.

### Q: The scores seem low for some queries — is the system broken?
A: No. Low Search Precision means our limited data sources didn't have matching products. The system is working correctly by honestly reporting "no results found." Response Accuracy is still 1.0 in these cases — the AI told the truth.

### Q: Why store evaluations locally AND in Langfuse?
A: Langfuse for team sharing and trend analysis; local store for real-time dashboard and offline access. Redundancy is intentional — Langfuse could go down, but the dashboard should keep working.

### Q: How much does evaluation cost?
A: ~1500 tokens per evaluation call (~2 calls per interaction) at DeepSeek pricing ≈ $0.00003 per interaction. Even at 100k interactions/day, evaluation costs < $3/day.
