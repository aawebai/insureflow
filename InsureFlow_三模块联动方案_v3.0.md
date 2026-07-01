# InsureFlow 三模块联动方案 v3.0

## 概述

当前三个模块（A产品配置、B核保引擎、C保单管家）各自独立运行，缺乏业务联动。本方案设计两套互补的联动方案，使 InsureFlow 从"三个Demo"升级为"一个产品"。

**核心目标**：让面试官看到一个功能完整、模块协同、有真实业务价值的 AI 保险中台。

### 两套方案对比

| 维度 | Scheme A：Hub统一智能中枢 | Scheme B：API级联自动串联 ⭐ |
|------|--------------------------|---------------------------|
| **原理** | 嵌入式 Prompt 路由，LLM 根据意图切换处理模式 | HTTP API 微服务编排，三个模块独立部署后串行调用 |
| **技术复杂度** | 中 | 高 |
| **架构模式** | Monolith（单体 Chatflow） | Microservice Orchestration（微服务编排） |
| **模块复用性** | 低（逻辑嵌入Hub，不可独立使用） | 高（每个模块独立发布，可单独调用也可编排） |
| **数据传递** | Conversation Variables（内存） | HTTP Request / Response（网络API） |
| **容错机制** | LLM 自然语言容错 | 结构化 JSON + safe_parse + 重试机制 |
| **面试加分** | 中（提示词工程、意图识别） | 高（微服务编排、API网关模式、跨服务数据传递） |
| **适用场景** | 日常用户交互、通用问答 | 演示全流程自动化、展示架构设计能力 |
| **实现文件** | `智保通-统一智能中枢.yml` | `insureflow_orchestrator.py`（Python外部编排脚本） |
| **平台限制** | ✅ Dify Cloud 可运行 | ⚠️ Dify Cloud 沙箱禁止HTTP节点出站；原YML（`智保通-全链路API自动串联.yml`）仅供架构参考 |

> **最终方案（2026-06-24 更新）**：
> - **Scheme A（Hub）**：✅ 已部署，Dify Cloud 可正常运行，用于日常演示
> - **Scheme B（API级联）**：Dify 内置 HTTP Request 节点在 Cloud 沙箱中无法出站调用（经 Debug V1→V2→V3 三级控制变量法验证确认）。改为 `insureflow_orchestrator.py` Python 脚本实现外部编排，调用各模块 Workflow API 完成全链路串联
> - **面试策略**：日常演示用 Hub；展示技术深度时，先讲 Dify HTTP 节点的排查过程（展示工程化调试能力），再展示 Python 编排脚本（展示架构设计和技术选型能力）

---

## 一、当前模块接口梳理

```
模块A: 智能产品配置助手 (Workflow)
  Input:  product_requirement (自然语言产品需求)
  Output: product_brochure_md    ← 产品说明书(Markdown)
          product_definition_json ← 产品定义(结构化JSON)
          status                  ← 草稿状态

模块B: 多Agent核保引擎 (Workflow)
  Input:  INSURE_inquiry (自然语言投保信息)
  Output: underwriting_report    ← 核保决策报告
          decision_json           ← 决策摘要(标准体/次标准体/延期体/拒保体)
          pricing_detail          ← 定价明细

模块C: 智能保单管家 (Chatflow)
  Input:  policy_inquiry (自然语言保单问题)
  Output: service_response       ← 保单服务回复
          intent_type             ← 识别的意图类型
```

**关键发现**：三个模块的输入输出都是**自然语言**和**结构化JSON**的混合，这为联动提供了统一的数据语言。

---

## 二、联动架构设计

### 2.1 总体架构

```
                        ┌──────────────────────────────────────────┐
                        │        InsureFlow Hub (新增模块D)          │
                        │        统一智能路由 + 上下文编排             │
                        │                                          │
   用户 ──→ 意图识别 ──→ 实体提取 ──→ 场景路由 ──→ 子模块调用       │
                        │     │                                    │
                        │     └─ Conversation Variables             │
                        │        (跨模块共享上下文)                  │
                        └────┬──────┬──────┬───────────────────────┘
                             │      │      │
                    ┌────────▼──┐ ┌─▼──────▼─┐ ┌────────▼──────────┐
                    │  模块A     │ │  模块B    │ │  模块C             │
                    │ 产品配置   │ │ 核保引擎   │ │ 保单管家           │
                    │ (Workflow) │ │ (Workflow) │ │ (Chatflow)         │
                    └─────┬──────┘ └─────┬──────┘ └────────┬──────────┘
                          │             │                  │
                    ┌─────▼─────────────▼──────────────────▼──────────┐
                    │              共享产品-保单知识库 (统一)           │
                    │  模块A知识库 + 模块B知识库 + 模块C知识库 + 联动桥接文档 │
                    └─────────────────────────────────────────────────┘
```

