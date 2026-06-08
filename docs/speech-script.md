# Commerce Agents — 10-Minute Presentation Script (Bilingual)

> 使用说明：英文是正式演讲内容，中文是你背稿时的理解辅助。
> 标注 **(Say this)** 的是要念出来的，标注 `[Action]` 的是操作。
> 每段开头有 ⏱ 时间参考，总共约 10 分钟。

---

## 1. System Overview ⏱ 30s

**(Say this)**
"Hi everyone, today I'd like to show you Commerce Agents — an AI-powered shopping assistant I built. It lets users search, compare, and purchase products through natural conversation."

"大家好，今天演示 Commerce Agents，一个 AI 购物助手。用户通过自然语言就可以搜索、对比、购买商品。"

"The core idea: instead of clicking through menus, you just type what you want — 'find me a jacket' — and the AI handles the rest: searching multiple data sources, recommending products, even handling payment."

"核心理念：不用点菜单，直接打字说你要什么，AI 去搜多个数据源、推荐商品、甚至处理支付。"

---

## 2. Architecture ⏱ 1min

**(Say this)**
"Let me quickly explain the architecture."

"快速过一下架构。"

> 可以指着架构图讲，边指边说

"Frontend is pure HTML/CSS/JS — no framework. Backend is FastAPI. The core is a ChatAgent that calls DeepSeek LLM to understand user intent and output structured JSON: what action to take, what to search, what to reply."

"前端纯 HTML/CSS/JS，后端 FastAPI。核心是 ChatAgent，调 DeepSeek 理解意图，输出结构化 JSON。"

"Behind the scenes, a ProductRegistry searches three data sources in parallel — FakeStore, DummyJSON, and Platzi — then merges and deduplicates results."

"ProductRegistry 并行查询三个数据源，合并去重后返回。"

"We also have an evaluation system with 6 metrics, Langfuse for observability, and Stripe for payments."

"还有 6 个评估指标、Langfuse 可观测性、Stripe 支付。"

---

## 3. Data Sources — The Hard Truth ⏱ 2min

> 这是重点段落——数据源限制是项目的核心故事。讲慢一点，突出"为什么只有 260 个商品"

**(Say this)**
"Now, important context. When you search 'shoes', you might expect to see every shoe on the internet. That's not what happens here."

"重要背景：搜 'shoes' 不会出现互联网上所有的鞋。"

"We are using three free, static APIs. FakeStore has about 20 items, DummyJSON has about 194, Platzi has about 47. Total: roughly 260 products. That's it."

"我们用了三个免费的静态 API。FakeStore ~20 件，DummyJSON ~194 件，Platzi ~47 件。总共大约 260 件商品。就这么多了。"

**(Say this)**
"So why don't we connect to real shopping sources?"

"那为什么不接真实的购物源呢？"

"We tried. Three integration attempts failed:"
- "Brave Search API — requires a credit card to sign up. We don't have one."
- "eBay Developer API — application still under review. Takes weeks."
- "Amazon PA-API — requires an active Amazon Associate account."

"我们尝试过三次集成：Brave 要信用卡注册、eBay 审核了几周没通过、Amazon 需要联盟营销账号。"

**(Say this)**
"This is actually an honest limitation worth discussing. For a production version, the architecture supports plugging in real sources — the ProductRegistry has a clean interface. But for this demo, we work within our 260 products."

"这是个诚实的限制。生产版本随时可以接入真实源——架构已经设计好了——但演示版就在 260 件商品里跑。"

"If a search returns nothing, the AI says 'I couldn't find anything' — and that's honest. The system works correctly; it's the data that's limited."

"搜不到就是搜不到，AI 诚实地说找不到。系统没坏，是数据有限。"

---

## 4. Problems Encountered & Decisions ⏱ 2min

> 选 2-3 个最有说服力的讲，不用全讲。推荐 4.1 + 4.3 + 4.4

### 4.1 JSON Parsing (30s)

**(Say this)**
"First problem: the LLM is supposed to output JSON. But sometimes it outputs plain text, especially when the user is vague. The server would crash — json.loads throws an error, returns a 500."

"第一个问题：LLM 偶尔不输出 JSON 直接说人话，服务器 json.loads 崩溃返回 500。"

"The fix? A three-layer fallback: try direct parse, try extracting from markdown code blocks, try regex. If all fail, treat it as a chat message. Never crash."

"三层 fallback：直接解析 → markdown 代码块提取 → 正则扫描。全失败就当聊天消息处理。再也不崩了。"

### 4.2 Evaluation Redesign (1min) ⏱ 推荐优先讲这个

**(Say this)**
"The evaluation system went through a major redesign. Originally it had two metrics — Faithfulness and Answer Relevancy — that always returned 0 or 1, never anything in between. A binary score tells you nothing."

