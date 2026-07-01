# InsureFlow 全链路API自动串联 —— Dify 实操手册

> ⚠️ **重要更新（2026-06-24）**：经三级控制变量调试（Debug V1→V2→V3）验证，Dify Cloud 沙箱环境**禁止 HTTP Request 节点发起外部 API 调用**。本文档中的 YML 方案在 Dify Cloud 上无法运行，仅供架构参考。
>
> **可运行的替代方案**：`insureflow_orchestrator.py`（Python 外部编排脚本），已实现完整的三模块 API 级联调用。详见项目根目录。
>
> **面试价值保留**：本文档记录的架构设计思路（微服务编排、跨模块数据传递、优雅降级）在面试中仍然有效，结合 Python 脚本展示即可。

## 文件说明

本文档是 InsureFlow 三模块联动方案的**高级实现手册**。通过在 Dify Workflow 中编排 HTTP API 级联调用，实现「一次输入 → 模块A产品配置 → 模块B核保引擎 → 模块C保单管家 → 完整报告」的全自动串联。

**对应文件**：`智保通-全链路API自动串联.yml`（可直接导入）

**技术方案**：Scheme B（API级联调用），相比 Scheme A（Prompt内嵌自动化）具备更高的技术复杂度，适合在面试中展示系统集成与微服务编排能力。

---

## 0. 架构概览

```
用户输入(user_profile_input)
  │
  ▼
LLM:信息结构化提取 ─── 提取用户画像+保险需求+构造产品需求描述
  │
  ▼
Code:构造模块A请求 ─── 构造 /v1/workflows/run 请求体
  │
  ▼
HTTP_A:调用产品配置助手 ─── POST → 模块A API，获得产品方案
  │
  ▼
Code:解析A+构造B请求 ─── 解析产品摘要 → 嵌入核保请求体
  │
  ▼
HTTP_B:调用多Agent核保引擎 ─── POST → 模块B API，获得核保报告
  │
  ▼
Code:解析B+构造C请求 ─── 解析核保结论 → 构造保单咨询请求体
  │
  ▼
HTTP_C:调用智能保单管家 ─── POST → 模块C API，获得保单服务指引
  │
  ▼
Code:解析C+汇总 ─── 汇总三阶段全部数据
  │
  ▼
LLM:全链路报告生成 ─── 整合为完整Markdown报告
  │
  ▼
End(full_chain_report)
```

**关键设计**：
- 每个 HTTP 节点的请求体由前一个 Code 节点动态构造
- 产品上下文从模块A提取后注入模块B（cross-module data passing）
- 核保结论从模块B提取后影响模块C的咨询方向
- 错误不中断链路：Code 节点的 safe_parse 保证优雅降级

---

## 1. 前置准备

### 1.1 将三个模块发布为 API 应用

每个模块必须单独发布，才能通过 HTTP API 调用。

**模块A — 智能产品配置助手**：
1. Dify 控制台 → 打开「智保通-智能产品配置助手」→ 发布
2. 发布后 → 左侧「API 访问」→ 查看 API 密钥
3. 复制 API 密钥，记录为 `API_KEY_MODULE_A`
4. 记录 Workflow 的输入变量名（Start 节点的变量名），应为 `product_requirement`

**模块B — 多Agent核保引擎**：
1. Dify 控制台 → 打开「智保通-多Agent核保引擎」→ 发布
2. 复制 API 密钥，记录为 `API_KEY_MODULE_B`
3. 确认输入变量名：`INSURE_inquiry` 和 `product_context_json`

**模块C — 智能保单管家**：
1. Dify 控制台 → 打开「智保通-智能保单管家」→ 发布
2. 复制 API 密钥，记录为 `API_KEY_MODULE_C`
3. 确认输入变量名，应为 `policy_inquiry`

### 1.2 确定 Dify 平台地址

| 部署方式 | DIFY_BASE_URL |
|----------|---------------|
| Dify Cloud | `https://cloud.dify.ai` |
| 自部署（默认端口） | `http://localhost:3000` |
| 自部署（Docker） | `http://你的IP:端口` |

**注意**：
- 不要以 `/` 结尾
- 如果是内网自部署，确保 Dify 服务器和运行环境网络互通
- 自部署需要 Dify 对外暴露 HTTP 端口

### 1.3 验证 API 连通性（可选但推荐）

在导入 YML 之前，可以先用 PowerShell 测试 API 是否可达：

```powershell
$body = @{
    inputs = @{ product_requirement = "配置一款少儿重疾险" }
    response_mode = "blocking"
    user = "test-user"
} | ConvertTo-Json -Compress

$response = Invoke-RestMethod -Uri "https://cloud.dify.ai/v1/workflows/run" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer 你的API_KEY_MODULE_A" } `
    -Body $body