### 2.2 核心联动机制：三层串联

| 层级 | 机制 | 技术实现 | 难度 |
|:---:|------|----------|:---:|
| **L1 入口层** | 统一 Hub 智能路由 | Chatflow + 意图识别 + If-Else 分支 | 中 |
| **L2 数据层** | 跨模块标准化协议 | Conversation Variables + JSON Schema | 中高 |
| **L3 知识层** | 共享知识库桥接 | 三个知识库合并 + 联动检索策略 | 高 |

---

## 附录A：Scheme B — API级联自动串联（推荐面试主Demo）

### A.1 架构设计

Scheme B 将三个模块独立发布为 Dify API 应用，然后创建一个编排层 Workflow 通过 HTTP Request 节点串行调用。

```
┌─────────────────────────────────────────────────────────────────┐
│              智保通-全链路API自动串联 (编排层 Workflow)            │
│                                                                  │
│  Start ──→ LLM:信息提取 ──→ Code:构造A请求                        │
│                                  │                               │
│              ┌───────────────────▼─────────────────────┐         │
│              │  HTTP_A: POST /v1/workflows/run          │         │
│              │  Authorization: Bearer API_KEY_MODULE_A  │         │
│              │  Body: {product_requirement: "..."}      │         │
│              └───────────────────┬─────────────────────┘         │
│                                  │                               │
│              Code:解析A+构造B请求 ← 提取 product_brief_json       │
│                                  │                               │
│              ┌───────────────────▼─────────────────────┐         │
│              │  HTTP_B: POST /v1/workflows/run          │         │
│              │  Authorization: Bearer API_KEY_MODULE_B  │         │
│              │  Body: {INSURE_inquiry, product_context} │         │
│              └───────────────────┬─────────────────────┘         │
│                                  │                               │
│              Code:解析B+构造C请求 ← 提取 underwriting_report      │
│                                  │                               │
│              ┌───────────────────▼─────────────────────┐         │
│              │  HTTP_C: POST /v1/workflows/run          │         │
│              │  Authorization: Bearer API_KEY_MODULE_C  │         │
│              │  Body: {policy_inquiry: "..."}           │         │
│              └───────────────────┬─────────────────────┘         │
│                                  │                               │
│  LLM:报告生成 ←── Code:解析C+汇总 ← 提取 policy_response         │
│     │                                                            │
│     ▼                                                            │
│  End(full_chain_report)                                          │
└─────────────────────────────────────────────────────────────────┘
```

### A.2 技术亮点

**1. 微服务编排（Service Orchestration）**
三个模块各自独立部署、独立发布，拥有独立的 API Key。编排层不包含任何业务逻辑，只负责流程控制和数据适配。这符合微服务架构中 "Smart Endpoints, Dumb Pipes" 的原则。

**2. 跨模块数据传递（Cross-Module Data Passing）**
这是整个方案最核心的技术难点：
- 模块A输出的 `product_brief_json`（产品摘要JSON）被提取后注入模块B的 `product_context_json` 输入
- 模块B的核保结论通过产品参数进行精准评估（如：保额不超过产品定义上限、费率基于产品基准费率）
- 模块B的核保决策类型影响模块C的保单咨询方向
- 数据传递链路：`用户输入 → 产品参数 → 核保结论 → 保单服务`，全链路自动流转

**3. 结构化数据协议（Structured Data Contract）**
每个 Code 节点通过 `safe_parse` 解析 JSON 响应，提取标准化字段。即使某个模块返回异常（网络超时、模型幻觉），链路不会全面崩溃——safe_parse 返回空对象，后续模块仍能获得最佳可用数据。

**4. API Gateway 模式**
编排层的 LLM:信息提取 节点相当于 API Gateway 的 Request Transformer，Code 节点相当于 Data Adapter，HTTP 节点相当于 Service Call。整个 Workflow 本质上是 API Gateway + Service Orchestrator 的轻量级实现。

**5. 环境变量安全管理**
API 密钥通过 Dify 环境变量（secret 类型）存储，不硬编码在 Workflow 配置中。这符合 Twelve-Factor App 的配置管理原则，也是企业级应用的安全基本要求。

### A.3 部署步骤摘要

