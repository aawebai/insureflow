# InsureFlow 模块A：智能产品配置助手 —— Dify 实操手册

## 文件说明
本文档对应设计方案 v2.0 中的 **P1 模块：智能产品配置助手（Product Factory）**。  
按步骤操作即可在 Dify 工作流中搭建完整可运行的产品配置引擎。

**与模块B的差异**：本模块是 Workflow（非 Chatflow），因为产品配置是多步骤处理流程而非多轮对话。

最可能出错的3个配置
  1. 查询构造器的输出变量名必须与 KB 检索节点的查询变量选择器一致
  2. LLM_A2 和 LLM_A3 的上下文必须配置为 KB:产品知识库 的输出（否则看不到检索结果）
  3. Code_A2 需要同时接收 params_json、compliance_json、user_data 三个变量

---

## 0. 前置准备：创建产品知识库

### 步骤 0.1：在 Dify 中创建知识库
1. 进入 Dify 控制台 → 顶部导航「知识库」→ 「创建知识库」
2. 知识库名称：`产品条款与监管规则库`
3. 上传以下文档（需提前准备，见步骤 0.3）：
   - `保险监管规定摘要.txt`（各险种监管核心条款）
   - `市场热门产品参数表.txt`（主流产品对比数据）
   - `标准条款模板库.txt`（等待期/免责/宽限期等模板）
   - `费率定价指导原则.txt`（各险种费率框架）
4. 分段设置：
   - 分段方式：自动分段与清洗
   - 分段最大长度：500 tokens
   - 重叠长度：50 tokens
5. 索引方式：高质量（Embedding）
6. 完成后记录知识库 ID

### 步骤 0.2：确认 Embedding 与重排序模型
- Embedding：推荐 `text-embedding-3-large`
- 重排序：`qwen3-rerank`（tongyi 供应商）或 `bge-reranker-v2-m3`
- 在 Dify 设置 → 模型供应商中确认已配置

### 步骤 0.3：知识库文档内容大纲

**文档1：保险监管规定摘要**
```
# 保险产品监管规定摘要

## 重疾险监管要点
- 等待期最低要求：90天（银保监会规定）
- 必须包含的28种重大疾病（2020版重疾定义）
- 轻症给付比例上限：基本保额的30%
- 不得将"确诊即赔"作为营销口号（需符合疾病定义标准）

## 医疗险监管要点
- 保证续保条款要求（短期医疗险不得含"保证续保"字样，长期医疗险需明确续保条件）
- 免赔额必须在条款中明示，不得隐性设置
- 费用补偿原则：不得通过多份医疗险获利

## 定期寿险监管要点
- 自杀免责期：合同成立2年内自杀不赔
- 等待期最低0天（无强制等待期要求）
- 必须明确全残定义和给付标准

## 意外险监管要点
- 意外定义四要素：外来的、突发的、非本意的、非疾病的
- 高危运动免责须在条款中明确列明
- 职业变更通知义务

## 通用合规要求
- 保险利益原则：投保人对被保险人必须有保险利益
- 如实告知义务：投保人须如实告知，保险人须明确询问
- 犹豫期：长期险≥15天，短期险通常3-7天
- 免责条款必须显著提示（加粗/加底色），否则不生效
```

**文档2：市场热门产品参数表**
```
# 市场热门保险产品参数参考

## 重疾险产品
### 平安-盛世福2025
- 投保年龄：0-55岁
- 保障期限：终身
- 重疾种类：120种
- 轻症种类：40种（每次30%保额，最多6次）
- 中症种类：20种（每次50%保额，最多2次）
- 等待期：90天
- 缴费期：趸交/10年/15年/20年/30年
- 特色：60岁前首次重疾额外给付50%保额
- 价格参考：30岁男/50万/20年缴 ≈ 12,000元/年

### 国寿-康宁2025
- 投保年龄：0-60岁
- 保障期限：终身
- 重疾种类：130种
- 轻症种类：35种（每次20%保额）
- 等待期：180天
- 缴费期：趸交/10年/20年
- 特色：含身故返还保费
- 价格参考：30岁男/50万/20年缴 ≈ 10,500元/年

### 泰康-乐享健康2025
- 投保年龄：0-50岁
- 保障期限：至70岁/终身
- 重疾种类：110种
- 轻症种类：50种（每次25%保额）
- 等待期：90天
- 缴费期：趸交/5年/10年/20年
- 特色：含轻症豁免、运动达标增加保额
- 价格参考：30岁男/50万/20年缴 ≈ 9,800元/年

## 医疗险产品
### 众安-尊享e生2025
- 投保年龄：0-60岁
- 保障期限：1年（保证续保6年）
- 一般医疗保额：300万
- 重疾医疗保额：600万
- 免赔额：一般医疗1万，重疾0免赔
- 特色：含质子重离子、外购药报销
- 价格参考：30岁 ≈ 400元/年

## 定期寿险产品
### 华贵-大麦2025
- 投保年龄：18-60岁
- 保障期限：10/20/30年/至60/65/70岁
- 等待期：90天
- 免责条款：3条（最少）
- 价格参考：30岁男/100万/30年缴 ≈ 1,200元/年
```