$response.data.outputs
```

如果返回产品数据，说明连通性正常。

---

## 2. 导入 YML

### 2.1 导入

1. Dify 控制台 → 创建应用 → 导入
2. 选择 `智保通-全链路API自动串联.yml`
3. 应用名称显示为「智保通-全链路API自动串联」

### 2.2 配置环境变量

导入后，**必须先配置环境变量**，否则 HTTP 节点无法工作。

1. 进入应用 → 左侧「环境变量」
2. 配置以下 4 个变量：

| 变量名 | 值 | 类型 | 说明 |
|--------|-----|------|------|
| `DIFY_BASE_URL` | 你的 Dify 平台地址 | string | 如 `https://cloud.dify.ai` |
| `API_KEY_MODULE_A` | 模块A的API密钥 | secret | `app-xxxxxxxxxxxxx` |
| `API_KEY_MODULE_B` | 模块B的API密钥 | secret | `app-xxxxxxxxxxxxx` |
| `API_KEY_MODULE_C` | 模块C的API密钥 | secret | `app-xxxxxxxxxxxxx` |

**重要**：类型为 `secret` 的变量保存后会加密存储，无法再次查看。请确保密钥正确后再保存。

### 2.3 检查 HTTP 节点 URL

三个 HTTP 节点的 URL 均为：`{{#env.DIFY_BASE_URL#}}/v1/workflows/run`

无需手动修改，只要环境变量配置正确即可。

### 2.4 发布

环境变量配置完成后，点击「发布」使应用生效。

---

## 3. 节点配置详解

### 节点 1：Start — 用户输入

| 配置项 | 值 |
|--------|-----|
| 变量名 | `user_profile_input` |
| 类型 | paragraph |
| 最大长度 | 2000 |
| 必填 | 是 |

**输入格式建议**（占位符已内置）：

```
【个人信息】
- 年龄、性别
- 职业
- 健康状况（高血压/糖尿病/脂肪肝/甲状腺结节/吸烟/BMI等，如实描述）

【保险需求】
- 想买的险种（重疾险/医疗险/定期寿险/意外险）
- 期望保额（如50万）
- 预算范围（如年缴1万以内）
- 特别偏好（如轻症豁免/多次赔付/月缴等）
```

---

### 节点 2：LLM:信息结构化提取

| 配置项 | 值 |
|--------|-----|
| 模型 | deepseek-v4-pro |
| Temperature | 0.3 |
| 结构化输出 | **开启** |
| 重试 | 开启，最多3次 |

**功能**：从自然语言中提取结构化 JSON，包含：
- `user_profile`：年龄、性别、职业、健康状况、吸烟、BMI
- `insurance_request`：目标险种、期望保额、预算、偏好、缴费方式
- `product_requirement_text`：构造给模块A的产品需求描述

**Assistant Prefill**：
```json
{
  "user_profile":
```

---

### 节点 3：Code:构造模块A请求

**输入变量**：
| 变量名 | 来源 |
|--------|------|
| `llm_output` | LLM:信息结构化提取 → text |

**输出变量**：
| 变量名 | 类型 | 说明 |
|--------|------|------|
| `request_body_a` | string | 模块A的完整请求体JSON |
| `user_profile_json` | string | 用户画像JSON |
| `insurance_request_json` | string | 保险需求JSON |
| `insure_inquiry` | string | 构造的投保咨询文本 |

**核心逻辑**：
1. safe_parse LLM输出的JSON
2. 提取 user_profile、insurance_request、product_requirement_text
3. 构造模块A请求体：`{"inputs": {"product_requirement": "..."}, "response_mode": "blocking", "user": "insureflow-auto"}`
4. 构造模块B的投保描述文本（insure_inquiry）

---

### 节点 4：HTTP_A:调用产品配置助手

| 配置项 | 值 |
|--------|-----|
| 方法 | POST |
| URL | `{{#env.DIFY_BASE_URL#}}/v1/workflows/run` |
| 认证 | Bearer → `{{#env.API_KEY_MODULE_A#}}` |
| Body类型 | JSON |
| Body内容 | `{{#1793000000003.request_body_a#}}` |
| Headers | `Content-Type: application/json` |
| 超时(connect) | 10s |
| 超时(read) | 60s |
| 重试 | 开启，最多2次 |

---

### 节点 5：Code:解析A+构造B请求

**输入变量**：
| 变量名 | 来源 |
|--------|------|
| `http_response_body` | HTTP_A → body |
| `insure_inquiry` | Code:构造模块A请求 → insure_inquiry |
| `user_profile_json` | Code:构造模块A请求 → user_profile_json |
| `insurance_request_json` | Code:构造模块A请求 → insurance_request_json |