1. 将模块A、B、C分别发布为 API 应用，获取各自的 API Key
2. 导入 `智保通-全链路API自动串联.yml`
3. 配置 4 个环境变量：`DIFY_BASE_URL`、`API_KEY_MODULE_A`、`API_KEY_MODULE_B`、`API_KEY_MODULE_C`
4. 发布并测试
5. 详细操作见：`操作手册/InsureFlow_Dify实操手册_全链路API自动串联.md`

### A.4 面试叙述框架

**当面试官问"三个模块如何联动"时**：

> "我设计了两层联动方案。第一层是统一智能中枢Hub，用户在一个对话窗口就能被自动路由到对应模块。但我觉得这还不够体现架构能力，所以又设计了第二层——API级联自动串联。
>
> 我把三个模块分别发布为独立的 API 应用，每个模块有自己的 API Key 和独立的生命周期。然后创建了一个编排层 Workflow，通过 HTTP Request 节点串行调用三个模块的 Dify Workflow API。
>
> 关键的技术难点是跨模块数据传递。模块A生成产品方案后，我需要提取出结构化的产品参数——等待期、保额范围、基准费率——并注入到模块B的核保请求中。这样核保引擎就不是基于通用规则做评估，而是针对刚才生成的这个具体产品进行精准核保。比如产品定义了保额上限100万，核保时如果用户申请120万就会自动告警。
>
> 从架构角度看，这本质上是微服务编排的一种轻量级实现。编排层负责流程控制和数据适配，三个业务模块各司其职。容错方面，每个解析节点都用了防御性的 JSON 解析逻辑，保证即使某个模块返回异常，链路也不会全面崩溃。
>
> 相比直接把三个模块的功能写死在一个 Prompt 里，API 级联的架构更清晰、模块复用性更高，也更接近企业级微服务编排的实际做法。"

**当面试官问"为什么不用一个Chatflow搞定"时**：

> "确实可以用一个 Chatflow 把所有逻辑写进去（Scheme A 的 Hub 就是这么做）。但那种做法的局限是：三个模块被耦合在一起，改一个模块的 Prompt 就可能导致整个链路出问题；而且模块无法独立复用——如果其他系统只想用核保引擎，就必须把整个 Hub 都调起来。
>
> API 级联方案（Scheme B）遵循了单一职责原则。每个模块独立部署、独立迭代、独立测试。编排层只做数据适配和流程控制，不耦合业务逻辑。这在实际工程中非常重要——当团队变大、模块变多时，松耦合架构的可维护性和可扩展性优势会越来越明显。"

### A.5 与 Scheme A 的关系

两套方案互补而非替代：
- **日常使用**：Scheme A（Hub）更适合——用户随意提问，Hub 自动路由
- **Demo 演示**：Scheme B（API 级联）更适合——技术深度、架构视野、自动化程度都更强
- **面试简历**：两套方案都写上去，体现"既能做用户体验设计（Hub路由），也能做系统架构设计（API编排）"

---

## 三、L1 入口层：InsureFlow Hub 统一智能路由（Scheme A）

### 3.1 新建 Chatflow：`InsureFlow-统一智能中枢`

这是用户交互的**唯一入口**。设计为 Chatflow 模式，用 Conversation Variables 维持跨轮次上下文。

### 3.2 工作流结构（11个节点）

```
Start(user_input)
  │
  ▼
LLM_H1: 意图识别+实体提取
  │  输出: {intent, entities, confidence, previous_context}
  │
  ▼
If-Else: 场景路由
  │
  ├── intent=="product_config" ──→ 分支A: 产品配置流程
  ├── intent=="underwriting"  ──→ 分支B: 核保评估流程
  ├── intent=="policy_service"──→ 分支C: 保单服务流程
  ├── intent=="full_chain"    ──→ 分支D: 全链路串联 ⭐
  └── intent=="general"       ──→ 分支E: 通用问答
```

### 3.3 LLM_H1 意图识别提示词（核心）