**文档3：标准条款模板库**
```
# 保险标准条款模板

## 等待期条款模板
> 自本合同生效日零时起90日内（含第90日），被保险人因非意外伤害原因发生保险事故的，本公司不承担保险责任，并无息退还所交保险费，本合同终止。
> 因意外伤害导致保险事故的，不受上述等待期限制。

## 免责条款（通用）模板
> 因下列情形之一导致被保险人发生保险事故的，本公司不承担保险责任：
> 1. 投保人对被保险人的故意杀害、故意伤害；
> 2. 被保险人故意犯罪或者抗拒依法采取的刑事强制措施；
> 3. 被保险人故意自伤、自杀（被保险人自杀时为无民事行为能力人的除外）；
> 4. 被保险人主动吸食或注射毒品；
> 5. 被保险人酒后驾驶、无合法有效驾驶证驾驶机动车；
> 6. 战争、军事冲突、暴乱或者武装叛乱；
> 7. 核爆炸、核辐射或者核污染。

## 宽限期条款模板
> 分期交纳保险费的，自保险费应交日的次日零时起60日为宽限期。宽限期内发生保险事故的，本公司承担保险责任，但在给付保险金时将扣除欠交的保险费。宽限期届满仍未交纳保险费的，本合同效力中止。

## 复效条款模板
> 本合同效力中止后2年内，投保人可以申请恢复合同效力。经本公司与投保人协商并达成协议，在投保人补交保险费及相应利息后，本合同效力恢复。自合同效力中止之日起满2年双方未达成协议的，本公司有权解除合同。

## 轻症豁免条款模板
> 被保险人于等待期后经医院确诊初次罹患本合同定义的轻症疾病，本公司豁免自确诊之日起本合同剩余各期应交保险费，本公司将继续承担保险责任。

## 多次赔付条款模板
> 被保险人于等待期后经医院确诊初次罹患本合同定义的重症疾病，本公司按基本保额给付首次重症疾病保险金，该重症疾病所属组别的保险责任终止。自首次重症疾病确诊之日起365日后，被保险人经医院确诊初次罹患其他组别的重症疾病，本公司再次按基本保额给付重症疾病保险金。
```

**文档4：费率定价指导原则**
```
# 保险产品费率定价指导原则

## 重疾险定价因子权重
- 年龄：权重约40%（年龄越大费率越高，指数型增长）
- 性别：权重约5%（女性略低于男性，因寿命更长但重疾发生率差异不大）
- 保障期限：权重约15%（终身 > 定期）
- 病种数量：权重约10%（每增加10种重疾，费率上浮约3-5%）
- 多次赔付：权重约10%（每增加一次赔付，费率上浮约15-20%）
- 轻症/中症覆盖：权重约8%
- 豁免条款：权重约5%
- 等待期长短：权重约3%（90天等期待vs180天等待期，费率差异约2-3%）
- 渠道费用：权重约5%

## 各险种费率区间参考（元/年/10万保额，30岁男性标准体）
- 重疾险：800-1800（定期）/ 1200-2800（终身）
- 医疗险：300-800
- 定期寿险：100-300（至60岁）
- 意外险：100-200

## 定价上下限约束
- 重疾险：不低于精算下限的90%，不高于市场同类产品均价的130%
- 医疗险：续保涨幅不超过30%/年
- 不得低于成本定价（偿付能力监管要求）
- 费率表中性别差异不得超过30%

## 预定利率参考
- 普通型人身险预定利率上限：3.0%（2025年标准）
- 分红型：2.5%
- 万能型：保底利率上限2.0%
```

---

## 1. 创建工作流

### 步骤 1.1
1. Dify 控制台 → 「创建应用」→ 选择「工作流」
2. 名称：`智保通-智能产品配置助手`
3. 描述：`基于AI的保险产品智能配置工作流——自然语言输入产品需求，自动生成产品定义JSON和产品说明书`

---

## 2. 节点配置（共 8 个节点，按顺序配置）

### 工作流全局结构
```
Start → LLM_A1:需求解析 → Code_A1:查询构造 → KB:产品知识库 → LLM_A2:参数推导 ↘
                                                         → LLM_A3:合规检查 → Code_A2:产品定义生成 → LLM_A4:产品说明 → End
```

---

### 节点 1：Start（用户输入）