**输出变量**：
| 变量名 | 类型 | 说明 |
|--------|------|------|
| `request_body_b` | string | 模块B的完整请求体JSON |
| `product_brief_json` | string | 产品摘要JSON |
| `product_brochure_md` | string | 产品说明书Markdown |
| `user_profile_json` | string | 透传 |
| `insurance_request_json` | string | 透传 |

**核心逻辑**：
1. 解析 Dify API 响应：`resp["data"]["outputs"]`
2. 提取 `product_brief_json`（产品摘要）和 `product_brochure_md`（产品说明书）
3. 将产品摘要注入模块B请求体：`"product_context_json": product_brief_json`
4. 构造模块B请求体

---

### 节点 6：HTTP_B:调用多Agent核保引擎

| 配置项 | 值 |
|--------|-----|
| 方法 | POST |
| URL | `{{#env.DIFY_BASE_URL#}}/v1/workflows/run` |
| 认证 | Bearer → `{{#env.API_KEY_MODULE_B#}}` |
| Body内容 | `{{#1793000000005.request_body_b#}}` |
| 超时(read) | 60s |

---

### 节点 7：Code:解析B+构造C请求

**输入变量**：
| 变量名 | 来源 |
|--------|------|
| `http_response_body` | HTTP_B → body |
| `product_brief_json` | Code:解析A+构造B请求 → product_brief_json |
| `product_brochure_md` | Code:解析A+构造B请求 → product_brochure_md |
| `user_profile_json` | Code:解析A+构造B请求 → user_profile_json |
| `insurance_request_json` | Code:解析A+构造B请求 → insurance_request_json |

**输出变量**：
| 变量名 | 类型 | 说明 |
|--------|------|------|
| `request_body_c` | string | 模块C的完整请求体JSON |
| `uw_report` | string | 核保报告 |
| `product_brief_json` | string | 透传 |
| `product_brochure_md` | string | 透传 |
| `user_profile_json` | string | 透传 |
| `insurance_request_json` | string | 透传 |

**核心逻辑**：
1. 解析模块B响应，提取核保报告（兼容多个可能的字段名）
2. 基于产品类型构造保单咨询语句
3. 构造模块C请求体

---

### 节点 8：HTTP_C:调用智能保单管家

| 配置项 | 值 |
|--------|-----|
| 方法 | POST |
| URL | `{{#env.DIFY_BASE_URL#}}/v1/workflows/run` |
| 认证 | Bearer → `{{#env.API_KEY_MODULE_C#}}` |
| Body内容 | `{{#1793000000007.request_body_c#}}` |
| 超时(read) | 60s |

---

### 节点 9：Code:解析C+汇总

**输入变量**：
| 变量名 | 来源 |
|--------|------|
| `http_response_body` | HTTP_C → body |
| `uw_report` | Code:解析B+构造C请求 → uw_report |
| `product_brief_json` | Code:解析B+构造C请求 → product_brief_json |
| `product_brochure_md` | Code:解析B+构造C请求 → product_brochure_md |
| `user_profile_json` | Code:解析B+构造C请求 → user_profile_json |
| `insurance_request_json` | Code:解析B+构造C请求 → insurance_request_json |

**输出**：汇总全部三阶段数据，透传给报告生成节点。

---

### 节点 10：LLM:全链路报告生成

| 配置项 | 值 |
|--------|-----|
| 模型 | deepseek-v4-pro |
| Temperature | 0.7 |
| 上下文 | 不配置（数据通过变量传入） |

**System Prompt** 包含完整报告模板：
- 执行摘要（3-5句话）
- 阶段一：产品配置（嵌入 product_brochure_md）
- 阶段二：智能核保（嵌入 uw_report）
- 阶段三：保单服务（嵌入 policy_response）
- 全链路概览表格

---

### 节点 11：End

| 输出变量 | 来源 |
|----------|------|
| `full_chain_report` | LLM:全链路报告生成 → text |

---

## 4. 测试用例

### 测试 1：完整全链路（标准案例）

```
输入：我30岁，程序员，轻度脂肪肝，想买50万重疾险，预算1万以内，希望有轻症豁免和多次赔付

预期：
- 阶段一输出：重疾险产品方案（含等待期、免责条款、费率参考）
- 阶段二输出：核保结论（预计标准体或轻度加费）+ 产品参数化核保（因为A已生成产品）
- 阶段三输出：保单解读（保障范围、理赔流程、续保规则）
- 报告末尾：三阶段状态表
```

### 测试 2：高风险职业案例

```
输入：我45岁，出租车司机，吸烟，想买100万意外险，经常开夜班车

预期：
- 阶段一：意外险产品方案（高危职业，费率偏高）
- 阶段二：核保可能为次标准体加费或拒保体 → 推荐替代方案
- 阶段三：即使核保结果不理想，保单服务仍给出指引
```