```
你是一个保险业务智能路由器。分析用户输入，识别业务意图。

意图类型：
- product_config: 用户想设计/配置保险产品（如"帮我设计一款年轻人的重疾险"）
- underwriting: 用户想投保/核保（如"我30岁程序员，想买重疾险，能过核保吗"）
- policy_service: 用户的保单相关问题（如"我的保单能赔吗""怎么续保"）
- full_chain: 用户想从产品选择→核保→保单全流程体验（如"我想完整体验买保险的流程"）
- general: 闲聊或无法归类

实体提取（根据意图提取对应字段）：
- 若 intent==product_config: 提取 product_type, target_age, budget_range, special_requirements
- 若 intent==underwriting: 提取 age, gender, occupation, health_conditions, target_product_type, budget
- 若 intent==policy_service: 提取 policy_type, inquiry_type(lookup/claim/renewal), health_mention

上下文引用：
- 如果用户说"用刚才那个产品""按上次的核保结果"，结合 Conversation Variables 中的历史记录推断
- 如果用户切换意图（如从核保切到保单查询），保留已收集的用户画像信息

Conversation Variables 中已有的上下文：
{previous_product_context}
{previous_underwriting_context}
{previous_policy_context}

输出JSON格式：
{
  "intent": "product_config|underwriting|policy_service|full_chain|general",
  "confidence": 0.0-1.0,
  "entities": {...},
  "needs_clarification": true/false,
  "clarification_question": "如果需要追问的话"
}
```

### 3.4 Conversation Variables 设计（跨模块上下文存储）

```yaml
conversation_variables:
  - name: global_user_profile
    type: object
    description: 跨模块共享的用户画像
    fields:
      age: null
      gender: null
      occupation: null
      health_conditions: []
      budget_range: {min: null, max: null}

  - name: product_context
    type: object
    description: 当前会话中创建/引用的产品定义
    fields:
      product_code: null
      product_type: null
      product_name: null
      coverage_scope: null
      sum_insured_range: null

  - name: underwriting_context
    type: object
    description: 当前会话中的核保决策结果
    fields:
      decision: null
      risk_score: null
      premium_estimate: null
      decision_reason: null

  - name: policy_context
    type: object
    description: 当前会话中的保单上下文
    fields:
      policy_id: null
      policy_type: null
      effective_date: null
      last_service_intent: null

  - name: conversation_flow_stage
    type: string
    description: 当前会话所处联动阶段标记
    enum: [idle, product_created, underwriting_done, policy_active, full_chain_in_progress]
```

---

## 四、L2 数据层：跨模块标准化协议

### 4.1 设计理念

三个模块各自独立部署，通过**统一 JSON Schema** 实现数据互通。每个模块在 Start 节点增加可选的 `prefilled_context` 输入，接收上游模块的输出。

### 4.2 对各模块的改动（最小侵入）

#### 模块A 改动：增加"产品引用输出"

在 Code_A2（产品定义生成）的输出中，新增一个 `product_brief` 字段：

```json
// 新增输出：供其他模块引用的产品摘要
{
  "product_brief": {
    "product_code": "CI-2026-ABC",
    "product_type": "重疾险",
    "product_name": "面向年轻人的高性价比重疾险",
    "core_coverage": "120种重疾 + 40种轻症(30%给付/最多6次) + 20种中症(50%给付)",
    "waiting_period_days": 90,
    "sum_insured_range": {"min": 100000, "max": 1000000},
    "target_age_range": {"min": 22, "max": 35},
    "key_exclusions": ["遗传性疾病", "先天性畸形", "故意杀害", "犯罪", "自伤", "吸毒", "酒驾", "战争", "核辐射"],
    "premium_benchmark": {"age_30_male_500k": "约11,000元/年"}
  }
}
```

#### 模块B 改动：增加"产品上下文"输入

在 Start 节点增加一个**可选**输入字段 `product_context_json`：

```
Start 节点新增变量：
  product_context_json  (可选, paragraph)
  用途：传入模块A生成的产品定义，核保时自动匹配该产品的核保规则
  默认值：空（不传则使用通用核保规则）
```

在 LLM1（信息提取）的 System Prompt 中增加：

```
如果输入中包含 product_context_json：
  - 根据 product_context_json 中的 product_type 调整提取策略
  - 对于等待期为90天的重疾险产品，健康核保标准相对严格
  - 对于等待期为180天的重疾险产品，可适当放宽轻微健康异常
  - 保额范围与产品定义中的 sum_insured_range 交叉验证
```

在 Code 定价计算节点中增加产品引用逻辑：

```python
# 新增伪代码逻辑
if product_context:
    # 使用该产品的费率基准而非通用基准
    benchmark = product_context.get("premium_benchmark", {})
    # 保额不超过产品定义的上限
    max_allowed = product_context.get("sum_insured_range", {}).get("max", 500000)
    if requested_sum_insured > max_allowed:
        warnings.append(f"申请保额超过本产品上限{max_allowed}元")
```

#### 模块C 改动：增加"保单来源"上下文

在 Conversation Variables 中增加可引用的 `source_context`：

```yaml
# 模块C 新增 Conversation Variable
- name: source_context
  type: object
  description: 保单来源（从模块B核保结果自动生成）
  fields:
    source: "underwriting_result" | "manual_input" | "product_config"
    product_code: null
    underwriting_decision: null
    risk_level: null
```