"评估系统大改过。原来只有 Faithfulness 和 Answer Relevancy，永远返回 0 或 1。二分法没有意义。"

"Also, the LLM call had max_tokens set to 200. DeepSeek uses about 1200 tokens just for reasoning before generating output. So the response was always empty, parsing always failed, score always 0."

"而且 max_tokens 设成 200，DeepSeek 思考就要 1200 token，输出一直是空的，分永远是 0。"

**(Say this)**
"The redesign gave us six metrics total:"
- "Search Precision — keyword overlap, no LLM needed, free"
- "Source Coverage — unique sources used, also free"
- "Response Accuracy — claim extraction + LLM verification"
- "Faithfulness, Answer Relevancy, Context Recall — all with a proper 4-level rubric"

"重新设计后变成 6 个指标：Search Precision（关键词匹配，免费）、Source Coverage（数据源覆盖，免费）、Response Accuracy（声明验证）和三个传统指标（带 4 级评分标准）。"

"Key insight: we only need two LLM calls for all six metrics. The other two are pure algorithms — zero cost."

"关键洞察：6 个指标只需要 2 次 LLM 调用。另外 2 个纯算法，零成本。"

### 4.3 Langfuse SDK Bug (20s)

**(Say this)**
"We used the Langfuse Python SDK for observability. Version 2.55 has two bugs: trace.span creates broken observation IDs, and trace.score creates orphaned scores. Traces exist, scores exist, but they're disconnected."

"Langfuse SDK v2.55 有两个 bug：trace.span 生成了无效的 observation ID，trace.score 生成了孤立的分数。数据都在但连不上。"

"Fix: ditch the SDK, call the REST API directly. Stable, documented, works."

"直接换 REST API，稳定可靠。"

### 4.4 Windows GBK (10s)

**(Say this)**
"Printing a checkmark character crashes on Windows terminal because of GBK encoding. Fixed by replacing all Unicode symbols with ASCII — [OK] instead of ✓."（笑一下带过）

"Windows 终端打印 ✓ 会崩溃，GBK 编码问题。全换成 ASCII [OK] 就好了。"

---

## 5. Live Demo ⏱ 3min

> 演示阶段，边操作边说

### 5.1 Startup (15s)

**(Say this)**
`[打开浏览器，指向 localhost:8000]`
"Server is running. Here's the chat interface. Clean, minimal."

"服务器已启动，聊天界面，简洁干净。"

### 5.2 Basic Search (45s)

**(Say this)**
"Let's start. I'll type: 'find me a shirt'."

`[输入 find me a shirt]`

"Five products come back as cards. Each card has a source badge showing where it came from — FakeStore, DummyJSON, Platzi. This proves the multi-source architecture is working."

"返回五张商品卡片，每张有来源标签，证明多源架构在跑。"

`[hover 展示按钮，点击 star，点击商品弹窗]`

"On hover, action buttons appear: favorite, detail view. Click favorite to save it. Click the card to see full details in a modal."

"悬停出现操作按钮：收藏、查看详情。点击收藏，点击卡片看详情弹窗。"

### 5.3 Compare + Payment (30s)

**(Say this)**
"Select two products, click Compare — you get a side-by-side comparison panel."

`[选两个商品，点 Compare]`

"Now let's buy something. Type: 'i want to buy the first one'."

`[输入 i want to buy the first one]`

"A Stripe payment modal opens. Enter test card 4242 4242 4242 4242 and it processes successfully."

"弹出 Stripe 支付窗口。输入测试卡号，支付成功。"

### 5.4 Multi-turn (45s)

`[新开一个 session，快速输入 5 条]`

**(Say this)**
"Now a new session. I'll send five messages in sequence to demonstrate context understanding."

"新建 session，连续输入 5 条，展示上下文理解。"

`[输入 find me a jacket]`
`[输入 I need a jacket for winter, any recommendations?]`

**(Say this)**
"Notice: the second message isn't a new search — it's asking for recommendations based on the previous results. The LLM understands this is a follow-up."

"第二条不是重新搜索，是在问推荐。LLM 理解这是追问。"

`[输入 great! now i also need a backpack for travel]`

"But now we switch from jacket to backpack. The LLM recognizes this as a new search."

"换了品类，LLM 识别为新搜索。"

`[输入 perfect. can you search for laptops or electronics?]`

"And again, switching categories — electronics. Multi-turn, multi-category."

"又换品类，多轮多品类。"

`[输入 also show me some watches or smartwatches]`

"Four different categories in one session. The agent handles them all."

"四个品类，一个 session，全处理了。"

### 5.5 eval-dashboard (45s)

`[切换到 /eval-dashboard]`

**(Say this)**
"Now let's look at the developer dashboard. Every interaction we just did is recorded here."

"打开开发者面板，所有交互都记录在这里了。"