### 测试 3：另一个险种

```
输入：我28岁，教师，身体健康，想买30万定期寿险保障家人

预期：
- 阶段一：定期寿险产品方案
- 阶段二：标准体核保
- 阶段三：保单解读
```

---

## 5. 调试与排查

### 5.1 如果某个 HTTP 节点返回错误

1. 检查对应模块的 API 密钥是否正确
2. 检查模块是否已「发布」（Dify中应用状态为"已发布"）
3. 检查 DIFY_BASE_URL 是否可被访问
4. 在 Code:解析节点输出中查看原始响应（通过 Dify 的「日志」功能）

### 5.2 如果报告某阶段为空

常见原因是响应字段名不匹配。当前 Code 节点兼容了多种字段名：
- 核保报告：`text` / `result` / `OUTPUT`
- 保单响应：`text` / `response` / `answer`

如果仍为空，检查对应模块 End 节点的实际输出变量名，更新 Code 节点的字段兼容列表。

### 5.3 如果产品上下文未传递到模块B

检查模块B的 Code:定价计算 节点是否正确接收 `product_context_json` 变量。确认模块B已更新为包含 product_brief 输出的版本。

### 5.4 查看每阶段具体输出

在 Dify「日志」中：
1. 找到本次运行的日志
2. 展开每个 Code 节点的输出
3. 查看 `product_brochure_md`、`uw_report`、`policy_response` 的实际内容

---

## 6. 关键配置检查清单

| 序号 | 检查项 | 正确配置 |
|:---:|--------|----------|
| 1 | 模块A已发布 | 应用状态"已发布"，API密钥已获取 |
| 2 | 模块B已发布 | 应用状态"已发布"，API密钥已获取 |
| 3 | 模块C已发布 | 应用状态"已发布"，API密钥已获取 |
| 4 | DIFY_BASE_URL | 正确且不加 `/` 结尾 |
| 5 | 3个API密钥 | 正确粘贴且类型为 secret |
| 6 | HTTP节点超时 | read ≥ 60s（核保模块耗时较长） |
| 7 | 模块B包含 product_context_json 输入 | 确认YML已更新 |
| 8 | 模块A End节点包含 product_brief_json | 确认YML已更新 |

---

## 7. 面试叙述指南

### 技术亮点（面试中可以强调）

1. **微服务编排**：三个独立模块通过 HTTP API 实现松耦合，每个模块独立部署、独立迭代，编排层负责数据串联。

2. **跨模块数据传递**：模块A输出的产品参数（等待期、费率、保额上限）自动注入模块B的核保定价，使得核保不再基于通用规则，而是针对具体产品进行精准评估——这是真正的 product-aware underwriting。

3. **优雅降级设计**：每个 Code 节点使用 safe_parse，即使某个模块返回异常（网络超时、模型幻觉输出非JSON），链路也不会全面崩溃，后续模块仍能获得最佳可用数据。

4. **API Gateway 模式**：LLM 结构化提取作为请求预处理，Code 节点作为数据适配器（Adapter），HTTP 节点作为服务调用——整个 Workflow 本质上是 API Gateway + Service Orchestrator。

5. **环境变量安全管理**：API 密钥通过 Dify 环境变量（secret类型）存储，不硬编码在工作流中，符合安全最佳实践。

### 面试回答模板

> **面试官**：你做的这个项目，三个模块是怎么联动的？

> **回答思路**：
>
> 我设计了两层联动方案。表层是统一智能中枢（Hub），用户可以在Hub中任意提问，由意图识别自动路由到对应的处理模式，这解决了用户不知道怎么选模块的问题。
>
> 深层是全链路API自动串联，这是一个更偏技术架构的方案。我把三个模块分别发布为独立的 API 应用，然后创建了一个编排层 Workflow。这个编排层通过 HTTP Request 节点串行调用三个模块的 Workflow API——先调用产品配置生成产品方案，把产品参数提取出来注入核保引擎的请求中，使核保定价能基于具体产品参数进行计算，最后把核保结论传递给保单服务模块。
>
> 技术上，这本质上是微服务编排的一种轻量级实现。每个模块独立部署、独立迭代，编排层负责数据适配和流程控制。中间使用了结构化输出（JSON Schema）来保证模块间数据的准确传递，每个节点都有防御性的 JSON 解析逻辑来保证链路稳定性。
>
> 对比直接用 Prompt 把三个模块功能写进一个 Workflow（Scheme A），API 级联（Scheme B）的优势是模块复用性更高、架构更清晰，也更接近企业级微服务编排的思路。

---

*本手册对应文件：`智保通-全链路API自动串联.yml`，可直接导入 Dify。*