当用户从模块B核保完成后自动跳转到模块C时，该变量已预填充，告知用户"基于刚才的核保结果，您的保单已生成，以下是您的保单信息..."。

### 4.3 统一数据协议 Schema

```json
// InsureFlow 跨模块通信标准协议 v1.0
{
  "$schema": "InsureFlow Inter-Module Protocol v1.0",
  "source_module": "A|B|C|Hub",
  "timestamp": "ISO8601",
  "session_id": "uuid",
  "user_profile": {
    "age": "number|null",
    "gender": "male|female|null",
    "occupation": "string|null",
    "health_conditions": ["string"]
  },
  "payload": {
    "product": { /* 来自模块A的product_brief */ },
    "underwriting": { /* 来自模块B的decision_json */ },
    "policy": { /* 来自模块C的policy_context */ }
  },
  "trace": [
    /* 记录用户在三个模块间的流转路径，实现全链路追踪 */
    {"module": "A", "action": "product_created", "timestamp": "..."},
    {"module": "B", "action": "underwriting_completed", "timestamp": "..."},
    {"module": "C", "action": "policy_serviced", "timestamp": "..."}
  ]
}
```

---

## 五、L3 知识层：共享知识库桥接

### 5.1 新建统一知识库

创建第四个知识库：`InsureFlow-统一产品保单知识库`，融合三个模块的知识库：

```
InsureFlow-统一产品保单知识库/
├── 来自模块A/
│   ├── 保险监管规定摘要.txt
│   ├── 市场热门产品参数表.txt
│   ├── 标准条款模板库.txt
│   └── 费率定价指导原则.txt
├── 来自模块B/
│   └── 核保规则知识库.md
├── 来自模块C/
│   ├── 保单条款与保障范围.txt
│   ├── 常见拒赔案例与解读.txt
│   ├── 理赔流程与材料指南.txt
│   └── 续保与保单服务规则.txt
└── 联动桥接文档 (新增)/
    ├── 产品-核保规则映射表.txt     ← 核心：将产品类型映射到对应核保规则
    ├── 核保决策-保单生成映射表.txt  ← 核保结果→保单初始状态
    └── 全链路FAQ.txt               ← 用户可能问的跨模块问题
```

### 5.2 联动桥接文档设计

**文档1：产品-核保规则映射表.txt**

```
# 产品类型 → 核保规则映射表

## 重疾险产品 → 核保规则
- 若等待期90天：健康核保相对严格，轻微异常也需评估
- 若等待期180天：健康核保可适当宽松，部分轻微异常可标准体承保
- 若含轻症豁免：核保时额外关注轻症高发风险（轻度脑中风、轻微心梗等）
- 若含多次赔付：核保时关注家族遗传病史
- 保额>100万：需额外风控审批，必须核查收入证明

## 医疗险产品 → 核保规则
- 一律需评估既往症风险
- 保证续保版：健康核保最严格（因续保无等待期）
- 需额外关注BMI和吸烟（医疗险对这两个因子敏感度高）
- 保额>400万：需核查是否有重复投保

## 定期寿险产品 → 核保规则
- 职业风险权重最高（高风险职业可能拒保或加费）
- 健康核保相对宽松（仅关注影响寿命的重大疾病）
- 高保额（>200万）必须核查收入负债比
- 吸烟因子对费率影响显著（可相差50-100%）

## 意外险产品 → 核保规则
- 健康核保最宽松（一般不查健康告知）
- 职业风险权重极大（5-6类职业可能拒保）
- 需关注是否参与高危运动/活动
- 高龄（>65岁）：保额上限降低至10万
```

**文档2：核保决策-保单生成映射表.txt**

```
# 核保决策结果 → 保单建议

## 标准体承保 → 正常保单
- 保单状态：正常承保
- 费率：标准费率 × 风险系数(1.0)
- 建议：告知用户保单生效时间、缴费日期、等待期

## 次标准体承保 → 加费保单
- 保单状态：加费承保
- 费率：标准费率 × 风险系数(1.2-2.5)
- 建议：解释加费原因，展示标准费率对比，强调保障完整

## 延期体 → 临时保单
- 保单状态：暂不承保
- 建议：告知延期原因、建议的复查时间、期间的风险提示

## 拒保体 → 替代方案
- 保单状态：拒绝承保
- 建议：推荐其他险种替代方案（如拒保重疾险 → 推荐意外险+医疗险组合）
```

**文档3：全链路FAQ.txt**