| 配置项 | 值 |
|--------|-----|
| 类型 | 开始（start） |
| 节点名 | `用户输入` |
| 输入变量 | 变量名 `product_requirement`，类型 `paragraph`，必填 |
| 标签 | `产品需求描述` |
| 最大长度 | 2000 |

**变量引用名**：`{{#start.product_requirement#}}`

**输入引导提示**（填在 placeholder）：
```
请描述你想配置的保险产品，例如：
"我想配置一款面向年轻人的重疾险，保额10-100万，覆盖120种重疾含轻症豁免，支持月缴，目标客群22-35岁，价格要有竞争力"
```

---

### 节点 2：LLM_A1 - 需求解析

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM_A1:需求解析` |
| 模型 | deepseek-v4-pro |
| 上下文 | **不配置**（此节点不需要知识库上下文） |

#### 提示词配置

**System Prompt**：
```
你是一个保险产品需求分析师。从用户自然语言描述中提取产品配置要素。

提取字段及规则：
- product_type: 重疾险/医疗险/定期寿险/意外险/年金险/两全险，根据描述推断最匹配的险种
- product_concept: 用一句话概括产品定位，如"面向年轻人的高性价比重疾险"
- target_age_range: {min, max}，未提及填null，如"年轻人"可推断为{min:18, max:40}
- target_income_range: {min, max, unit:"万"}，如"中产"可推断{min:15, max:50, unit:"万"}，未提及填null
- target_occupations: 职业类别或行业列表，如["互联网","金融"]，未提及填null
- coverage_scope: 保障责任详细清单（如"120种重疾""轻症30%给付/最多6次""身故返还保费"）
- sum_insured_range: {min, max, step}，保留数字+单位，如{min:"10万", max:"100万", step:"10万"}
- payment_period_options: 可选缴费期列表，如["趸交","10年","20年","30年"]
- payment_frequency: 可选缴费频率，如["月缴","年缴"]
- special_clauses: 特色条款列表，如["轻症豁免","重症多次赔付","身故返还","运动达标增保额"]
- waiting_period_days: 等待期天数，如90或180，未提及填null（不编造）
- competitor_reference: 用户提到的参考产品名称或"想比XX更便宜"，未提及填null
- regulatory_region: 销售区域，默认"中国大陆"
- target_premium_range: {min, max, unit:"元/年"}，如"价格要有竞争力"可尝试推断，未提及填null

输出必须是合法JSON，不包含任何其他文字。未提及字段填null，不要编造数值。
```

**User Prompt**：
```
请从以下产品需求描述中提取配置要素：