`[指着 Traces 表格]`

"Recent Traces table: time, action type, query, scores. Click any row to see full detail — the complete query, the AI's reply, all six scores."

"Recent Traces 表格：时间、动作类型、查询、分数。点击行看详情——完整 query、回复、6 个分数。"

`[切换到 Metrics 页面]`

"Metrics page: two sections. New metrics v2.0 — Search Precision, Source Coverage, Response Accuracy. Legacy metrics v1.0 preserved for comparison."

"Metrics 页面：两个分区。新版指标和旧版指标（保留做对比）。"

"Search Precision: currently around X% pass rate. This tells us how well our search matches user intent. Source Coverage: around X% — meaning most searches use 2 out of 3 data sources. Response Accuracy: consistently high because the AI either confirms from product data or says nothing."

"Search Precision 约 X% 通过率，说明搜索匹配质量。Source Coverage 约 X%，多数搜索用了 2/3 的数据源。Response Accuracy 稳定在高位，因为 AI 有数据就说、没数据就不说。"

`[如果时间够，打开 Langfuse]`

"And in Langfuse, if time permits, we can see every trace with its full input, output, and all six evaluation scores."

"时间够的话打开 Langfuse 看 trace 详情和 6 个评分。"

---

## 6. Evaluation Metrics Recap ⏱ 30s

> 快速总结，不用展开

**(Say this)**
"To summarize the six metrics:"

"总结 6 个指标："

| Metric | What it measures | Cost |
|--------|-----------------|------|
| Search Precision | Are returned products relevant to the query? | Free |
| Source Coverage | Are we using all available data sources? | Free |
| Response Accuracy | Is the AI's reply factually correct? | 1 LLM call |
| Faithfulness | Does the AI fabricate details? | 1 call (shared) |
| Answer Relevancy | Does the reply address the question? | same call |
| Context Recall | Does the AI use available product info? | same call |

"Only two LLM calls for all six. The other two metrics cost nothing."

"6 个指标只要 2 次 LLM 调用。另外 2 个零成本。"

---

## 7. Q&A Prep ⏱（回答阶段）

> 以下是常见问题的中英文回答，被问到直接看这里

### Q: Why DeepSeek, not GPT-4?
**EN:** "DeepSeek costs about 1/10 of GPT-4 and is OpenAI API-compatible — switching models is one line of config. For this scale, it's more than sufficient."
**ZH:** "DeepSeek 成本约 GPT-4 的 1/10，兼容 OpenAI API，换模型改一行配置。演示场景完全够用。"

### Q: Low scores — is the system broken?
**EN:** "No. Low Search Precision means our limited data sources didn't have matching products. Response Accuracy is still 1.0 in those cases — the AI told the truth."
**ZH:** "低分说明数据源没有匹配商品，不是系统坏了。Response Accuracy 仍然是 1.0——AI 说实话了。"

### Q: Why local storage AND Langfuse?
**EN:** "Langfuse for sharing and trend analysis; local store for real-time dashboard and offline access. If Langfuse goes down, the dashboard keeps working — intentional redundancy."
**ZH:** "Langfuse 用于团队分享和趋势分析；本地存储用于实时面板和离线访问。Langfuse 挂了面板也能用。"

### Q: Evaluation cost at scale?
**EN:** "About 1500 tokens per evaluation, two calls per interaction. At DeepSeek pricing, that's roughly $0.00003 per interaction — less than $3/day at 100k interactions."
**ZH:** "每次评估约 1500 token，两次调用。DeepSeek 定价下每次交互约 $0.00003——10 万次/天不到 $3。"

### Q: Why not real-time web search?
**EN:** "We attempted Brave, eBay, and Amazon integration, but each had barriers — credit card, long review cycles, or account requirements. The architecture supports it, but the demo runs on static data."
**ZH:** "试过 Brave、eBay、Amazon，各有障碍。架构支持接入，但演示版跑在静态数据上。"

---

## 时间控制速查

| 段落 | 时间 | 累计 |
|------|------|------|
| 1. System Overview | 30s | 0:30 |
| 2. Architecture | 1min | 1:30 |
| 3. Data Sources story | 2min | 3:30 |
| 4. Problems & Decisions | 2min | 5:30 |
| 5. Live Demo | 3min 30s | 9:00 |
| 6. Metrics Recap | 30s | 9:30 |
| Q&A | 剩余 | 10:00 |

**关键提醒：**
- 第三部分（数据源限制）和第四部分（踩坑经历）是面试官最感兴趣的——这是 STAR 故事的素材
- 演示别慌，卡住了就说"This is a demo, things happen"（演示嘛，正常）
- 被问到答不上来的，诚实说"I haven't tested that scenario, but here's how I'd approach it..."（没测过，但我会这么处理……）