```
# 全链路常见问题

## Q1: 我在核保时被拒保了，能换一款产品吗？
→ 自动路由回模块A，根据用户画像推荐替代产品

## Q2: 核保通过后，保单什么时候生效？
→ 自动路由到模块C，读取产品定义中的等待期和生效规则

## Q3: 这个产品的某个条款我没看懂？
→ 自动路由到模块C，用模块A的产品定义条款做详细解读

## Q4: 我已有保单，想再加保额？
→ 先走模块C查现有保单 → 再走模块B做加保核保 → 最后汇总
```

---

## 六、四大联动场景设计（Demo演示用）

### 场景1：产品→核保直通 (A→B) ⭐ 最核心

```
用户: "我上个月刚设计了一款重疾险，产品代码CI-2026-ABC，
      现在有个30岁的程序员想买50万保额，帮我评估一下。"

Hub流程:
1. LLM_H1 识别 intent=underwriting, 实体中提取到 product_code=CI-2026-ABC
2. 从 product_context (Conversation Variable) 中读取产品定义
3. 将 product_context 注入模块B的 product_context_json 输入
4. 模块B基于该产品的具体参数（等待期90天、120种重疾等）执行核保
5. 输出核保报告时标注"基于产品 CI-2026-ABC 的核保规则"

技术亮点：
- 产品定义驱动核保策略（不是通用核保，而是针对特定产品的核保）
- Conversation Variable 跨分支传递上下文
- 核保规则根据产品参数动态调整
```

### 场景2：核保→保单生成 (B→C)

```
用户: "刚才的核保通过了，帮我看看我的保单情况。"

Hub流程:
1. LLM_H1 识别 intent=policy_service
2. 检测到 underwriting_context 中存在刚完成的核保结果
3. 自动构造 policy_context（从核保结果推断保单状态）
4. 注入模块C的 source_context，告知"保单来源于核保结果"
5. 模块C根据核保决策给出对应的保单解读：
   - 标准体 → 正常保单介绍
   - 次标准体 → 加费说明 + 保障范围确认
   - 拒保体 → 替代方案推荐

技术亮点：
- 核保结果自动转化为保单上下文
- 无需用户手动输入保单信息
- 不同核保决策触发不同的保单服务分支
```

### 场景3：全链路一站式体验 (A→B→C) ⭐ 面试主Demo

```
用户: "我想完整体验一遍买保险的流程，从选产品到核保到保单服务。"

Hub流程:
1. 识别 intent=full_chain
2. 阶段1 - 产品选择:
   "您好！让我们先从选择产品开始。请问您想了解哪种类型的保险？
    目前我们可以帮您：配置新产品 / 查看已有产品 / 根据需求推荐"
   
3. 阶段2 - 用户描述需求后，走模块A分支生成产品定义
   → 产品定义存入 product_context
   → Hub 自动提示："产品已生成（代码 CI-2026-XYZ），接下来帮您做核保评估"
   
4. 阶段3 - 自动进入核保流程
   → 从 product_context 读取产品参数注入模块B
   → 收集用户个人信息（年龄、职业、健康）
   → 执行核保，结果存入 underwriting_context
   → Hub 自动提示："核保完成，结果为【标准体承保】，年缴保费约11,000元。需要查看保单详情吗？"
   
5. 阶段4 - 自动进入保单服务
   → 从 underwriting_context 生成保单上下文注入模块C
   → 展示保单信息、保障范围、注意事项、续保规则

技术亮点：
- 单次会话完成全链路（产品配置→核保→保单服务）
- Conversation Variables 驱动阶段流转
- 每个阶段的条件门控（前一步必须完成才能进入下一步）
- 全程上下文追踪
```

### 场景4：智能降级 — 信息不足时的跨模块补偿

```
用户: "我想买个保险，但不太懂..."
     (信息极少，无法判断意图)

Hub流程:
1. LLM_H1 识别 intent=general, confidence=0.3, needs_clarification=true
2. 进入通用引导分支：
   "没关系！让我帮您梳理一下。
    买保险一般有三个步骤：
    ① 确定产品 - 告诉我您的年龄、预算和关注点，我帮您推荐
    ② 健康核保 - 评估您是否符合投保条件
    ③ 保单管理 - 买了之后随时咨询
    我们先从第一步开始？"
3. 引导用户逐步提供信息
4. 当信息足够时自动路由到对应模块

技术亮点：
- 模糊输入不崩溃
- 渐进式信息收集
- 智能降级引导
```

---

## 七、新增：模块D — InsureFlow Hub YML 结构