用户输入：{{#start.product_requirement#}}
```

**Assistant Prefill**：
```json
{
  "product_type":
```

#### 关键设置
| 设置项 | 值 |
|--------|-----|
| 结构化输出 | **开启**（structured_output_enabled: true） |
| 重试 | 开启，最大3次，间隔1000ms |
| Temperature | **0.3**（产品配置需要高一致性，比核保模块的0.7更低） |
| 记忆 | **不开启** |

#### 输入变量
| 变量 | 来源 |
|------|------|
| `{{#start.product_requirement#}}` | 用户输入的产品需求描述 |

---

### 节点 3：Code_A1 - 查询构造器

| 配置项 | 值 |
|--------|-----|
| 类型 | Code（Python3） |
| 节点名 | `Code_A1:查询构造` |
| 上下文 | **不配置** |

#### 输入变量
| 变量名 | 来源节点 | 来源字段 |
|--------|----------|----------|
| `requirement_json` | `LLM_A1:需求解析` | `text` |

#### 代码内容
```python
import json
import re

def main(requirement_json: str) -> dict:
    """
    从需求解析JSON中构造精准的产品知识库查询语句
    生成3条独立查询：监管合规、竞品参考、条款模板
    """
    # 安全解析
    if isinstance(requirement_json, str):
        requirement_json = re.sub(r"<think>.*?</think>", "", requirement_json, flags=re.DOTALL).strip()
        try:
            data = json.loads(requirement_json)
        except:
            data = {}
    else:
        data = requirement_json if isinstance(requirement_json, dict) else {}
    
    product_type = data.get("product_type", "")
    special_clauses = data.get("special_clauses", [])
    target_age = data.get("target_age_range", {})
    regulatory_region = data.get("regulatory_region", "中国大陆")
    competitor_ref = data.get("competitor_reference", "")
    
    # 查询1：监管要求与合规边界
    query1_parts = []
    if product_type:
        query1_parts.append(f"{product_type}监管规定")
    if regulatory_region:
        query1_parts.append(f"{regulatory_region}适用规则")
    query1_parts.append("合规要求")
    query1_parts.append("等待期要求 免责条款规定 轻症给付上限")
    search_query_1 = "；".join(query1_parts)
    
    # 查询2：同类产品参考
    query2_parts = []
    if product_type:
        query2_parts.append(f"{product_type}市场产品参数对比")
    if target_age:
        min_age = target_age.get("min", "")
        max_age = target_age.get("max", "")
        if min_age or max_age:
            query2_parts.append(f"投保年龄{min_age}-{max_age}岁")
    if competitor_ref:
        query2_parts.append(f"竞品参考：{competitor_ref}")
    query2_parts.append("价格区间 保障责任 特色条款")
    search_query_2 = "；".join(query2_parts)
    
    # 查询3：条款模板
    query3_parts = ["标准条款模板"]
    if product_type:
        query3_parts.append(f"{product_type}条款范例")
    if special_clauses and isinstance(special_clauses, list):
        for clause in special_clauses:
            query3_parts.append(f"{clause}条款模板")
    query3_parts.append("免责条款 宽限期 复效条款 等待期条款")
    search_query_3 = "；".join(query3_parts)
    
    # 合并查询（Dify KB节点用分号拼接做一次检索）
    combined_query = f"{search_query_1}；{search_query_2}；{search_query_3}"
    
    return {
        "search_query": combined_query,
        "query_breakdown": {
            "regulatory": search_query_1,
            "competitor": search_query_2,
            "template": search_query_3
        },
        "user_data": data
    }
```

#### 输出变量
| 输出 | 说明 |
|------|------|
| `result` | 包含 `search_query`（检索用）、`query_breakdown`（调试用）、`user_data`（原始需求数据） |

#### 关键设置
| 设置项 | 值 |
|--------|-----|
| 重试 | 开启，最大3次，间隔1000ms |

---

### 节点 4：KB - 产品知识库检索

| 配置项 | 值 |
|--------|-----|
| 类型 | 知识检索（knowledge-retrieval） |
| 节点名 | `KB:产品知识库` |
| 知识库 | 选择第0步创建的「产品条款与监管规则库」 |

#### 检索设置
| 设置项 | 值 |
|--------|-----|
| 检索模式 | 混合检索（multiple） |
| Top K | **6**（覆盖监管、竞品、模板三类信息） |
| 重排序 | **开启** |
| 重排序模型 | qwen3-rerank |
| 权重设置 | 向量权重 0.7，关键词权重 0.3 |

#### 查询变量（核心！）
| 变量 | 来源 |
|------|------|
| 查询文本 | `Code_A1:查询构造` → `result` → `search_query` |

> 与模块B一样的模式：不用原始用户输入，而是用代码节点构造精准查询。

#### 输入变量（上下文变量）
| 变量名 | 来源节点 | 来源字段 | 用途 |
|--------|----------|----------|------|
| `user_data` | `Code_A1:查询构造` | `result.user_data` | 传递给下游节点使用 |

---

### 节点 5：LLM_A2 - 参数推导

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM_A2:参数推导` |
| 模型 | deepseek-v4-pro |
| 上下文 | **配置为「KB:产品知识库」的输出**（`{{#context#}}`） |
| Temperature | **0.3**（产品参数需要精确一致） |

#### 提示词配置

**System Prompt**：
```
你是一个保险产品精算师。你的任务是根据用户需求和知识库检索到的市场/监管信息，推导出完整的产品参数。

推导规则：

1. 等待期（waiting_period_days）：
   - 重疾险默认90天（监管最低要求），若竞品多用180天且用户强调"低价"可用180天
   - 医疗险默认30天
   - 定期寿险默认90天
   - 意外险默认0天（无等待期）

2. 免责条款（exclusions）：
   - 必须包含7条法定免责（故意杀害、犯罪、自伤、吸毒、酒驾、战争、核辐射）
   - 重疾险额外加：遗传性疾病免责、先天性畸形免责
   - 意外险额外加：高危运动免责（除非明确覆盖）
   - 如果知识库有参考模板，优先使用模板表述

3. 费率框架（premium_framework）：
   - 参考知识库中同类产品的费率区间
   - 年轻客群（<35岁）：定位在同类产品费率的下三分之一区间（"有竞争力"）
   - 中年客群（35-55岁）：定位在市场平均费率
   - 费率需包含性别差异（女性略低于男性，但差距不超过10%）

4. 缴费方案（payment_config）：
   - 如果用户提到"月缴"需求：支持月缴/季缴/半年缴/年缴
   - 缴费期选项：年轻客群最大30年、中年客群最大20年
   - 短期险（医疗险）仅支持年缴

5. 保额限制（sum_insured_constraints）：
   - 重疾险：最低10万，最高500万（500万以上需风控）
   - 医疗险：一般医疗100-600万，重疾医疗200-800万
   - 定期寿险：最低10万，最高根据年龄和收入限制（年收入×20倍为上限）
   - 意外险：最低5万，最高500万

6. 保障期限（coverage_term）：
   - 重疾险：定期（至70岁/80岁）或终身
   - 医疗险：1年（保证续保期根据监管要求设置）
   - 定期寿险：10/20/30年，或至60/65/70岁
   - 意外险：1年

优先使用知识库中的具体数据和模板。若知识库无精确参考，按上述规则推导。

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```
请根据以下信息推导产品参数：

用户需求：{{#Code_A1:查询构造.result.user_data#}}

知识库检索到的市场与监管信息：
{{#context#}}

请输出完整的产品参数推导结果。
```

**Assistant Prefill**：
```json
{
  "waiting_period_days":
```

#### 上下文配置（关键！）
| 配置项 | 值 |
|--------|-----|
| 上下文来源 | `KB:产品知识库` 节点 |
| 引用方式 | `{{#context#}}` |

---

### 节点 6：LLM_A3 - 合规检查（与节点5并行）

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM_A3:合规检查` |
| 模型 | deepseek-v4-pro |
| 上下文 | **配置为「KB:产品知识库」的输出**（`{{#context#}}`） |
| Temperature | **0.3**（合规判断需要严谨） |

#### 提示词配置

**System Prompt**：
```
你是一个保险产品合规审查员。你的唯一任务是根据知识库中的监管规则，检查用户需求是否存在合规风险。

检查维度：

1. 等待期合规性：
   - 重疾险等待期不得低于90天
   - 医疗险等待期不得低于30天（续保无等待期除外）
   - 不得设置"变相等待期"（如首年仅给付一定比例）

2. 免责条款合规性：
   - 7条法定免责是否完整包含
   - 免责条款是否显著提示（用❗标记缺少显著提示的风险）
   - 不得设置超出法定范围的歧视性免责

3. 费率合规性：
   - 性别差异不得超过30%（检查原则：如女/男费率比 < 0.7 则为不合规）
   - 高龄加费不得超过精算合理范围（原则上65岁以上不超过标准体的3倍）
   - 不得设置"保费自动上涨"陷阱条款

4. 条款表述合规性：
   - 不得使用"确诊即赔"（重大疾病需符合定义标准才赔）
   - 不得使用"保证续保"于短期医疗险（监管禁止）
   - 保障范围描述不得误导性扩大

5. 销售合规性：
   - 产品名称不得含"国家""政府""监管"等误导性词汇
   - 不得以"免费""赠送"为噱头（保险不得作为赠品）

6. 保险利益合规性：
   - 投保人与被保险人必须存在保险利益关系
   - 为他人投保需取得被保险人同意

输出JSON格式：
{
  "compliance_status": "pass" | "warning" | "fail",
  "issues": [
    {
      "severity": "critical" | "warning",
      "category": "等待期" | "免责条款" | "费率" | "条款表述" | "销售合规" | "保险利益",
      "description": "具体问题描述",
      "regulation_ref": "违反的监管规定（如能从知识库中找到则引用）",
      "suggestion": "修改建议"
    }
  ],
  "risk_summary": "一句话总结整体合规风险"
}

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```
请对以下产品需求进行合规检查：

用户需求：{{#Code_A1:查询构造.result.user_data#}}

知识库中的监管规则：
{{#context#}}

请逐项检查并输出合规报告。
```

**Assistant Prefill**：
```json
{
  "compliance_status":
```

#### 上下文配置
| 配置项 | 值 |
|--------|-----|
| 上下文来源 | `KB:产品知识库` 节点 |

---

### 节点 7：Code_A2 - 产品定义生成

| 配置项 | 值 |
|--------|-----|
| 类型 | Code（Python3） |
| 节点名 | `Code_A2:产品定义生成` |
| 上下文 | **不配置** |

#### 输入变量
| 变量名 | 来源节点 | 来源字段 |
|--------|----------|----------|
| `params_json` | `LLM_A2:参数推导` | `text` |
| `compliance_json` | `LLM_A3:合规检查` | `text` |
| `user_data` | `Code_A1:查询构造` | `result.user_data` |

#### 代码内容
```python
import json
import re
from datetime import datetime

def safe_parse(raw) -> dict:
    """安全解析LLM输出的JSON（与模块B共用模式）"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except:
                pass
    return {}

def generate_product_code(product_type: str) -> str:
    """生成产品代码"""
    type_map = {
        "重疾险": "CI", "医疗险": "MI", "定期寿险": "TL",
        "意外险": "PA", "年金险": "AN", "两全险": "EN"
    }
    prefix = type_map.get(product_type, "XX")
    year = datetime.now().year
    import random
    suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
    return f"{prefix}-{year}-{suffix}"

def validate_fields(params: dict, compliance: dict) -> dict:
    """字段完整性与合理性校验"""
    warnings = []
    missing = []
    
    # 必填字段检查
    required = {
        "product_type": "险种类型",
        "coverage_scope": "保障范围",
        "target_age_range": "目标客群年龄"
    }
    for field, label in required.items():
        if not params.get(field):
            missing.append({"field": field, "label": label})
    
    # 数值合理性检查
    si_range = params.get("sum_insured_range", {})
    if isinstance(si_range, dict):
        si_min = si_range.get("min", "")
        si_max = si_range.get("max", "")
        
        # 尝试解析数值
        def parse_amount(val):
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                digits = ''.join(c for c in val if c.isdigit() or c == '.')
                try:
                    num = float(digits)
                    if "万" in val:
                        num *= 10000
                    return num
                except:
                    return None
            return None
        
        min_val = parse_amount(si_min)
        max_val = parse_amount(si_max)
        
        if min_val and max_val:
            if min_val > max_val:
                warnings.append("保额下限大于上限，数据异常")
            if max_val > 5000000:
                warnings.append("保额上限超过500万元，需要额外风控审批")
            if min_val < 50000 and params.get("product_type") == "重疾险":
                warnings.append("重疾险保额下限过低（<5万），建议至少10万起")
    
    # 等待期检查
    waiting_days = params.get("waiting_period_days")
    if waiting_days:
        try:
            wd = int(waiting_days)
            product_type = params.get("product_type", "")
            if product_type == "重疾险" and wd < 90:
                warnings.append(f"重疾险等待期{w days}天低于监管最低要求90天")
            if wd < 0:
                warnings.append("等待期不能为负数")
            if wd > 365:
                warnings.append(f"等待期{w days}天异常偏高，请确认")
        except:
            warnings.append("等待期不是有效数值")
    
    # 合规结论汇总
    compliance_status = compliance.get("compliance_status", "unknown")
    compliance_issues = compliance.get("issues", [])
    critical_issues = [i for i in compliance_issues if i.get("severity") == "critical"]
    
    # 最终状态
    if critical_issues:
        status = "needs_revision"
    elif missing:
        status = "draft_incomplete"
    elif warnings:
        status = "draft_with_warnings"
    else:
        status = "ready_for_review"
    
    return {
        "status": status,
        "missing_fields": missing,
        "warnings": warnings,
        "compliance_status": compliance_status,
        "critical_compliance_issues": len(critical_issues)
    }

def main(params_json, compliance_json, user_data) -> dict:
    """产品定义生成主函数"""
    params = safe_parse(params_json)
    compliance = safe_parse(compliance_json)
    user = safe_parse(user_data)
    
    # 生成产品代码
    product_type = params.get("product_type", user.get("product_type", "未命名"))
    product_code = generate_product_code(product_type)
    
    # 生成产品名称
    product_concept = user.get("product_concept", "")
    if not product_concept:
        target_age = user.get("target_age_range", {})
        if isinstance(target_age, dict) and target_age.get("min", 0) <= 35:
            product_concept = f"面向年轻人的{product_type}"
        else:
            product_concept = f"综合{product_type}"
    
    # 产品名称从concept中提取关键词
    product_name = f"{product_type}" if not product_concept else product_concept[:20]
    
    # 字段校验
    validation = validate_fields(params, compliance)
    
    # 组装完整的产品定义JSON
    product_definition = {
        "product_code": product_code,
        "product_name": product_name,
        "product_concept": product_concept,
        "product_type": product_type,
        "insurance_type": product_type,
        "regulatory_region": user.get("regulatory_region", "中国大陆"),
        "target_market": {
            "age_range": user.get("target_age_range"),
            "income_range": user.get("target_income_range"),
            "occupations": user.get("target_occupations"),
            "geo_scope": user.get("regulatory_region", "中国大陆")
        },
        "coverage": {
            "scope": user.get("coverage_scope", ""),
            "sum_insured": user.get("sum_insured_range"),
            "special_clauses": user.get("special_clauses", [])
        },
        "terms": {
            "waiting_period_days": params.get("waiting_period_days"),
            "exclusions": params.get("exclusions", []),
            "grace_period_days": params.get("grace_period_days", 60),
            "reinstatement_period_months": params.get("reinstatement_period_months", 24)
        },
        "payment": {
            "period_options": params.get("payment_period_options", user.get("payment_period_options")),
            "frequency_options": params.get("payment_frequency_options", user.get("payment_frequency")),
            "premium_framework": params.get("premium_framework")
        },
        "compliance": {
            "status": compliance.get("compliance_status", "unchecked"),
            "issues_summary": compliance.get("risk_summary", ""),
            "critical_count": validation["critical_compliance_issues"]
        },
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "status": validation["status"],
            "version": "1.0-draft"
        }
    }
    
    return {
        "product_definition": json.dumps(product_definition, ensure_ascii=False, indent=2),
        "validation_report": json.dumps(validation, ensure_ascii=False),
        "status": validation["status"]
    }
```

#### 输出变量
| 输出 | 类型 | 说明 |
|------|------|------|
| `result` | dict | 包含 `product_definition`（完整JSON）、`validation_report`（校验报告）、`status`（状态） |

---

### 节点 8：LLM_A4 - 产品说明书生成

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM_A4:产品说明` |
| 模型 | deepseek-v4-pro |
| 上下文 | **不配置** |
| Temperature | 0.7（自然语言输出可更灵活） |

#### 提示词配置

**System Prompt**：
```
你是一个保险产品文案专家。你的任务是将结构化的产品定义JSON转化为一份面向产品经理和业务人员的可读产品说明书。

写作规则：
1. 面向内部业务人员（产品经理/核保员/渠道经理），不是面向消费者
2. 使用专业但易懂的语言
3. 所有数字和条款必须来自输入数据，不得编造
4. 如果某些字段为null或空，标注"待确定"而不猜测
5. 使用 Markdown 格式输出

说明书模板结构：

## 一、产品概述
- 产品名称、代码、定位
- 目标市场（客群画像、销售区域）

## 二、保障详情
- 保障责任详细说明
- 保额范围
- 特色条款说明

## 三、条款要点
- 等待期
- 免责条款（逐条说明）
- 宽限期与复效条款

## 四、缴费方案
- 可选缴费期
- 可选缴费频率
- 费率框架参考

## 五、合规状态
- 合规检查结论
- 风险提示（如有）

## 六、待确定事项
- 列举所有标注为"待确定"的字段，提示需要人工确认

## 七、下一步建议
- 精算定价（需精算师确认最终费率）
- 条款法律审查（需法务审核免责条款）
- 监管备案（如适用）
- 系统配置（在InsureMO产品工厂中录入）
```

**User Prompt**：
```
请根据以下产品定义生成产品说明书：

【产品定义JSON】
{{#Code_A2:产品定义生成.result.product_definition#}}

【校验报告】
{{#Code_A2:产品定义生成.result.validation_report#}}

【原始需求】
{{#Code_A1:查询构造.result.user_data#}}

请按模板结构生成产品说明书。
```

#### 输入变量
| 变量 | 来源 |
|------|------|
| 产品定义 | `Code_A2:产品定义生成` → `result.product_definition` |
| 校验报告 | `Code_A2:产品定义生成` → `result.validation_report` |
| 原始需求 | `Code_A1:查询构造` → `result.user_data` |

---

### 节点 9：End（输出）

| 配置项 | 值 |
|--------|-----|
| 类型 | 结束（end） |
| 节点名 | `输出` |

#### 输出变量（报告优先展示，JSON 供系统对接）
| 变量名 | 来源节点 | 来源字段 |
|--------|----------|----------|
| `product_brochure_md` | `LLM_A4:产品说明` | `text` |
| `product_definition_json` | `Code_A2:产品定义生成` | `result.product_definition` |
| `status` | `Code_A2:产品定义生成` | `result.status` |

> 将 `product_brochure_md`（人可读的 Markdown 产品说明书）放在第一输出位，确保 Dify 运行结果面板直接展示报告而非 JSON 代码。

---

## 3. 节点连接关系（边）

在 Dify 工作流画布上按以下顺序连线：

| 序号 | 源节点 | 目标节点 | 说明 |
|------|--------|----------|------|
| 1 | Start | LLM_A1:需求解析 | 用户输入 → 需求提取 |
| 2 | LLM_A1:需求解析 | Code_A1:查询构造 | 提取结果 → 构造查询 |
| 3 | Code_A1:查询构造 | KB:产品知识库 | 精准查询 → 知识检索 |
| 4 | KB:产品知识库 | LLM_A2:参数推导 | 规则 → 参数推导 |
| 5 | KB:产品知识库 | LLM_A3:合规检查 | 规则 → 合规检查（与4并行） |
| 6 | LLM_A2:参数推导 | Code_A2:产品定义生成 | 参数 → 定义生成 |
| 7 | LLM_A3:合规检查 | Code_A2:产品定义生成 | 合规 → 定义生成（与6并行汇入） |
| 8 | Code_A2:产品定义生成 | LLM_A4:产品说明 | 定义 → 说明书 |
| 9 | LLM_A4:产品说明 | End | 说明书 → 输出 |

> **并行关系**：LLM_A2 和 LLM_A3 都从 KB:产品知识库 出发，分别做参数推导和合规检查，然后同时汇入 Code_A2。Dify 自动并行执行。

---

## 4. 关键配置检查清单

上线前逐项检查：

| 序号 | 检查项 | 正确的配置 | 常见错误 |
|------|--------|------------|----------|
| 1 | KB检索的查询变量 | 指向 Code_A1 的 search_query | 指向 Start 的原始输入 |
| 2 | LLM_A2 的上下文 | `{{#context#}}` 来自 KB:产品知识库 | 没配上下文 |
| 3 | LLM_A3 的上下文 | `{{#context#}}` 来自 KB:产品知识库 | 同上 |
| 4 | LLM_A1 结构化输出 | 开启，Temperature 0.3 | Temperature 太高导致提取字段不稳定 |
| 5 | Code_A2 输入 | params_json + compliance_json + user_data | 遗漏任何一个 |
| 6 | 产品知识库有文档 | 4个文档均已上传并索引完成 | 空知识库导致检索无结果 |
| 7 | 节点命名精确 | 引用变量时节点名必须与实际节点名一致 | 改了节点名但没更新下游变量引用 |

---

## 5. 测试用例

### 测试 1：标准产品配置
```
输入：我想配置一款面向年轻人的重疾险，保额10-100万，覆盖120种重疾，
      含轻症豁免和重症多次赔付，支持月缴和年缴，目标客群22-35岁，价格要有竞争力。

预期：
- product_type: 重疾险
- waiting_period_days: 90
- 含轻症豁免 + 多次赔付
- 支持月缴 + 年缴
- status: draft_with_warnings 或 ready_for_review
```

### 测试 2：模糊需求 —— 需要系统推断
```
输入：想做一款高性价比的医疗险，主要卖给上班族。

预期：
- product_type: 医疗险
- target_occupations: ["上班族"] → 推断通用白领职业
- waiting_period_days: 30
- 多个字段填null或"待确定"
- status: draft_incomplete（很多必填字段缺失）
```

### 测试 3：包含竞品对标
```
输入：参考平安盛世福，做一款更便宜的定期重疾险，保至70岁，轻症赔付比例做到40%，
      目标客群30-45岁中产家庭。

预期：
- competitor_reference: 含"平安盛世福"
- 轻症给付40% → 合规检查可能warning（行业常见30%，40%偏高需关注）
- 定期保障（至70岁）
```

### 测试 4：合规风险测试
```
输入：配置一款终身重疾险，等待期30天，保额上限1000万，确诊即赔。

预期：
- 等待期30天 → 合规critical（重疾险最低90天）
- 保额1000万 → validation warning（超过500万阈值）
- "确诊即赔" → 合规warning（需符合疾病定义标准）
- status: needs_revision
```

### 测试 5：极端输入 —— 信息极少
```
输入：帮我做个保险产品。

预期：
- product_type 为null或推断失败
- 大部分字段为null
- status: draft_incomplete
- missing_fields 包含多个必填字段
- 系统不崩溃
```

---

## 6. 调试技巧

### 如果参数推导结果不合理
1. 检查 KB:产品知识库 是否检索到了相关的竞品数据和监管规则
2. 检查 LLM_A2 的 System Prompt 中的推导规则是否需要调整
3. 在 Code_A1 中打印 `search_query`，确认查询语句覆盖了关键维度

### 如果合规检查过于宽松/严格
1. 合规检查的严格程度主要由 System Prompt 中的检查规则决定
2. 如果过于严格：放宽某些检查条件（如"性别费率比<0.7"改为"<0.65"）
3. 如果过于宽松：增加更多检查维度

### 如果产品定义 JSON 字段缺失严重
1. 检查 LLM_A1 需求解析是否提取到了足够信息
2. 如果信息确实不足（用户输入模糊），这是预期的——系统应提示"信息不足"
3. 若需降低信息缺失率：在 Start 的 placeholder 中给出更具体的输入示例

### 如果 Code 节点报错
1. 点击 Code 节点 → 查看错误日志
2. 常见原因：上游 LLM 输出了非 JSON 格式、think 标签未被清洗干净
3. safe_parse 已做容错，如果仍报错，检查变量来源选择器是否正确

---

## 7. 与模块B的联动设计（预留）

当模块A和模块B都部署后，可以实现以下联动：

```
模块A 输出的 product_definition JSON
  → 存入产品知识库（作为新的产品文档）
    → 模块B 核保时可以检索该产品的核保规则
      → 模块B 做完核保后，如果拒保，可以推荐模块A配置的其他产品
```

面试时可以说："模块A生成的产品定义可以直接入库，成为模块B核保引擎的规则来源——这就形成了产品配置→核保决策的闭环。"

---

*配套文件：设计方案 v2.0、产品知识库文档（待撰写）、测试用例（待补充）*
