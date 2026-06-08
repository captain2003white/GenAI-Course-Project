# Round 2 — Multi-Source Architecture & Web Shopping Integration

**Date:** 2026-06-08
**Goal:** 从固定 2 个有限数据源升级为可扩展的多源架构，并接入实时网络购物搜索

---

## 1. Multi-Source 架构重构

### 抽象层设计

创建了 `ProductSource` 抽象基类，统一所有数据源接口：

```
ProductSource (ABC)
├── name -> str              # 唯一标识
├── enabled -> bool          # 动态开关（无 API key 自动禁用）
├── search(query, top_k)     # 关键词搜索
├── get_by_id(id)            # 单个商品查询
├── get_all()                # 全量商品
└── categories               # 分类列表
```

### ProductRegistry 聚合器

并行查询所有注册源，合并、去重、排序：

```python
registry = ProductRegistry()
registry.register(FakeStoreSource())
registry.register(DummyJSONSource())
# ...

results = await registry.search_merged("shoes")
# 并行搜索所有源 → 合并 → 按标题去重 → 按评分排序
```

### Product 模型扩展

- 新增 `source: str = "unknown"` 字段（追踪商品来源）
- 新增 `url: str = ""` 字段（网页来源商品的购买链接）
- 所有现有代码向后兼容

---

## 2. 数据源一览

| 数据源 | 商品数 | 认证 | 状态 |
|--------|--------|------|------|
| [FakeStore](backend/sources/fakestore.py) | ~20 | 无需 | ✅ 内置 |
| [DummyJSON](backend/sources/dummyjson.py) | ~194 | 无需 | ✅ 内置 |
| [Platzi](backend/sources/platzi.py) | ~47 | 无需 | ✅ 内置 |
| [Brave Shopping](backend/sources/brave_shopping.py) | 实时 | 需 BRAVE_API_KEY（信用卡） | ⏸️ 需配置 |
| [eBay](backend/sources/ebay.py) | 实时 | 需 EBAY_CLIENT_ID + SECRET | ⏸️ 需配置 |

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/sources/base.py` | ProductSource 抽象基类 |
| `backend/sources/registry.py` | ProductRegistry 聚合器 |
| `backend/sources/fakestore.py` | FakeStore 实现 |
| `backend/sources/dummyjson.py` | DummyJSON 实现（含字段映射） |
| `backend/sources/platzi.py` | Platzi API 实现（免注册） |
| `backend/sources/brave_shopping.py` | Brave Search API 实现 |
| `backend/sources/ebay.py` | eBay Browse API 实现（OAuth2） |
| `backend/sources/__init__.py` | 包入口，自动注册所有源 |

---

## 3. 核心修复

### 3.1 分类模糊匹配

**问题：** LLM 发送 `category: "clothing"` 但 FakeStore 的分类是 `"men's clothing"` 和 `"women's clothing"`，精确匹配导致 0 结果。

**修复** ([`backend/tools/search.py`](backend/tools/search.py))：

```python
if category:
    cat_lower = category.lower().strip()
    filtered = [p for p in results
                if p.category == cat_lower
                or cat_lower in p.category
                or p.category in cat_lower]
    if filtered:
        results = filtered
    # 如果过滤后为空则忽略分类（LLM 猜错了）
```

### 3.2 Langfuse Score 显示修复

**问题：** SDK v2.55.0 中 `trace.span()` 产生损坏的 observation ID，导致 UI 显示 "Observation not found"。

**修复** ([`backend/main.py`](backend/main.py))：
- 用 `trace.update(metadata=...)` 替代 `trace.span()`
- 用 `trace.score()` 替代 `langfuse.score(trace_id=...)`
- 单次 `langfuse.flush()` 替代双次 flush（保证 trace + scores 同时提交）

### 3.3 Stripe 支付恢复

**问题：** 前端重构后 Buy Now 按钮和支付弹窗丢失。

**修复** ([`frontend/index.html`](frontend/index.html))：
- 恢复 Buy Now 按钮（内联卡片 + 网格卡片）
- 恢复支付弹窗（含 Stripe 测试卡信息）
- 实现 `openStripePayment()` / `buyProductById()` 函数

---

## 4. 前端增强

| 改动 | 说明 |
|------|------|
| 智能按钮 | 网页来源商品 → "View on Site"（紫色，跳商家），目录商品 → "Buy"（绿色，走 Stripe）|
| 来源标签 | 每张商品卡显示数据来源（`fakestore` / `dummyjson` / `platzi` 等）|
| 商品详情 | 弹窗显示来源和购买链接 |
| 三栏布局 | Sidebar(260px) + Chat(flex:1) + Panel(380px) |
| Session 管理 | localStorage 持久化，创建/切换/删除 |
| Markdown 渲染 | marked.js 渲染 AI 回复 |
| 收藏/对比 | 跨 Session 收藏，最多 4 商品对比 |

---

## 5. 搜索效果对比

| 查询 | 之前（单源） | 之后（多源） |
|------|-------------|-------------|
| "find me a jacket" | 4 (FakeStore 仅 exact match) | 4 ✅（模糊匹配修复）|
| "shoes" | ❌ 0 | **9** (DummyJSON + Platzi) |
| "laptop" | ❌ 0 | **7** (FakeStore + DummyJSON + Platzi) |
| "iphone" | ❌ 0 | **5** (DummyJSON) |
| "shirt" | ❌ 0 | **5** (FakeStore + DummyJSON) |

---

## 6. 可观测性增强

Langfuse trace metadata 增加：
```json
{
  "action": "search",
  "product_count": 9,
  "sources": ["dummyjson", "platzi"],
  "source_breakdown": {"dummyjson": 4, "platzi": 5}
}
```

评估仪表盘（`/eval-dashboard`）实时显示：
- Faithfulness / Answer Relevancy 评分
- 搜索覆盖率趋势
- 最近 200 条评估记录

---

## 7. 待完成

- [ ] **eBay 审核通过后**：在 `.env` 填入 `EBAY_CLIENT_ID` 和 `EBAY_CLIENT_SECRET`
- [ ] **验证 Langfuse Score**：重启服务器，发送新消息，检查 scores 是否在 Langfuse UI 显示
- [ ] **接入更多数据源**：按需添加如 SerpAPI、Amazon Creators API 等
- [ ] **前端补充**：对比面板中展示 `url` 字段

---

## 8. 架构图

```
┌───────────── User ─────────────┐
│  Frontend (index.html)          │
│  3-panel: Sidebar + Chat + Panel│
└──────────────┬──────────────────┘
               │ POST /chat, /buy
┌──────────────▼──────────────────┐
│  FastAPI (main.py)              │
│  ├── ChatAgent (LLM intent)     │
│  ├── Evaluator (faithfulness)   │
│  ├── Langfuse (observability)   │
│  └── tools/search.py (统一入口)  │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  ProductRegistry                │
│  ├── FakeStoreSource   (20)  ✅ │
│  ├── DummyJSONSource   (194) ✅ │
│  ├── PlatziSource       (47)  ✅ │
│  ├── BraveShoppingSource  (—) ⏸️│
│  └── EbaySource           (—) ⏸️│
└─────────────────────────────────┘
```