### 7.1 节点清单（共 15 个节点）

| 序号 | 节点 | 类型 | 功能 |
|:---:|------|------|------|
| 1 | Start | start | 用户输入，接收 user_input |
| 2 | LLM_H1:意图识别 | llm | 识别意图 + 提取实体 |
| 3 | Code_H1:上下文聚合 | code | 从 Conversation Variables 聚合历史上下文 |
| 4 | If-Else:场景路由 | if-else | 根据 intent 分发到5个分支 |
| 5a | LLM_A_Hub:产品配置协调 | llm | 调用模块A逻辑的适配层 |
| 5b | LLM_B_Hub:核保协调 | llm | 调用模块B逻辑的适配层 |
| 5c | LLM_C_Hub:保单服务协调 | llm | 调用模块C逻辑的适配层 |
| 5d | LLM_FullChain:全链路编排 | llm | 管理A→B→C流程 |
| 5e | LLM_General:通用引导 | llm | 信息不足时的引导 |
| 6a/6b/6c | KB:统一知识库检索 | knowledge-retrieval | 各分支独立检索（Top K=8） |
| 7 | Code_StageManager:阶段管理 | code | 更新 Conversation Variables 推进流程 |
| 8 | LLM_Response:回复生成 | llm | 统一格式化输出 |
| 9 | End | end | 输出 response + current_stage |

### 7.2 关键节点设计：Code_StageManager

```python
import json

def main(intent: str, branch_output: str, current_stage: str,
         product_context: dict, underwriting_context: dict, 
         policy_context: dict) -> dict:
    """
    管理全链路阶段流转
    - 根据当前分支输出更新对应上下文
    - 推进流程阶段
    - 返回更新后的状态
    """
    
    # 初始化
    stage = current_stage or "idle"
    updates = {}
    next_action = ""
    
    if intent == "product_config":
        # 尝试从输出中提取产品信息
        product_info = extract_product_info(branch_output)
        if product_info:
            updates["product_context"] = product_info
            stage = "product_created"
            next_action = "产品已生成。您可以直接说'帮我核保'进入核保流程。"
            
    elif intent == "underwriting":
        uw_info = extract_underwriting_info(branch_output)
        if uw_info:
            updates["underwriting_context"] = uw_info
            stage = "underwriting_done"
            next_action = "核保完成。需要查看保单详情或咨询理赔问题吗？"
            
    elif intent == "policy_service":
        policy_info = extract_policy_info(branch_output)
        if policy_info:
            updates["policy_context"] = policy_info
            if stage == "underwriting_done":
                stage = "policy_active"
                
    elif intent == "full_chain":
        # 全链路模式的状态机
        if stage == "idle" or stage == "product_created":
            next_action = "现在进入核保环节。请告诉我您的年龄、职业和健康状况。"
        elif stage == "underwriting_done":
            next_action = "核保通过！现在为您生成保单..."

    return {
        "updated_stage": stage,
        "context_updates": json.dumps(updates, ensure_ascii=False),
        "next_action_prompt": next_action
    }
```

---

## 八、实施计划

### Scheme A（Hub统一智能中枢）

| 阶段 | 内容 | 工作量 | 产出 | 状态 |
|:---:|------|:---:|------|:---:|
| **第1步** | 创建统一知识库 + 撰写3个桥接文档 | 1天 | 共享KB + 3个桥接txt | ✅ 已完成 |
| **第2步** | 在 Dify 中创建 InsureFlow Hub Workflow | 1天 | Hub YML + 截图 | ✅ 已完成 |
| **第3步** | 模块A和B各增加产品上下文输入/输出 | 0.5天 | 更新后的YML | ✅ 已完成 |
| **第4步** | 实现5种意图路由和全链路引导 | 0.5天 | 测试用例通过 | ✅ 已完成 |

### Scheme B（API级联自动串联）⭐ 推荐

| 阶段 | 内容 | 工作量 | 产出 | 状态 |
|:---:|------|:---:|------|:---:|
| **第1步** | 模块A/B/C发布为API应用，获取API Key | 0.5天 | 3个API Key | 🔲 待完成 |
| **第2步** | 导入API级联YML + 配置环境变量 | 0.5天 | 可运行的级联Workflow | 🔲 待完成 |
| **第3步** | 端到端测试（3个测试用例） | 0.5天 | 测试截图/录屏 | 🔲 待完成 |
| **第4步** | 准备面试叙述（架构对比 + 技术亮点） | 0.5天 | 面试话术 | 🔲 待完成 |

**当前进度**：Scheme A 全部完成，Scheme B 的 YML 和操作手册已就绪，待用户发布模块并配置环境变量后即可测试。

---

## 九、技术难点总结（面试加分项）

### Scheme A 技术难点

| 难点 | 描述 | 面试话术 |
|------|------|----------|
| **跨模块状态管理** | 三个独立Workflow/Chatflow之间通过Conversation Variables传递上下文，实现无状态模块间的有状态会话 | "我设计了一套跨模块的上下文协议，让三个独立部署的应用能在一次用户会话中无缝协作" |
| **知识库桥接** | 从三个独立KB到一个统一KB，并新增联动桥接文档实现智能路由 | "传统RAG是单知识库单场景，我实现了多知识库融合+桥接检索，让核保引擎能感知产品定义的变更" |
| **全链路状态机** | Code_StageManager实现状态流转，保证A→B→C的执行顺序和条件门控 | "我设计了一个轻量级状态机来管理全链路的阶段流转，确保用户不会跳步或遗漏关键信息" |
| **智能降级策略** | 用户输入信息不足时，系统不崩溃，而是渐进式引导收集信息 | "这是从模块B的safe_parse经验延伸出来的——不仅在代码层面容错，也在业务层面设计了信息不足时的引导补偿机制" |
| **统一数据协议** | 定义跨模块通信的JSON Schema标准 | "就像微服务之间的API Contract，我定义了模块间的数据协议，保证每个模块可以独立迭代而不破坏整体联动" |
| **产品定义驱动核保** | 模块B的核保规则根据模块A的产品参数动态调整 | "不是通用核保，而是针对具体产品的精准核保——这在实际保险业务中非常重要，因为不同产品的核保标准确实不同" |

### Scheme B 附加强技术难点 ⭐

| 难点 | 描述 | 面试话术 |
|------|------|----------|
| **微服务编排** | 通过 HTTP Request 节点串行调用三个独立部署的 Workflow API，编排层负责流程控制 | "我把三个模块独立发布为 API 应用，在编排层用 HTTP 节点串行调用——这本质上是微服务编排的轻量级实现，和主流的服务编排框架（如 Temporal、Conductor）思路一致" |
| **跨服务数据传递** | 模块A的产品参数（JSON）经 Code 适配后注入模块B的请求体，实现产品参数驱动的精准核保 | "产品定义里的等待期、保额上限、基准费率都会影响核保决策。我设计了一套数据适配器，让上游模块的结构化输出自动适配为下游模块的输入——这是微服务间数据契约的实际应用" |
| **API安全与配置管理** | API Key 通过环境变量 secret 类型加密存储，符合安全最佳实践 | "所有 API 密钥都通过环境变量加密存储，不硬编码在工作流配置中——这是 Twelve-Factor App 的配置分离原则" |
| **优雅降级与容错** | 每个 Code 节点使用防御性 safe_parse，模块异常不导致全链路崩溃 | "即使某个模块因为网络超时或模型幻觉返回了异常数据，safe_parse 也能保证链路不崩溃——这种防御性编程是生产级系统的基本要求" |
| **双架构对比思维** | 同时实现了嵌入式路由（Scheme A）和 API 编排（Scheme B），能够从工程角度对比两种架构的适用场景 | "我做这两个方案不是为了重复，而是想展示：同一个业务目标可以用不同的架构来实现。Scheme A 适合快速迭代，Scheme B 适合团队协作和独立部署——选哪种取决于团队规模和迭代速度" |

---

## 十、联动前后对比

| 维度 | 联动前（现状） | Scheme A（Hub） | Scheme B（API级联）⭐ |
|------|--------------|-----------------|---------------------|
| 模块关系 | 三个独立Demo，手动切换 | 统一入口，自动路由 | 独立部署，API编排调用 |
| 用户体验 | 分别打开三个应用 | 一个对话窗口完成全流程 | 一次输入，30秒输出完整报告 |
| 数据流转 | 无，每次从零开始 | 产品→核保→保单，CV传递 | 产品→核保→保单，HTTP传递 |
| 业务完整性 | 碎片化功能展示 | 完整的保险业务全链路 | 自动化端到端业务流程 |
| 技术深度 | 单一工作流设计 | 意图识别 + 知识桥接 + 状态机 | 微服务编排 + 数据适配 + API Gateway |
| 架构模式 | Monolith | Modular Monolith | Microservice Orchestration |
| HR感知 | "做了三个小工具" | "搭建了一个AI保险中台" | "设计了一套微服务编排架构" |

---

*联动方案 v3.0，基于三个模块已全部部署跑通的现状设计。*
