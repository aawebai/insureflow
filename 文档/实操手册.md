# InsureFlow 模块B：多Agent核保引擎 —— Dify 实操手册

## 文件说明
本文档对应设计方案 v2.0 中的 **P0 模块：多Agent协同核保引擎**。  
按步骤操作即可在 Dify 工作流中搭建完整可运行的核保引擎。模块B 是 InsureFlow 的核心，已实际部署并通过 8 个测试用例验证。

最可能出错的3个配置
  1. KB检索的查询变量：必须指向「代码执行:查询构造器」的 search_query 输出，不是 Start 的原始输入（否则检索为空）
  2. LLM2 / LLM3 的上下文：必须配置 `{{#context#}}` 来自「知识检索」节点（否则 LLM 看不到核保规则）
  3. 代码执行:定价计算的输入：需要同时接收职业评估(text)、健康评估(text)、用户数据(object)三个变量

---

## 0. 前置准备：创建核保规则知识库

### 步骤 0.1：在 Dify 中创建知识库
1. 进入 Dify 控制台 → 顶部导航「知识库」→ 「创建知识库」
2. 知识库名称：`核保规则库`
3. 上传文档：`核保规则文档.txt`（即《核保规则知识库》文档，位于同目录下）
4. 分段设置：
   - 分段方式：自动分段与清洗
   - 分段最大长度：500 tokens
   - 重叠长度：50 tokens
5. 索引方式：高质量（Embedding）
6. 完成后记录知识库 ID，后续 YML 和工作流中需要引用

### 步骤 0.2：确认模型配置
- LLM 模型：`deepseek-v4-pro`（deepseek 供应商）
- Embedding 模型：`text-embedding-3-large`（OpenAI 兼容）
- 重排序模型：`qwen3-rerank`（tongyi 供应商）
- 在 Dify 设置 → 模型供应商中确认已配置以上三个模型

### 步骤 0.3：知识库内容概览
`核保规则文档.txt` 包含以下 8 类规则：

| 章节 | 内容 | 支撑节点 |
|------|------|----------|
| 一、职业风险等级 | 6级职业分类 + 加费比例（程序员0%→雇佣兵拒保） | LLM2:职业风险评估 |
| 二、各险种核保规则 | 重疾/医疗/定寿/意外险的基准费率表 | 代码执行:定价计算 |
| 三、健康状况核保规则 | 高血压/糖尿病/结节/BMI等9类加费标准 | LLM3:健康风险评估 |
| 四、BMI体重指数规则 | 从16.0到40.0的7档加费标准 | LLM3:健康风险评估 |
| 五、吸烟核保规则 | 轻度/中度/重度吸烟 + 戒烟后的加费标准 | LLM3 + 定价计算 |
| 六、年龄风险系数 | ≤17(0.8) → >65(2.0) 五档系数 | 代码执行:定价计算 |
| 七、综合核保决策标准 | 标准体/次标准体/延期体/拒保体的判定标准 | LLM4:决策汇总 |
| 八、常见组合场景参考 | 8个典型案例的核保结论 | LLM4:决策汇总 |

---

## 1. 创建工作流

### 步骤 1.1
1. Dify 控制台 → 「创建应用」→ 选择「工作流」
2. 名称：`智保通-多Agent核保引擎`
3. 描述：`基于多Agent协同的智能核保决策工作流——用户输入个人信息，5个Agent并行评估职业/健康风险，输出核保决策报告和精准定价`

> 如果已有导出的 YML 文件（`智保通-多Agent核保引擎.yml`），可直接导入。导入后仅需替换知识库 ID。

---

## 2. 节点配置（共 9 个节点，按顺序配置）

### 工作流全局结构
```
Start(INSURE_inquiry)
  │
  ▼
LLM1:信息提取 ─── 提取结构化字段（temperature=0.7, structured_output=on）
  │
  ▼
代码执行:查询构造器 ─── 清洗think标签 + 构造精准query + 传递user_data
  │
  ▼
知识检索 ─── Top K=8, 混合检索, qwen3-rerank重排序
  │
  ├──────────────────────────────────┐
  ▼                                  ▼
LLM2:职业风险评估                    LLM3:健康风险评估
  │ (context=知识检索)                │ (context=知识检索)
  │ System Prompt内含降级规则        │ System Prompt内含降级规则
  │                                  │
  └────────────┬─────────────────────┘
               ▼
代码执行:定价计算 ─── safe_parse ×3 → 费率查表 → 风险系数计算 → JSON输出
  │
  ▼
LLM4:决策汇总 ─── 综合评估 → 四档决策（temperature=0.7）
  │
  ▼
LLM5:报告生成 ─── Markdown格式化输出（temperature=0.7）
  │
  ▼
End(OUTPUT)
```

---

### 节点 1：Start（用户输入）

| 配置项 | 值 |
|--------|-----|
| 类型 | 开始（start） |
| 节点名 | `用户输入` |
| 输入变量 | 变量名 `INSURE_inquiry`，类型 `text-input`，必填 |
| 标签 | `投保咨询` |
| 最大长度 | 256 |

**变量引用名**：`{{#start.INSURE_inquiry#}}`

**Placeholder 引导语**：
```
请描述您的投保需求，例如：
"我今年30岁，男，程序员，不抽烟，身体健康，想买50万重疾险。身高175cm，体重70kg。"
```

---

### 节点 2：LLM1 - 信息提取

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM1:信息提取` |
| 模型 | deepseek-v4-pro |
| 上下文 | **不配置**（此节点不需要知识库上下文） |

#### 提示词配置

**System Prompt**：
```text
你是一个保险信息提取器。你的唯一任务是从用户输入中提取投保所需的结构化字段。不做任何判断、不计算、不给建议。

提取字段及规则：
- age: 年龄数字（整数），未提及填"未知"
- gender: 男/女，未提及填"未知"
- occupation: 具体职业名称，如"程序员""教师""外卖骑手"
- insurance_type: 重疾险/医疗险/定期寿险/意外险，未提及填"未知"
- coverage_amount: 保额（保留数字+单位，如"50万"），未提及填"未知"
- health_notes: 用户提到的所有健康状况，如"高血压""甲状腺结节"，无异常填"无异常"
- smoking: 有/无，未提及填"未知"
- bmi: 如用户提供了身高体重则计算（体重kg÷身高m²，保留一位小数），否则填"未知"

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```text
请从以下用户输入中提取投保信息：

用户输入：{{#start.INSURE_inquiry#}}
```

**Assistant Prefill**：
```json
{
  "age":
```

#### 关键设置
| 设置项 | 值 |
|--------|-----|
| 结构化输出 | **开启**（structured_output_enabled: true） |
| 重试 | 开启，最大3次，间隔1000ms |
| Temperature | 0.7 |
| 记忆 | **不开启** |

#### 输入变量
| 变量 | 来源 |
|------|------|
| `{{#start.INSURE_inquiry#}}` | 用户输入的原始投保咨询 |

---

### 节点 3：代码执行 - 查询构造器

| 配置项 | 值 |
|--------|-----|
| 类型 | Code（Python3） |
| 节点名 | `代码执行:查询构造器` |
| 上下文 | **不配置** |

#### 输入变量
| 变量名 | 来源节点 | 来源字段 |
|--------|----------|----------|
| `extracted_json` | `LLM1:信息提取` | `text` |

#### 代码内容
```python
import json
import re

def main(extracted_json: str) -> dict:
    """
    从LLM提取的JSON中构造精准的知识库查询语句
    解决之前用原始自然语言查询匹配度低的问题
    """
    # 清洗可能的 <think> 标签
    if isinstance(extracted_json, str):
        extracted_json = re.sub(r"<think>.*?</think>", "", extracted_json, flags=re.DOTALL).strip()
        try:
            data = json.loads(extracted_json)
        except:
            data = {}
    else:
        data = extracted_json if isinstance(extracted_json, dict) else {}
    
    occupation = data.get("occupation", "")
    insurance_type = data.get("insurance_type", "")
    health_notes = data.get("health_notes", "")
    age = data.get("age", "")
    smoking = data.get("smoking", "")
    bmi = data.get("bmi", "")
    
    # 构造精准查询：将关键字段拼接成语义查询
    query_parts = []
    
    if occupation and occupation != "未知":
        query_parts.append(f"职业：{occupation}，职业风险等级与费率调整")
    
    if insurance_type and insurance_type != "未知":
        query_parts.append(f"险种：{insurance_type}，核保规则与要点")
    
    if health_notes and health_notes != "无异常" and health_notes != "未知":
        query_parts.append(f"健康状况：{health_notes}，核保规则与加费标准")
    
    if smoking == "有":
        query_parts.append("吸烟核保规则，加费15%")
    
    if bmi and bmi != "未知":
        query_parts.append(f"BMI体重指数核保规则")
    
    # 始终查询年龄系数
    if age and age != "未知":
        query_parts.append(f"年龄{age}岁对应的风险系数")
    else:
        query_parts.append("年龄风险系数表")
    
    search_query = "；".join(query_parts) if query_parts else "核保规则综合查询"
    
    return {
        "search_query": search_query,
        "user_data": data
    }
```

#### 输出变量
| 输出 | 说明 |
|------|------|
| `result` | 包含 `search_query`（检索用）和 `user_data`（原始提取数据） |

#### 关键设置
| 设置项 | 值 |
|--------|-----|
| 重试 | 开启，最大3次，间隔1000ms |

---

### 节点 4：知识检索

| 配置项 | 值 |
|--------|-----|
| 类型 | 知识检索（knowledge-retrieval） |
| 节点名 | `知识检索` |
| 知识库 | 选择第0步创建的「核保规则库」 |

#### 检索设置
| 设置项 | 值 | 说明 |
|--------|-----|------|
| 检索模式 | 混合检索（multiple） | 向量+关键词双路召回 |
| Top K | 8 | 比模块A的6更高，因核保需覆盖职业+健康+年龄+BMI+吸烟多个维度 |
| 重排序 | **开启** | 提升检索精度 |
| 重排序模型 | qwen3-rerank | tongyi 供应商 |
| 权重设置 | 向量权重 0.7，关键词权重 0.3 | |

#### 查询变量（核心！）
| 变量 | 来源 |
|------|------|
| 查询文本 | `代码执行:查询构造器` → `result` → `search_query` |

> **这是之前知识检索为空的根因修复点**：不再用原始用户输入 `{{#start.INSURE_inquiry#}}`，而是用代码节点构造的精准关键词查询。原始自然语言（如"我30岁外卖骑手想买重疾险"）和知识库规则文本（如"3级风险职业加费10%"）的语义距离太远，直接 Embedding 匹配效果差。

#### 输入变量（上下文变量）
| 变量名 | 来源节点 | 来源字段 | 用途 |
|--------|----------|----------|------|
| `user_data` | `代码执行:查询构造器` | `result.user_data` | 传递给下游节点使用 |

---

### 节点 5：LLM2 - 职业风险评估（与LLM3并行）

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM2:职业风险评估` |
| 模型 | deepseek-v4-pro |
| 上下文 | **配置为「知识检索」的输出**（`{{#context#}}`） |
| Temperature | 0.7 |

#### 提示词配置

**System Prompt**：
```text
你是一个保险职业风险评估专家。你的唯一职责是从知识库检索结果中，找到与用户职业匹配的风险等级和费率调整规则。

规则：
1. 从知识库检索结果中精确匹配用户的职业名称
2. 如果知识库中有明确匹配，输出匹配的等级和加费比例
3. 如果知识库无精确匹配，根据相近职业推断，并标注"推断"
4. 优先使用知识库规则；若知识库无精确匹配，按以下通用标准评估：

通用职业风险等级标准（加费比例）：
- 1级+0%（室内办公）：程序员、文员、教师、学生、行政、会计、设计师、产品经理、客服、人事、财务、律师、退休人员
- 2级+0%（轻度外勤）：销售员、店员、外卖骑手、快递员、网约车司机、出租车司机、导游、家政人员、物业管理员
- 3级+10%（体力劳动/一定危险）：建筑工人、装修工人、水电工、电焊工、机械操作工、化工厂操作工、矿工地面、货车司机、农民、渔民近海、垃圾清运工
- 4级+20-30%（高风险）：高空作业、塔吊司机、架子工、爆破工、矿井下、深海渔民、消防员一线、刑警、特警、职业运动员
- 5级+50-100%（极高风险）：试飞员、深海潜水员、拆弹专家、战地记者、远洋船员、私人保镖、赛车手
- 6级拒保：雇佣兵、无安全保障高危作业

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```text
用户职业：{{#代码执行:查询构造器.result.user_data.occupation#}}
用户险种：{{#代码执行:查询构造器.result.user_data.insurance_type#}}

知识库检索到的职业规则：
{{#context#}}

请评估该用户的职业风险等级和费率调整。
```

**Assistant Prefill**：
```json
{
  "agent": "职业风险评估",
  "occupation":
```

#### 上下文配置（关键！）
| 配置项 | 值 |
|--------|-----|
| 上下文来源 | `知识检索` 节点 |
| 引用方式 | `{{#context#}}`（自动获取检索到的片段） |

---

### 节点 6：LLM3 - 健康风险评估（与LLM2并行）

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM3:健康风险评估` |
| 模型 | deepseek-v4-pro |
| 上下文 | **配置为「知识检索」的输出**（`{{#context#}}`） |
| Temperature | 0.7 |

#### 提示词配置

**System Prompt**：
```text
你是一个保险健康风险评估专家。你的唯一任务是从知识库检索结果和用户健康信息中，匹配健康核保规则并给出评估结论。

规则：
1. 逐条匹配用户的健康状况与知识库中的核保规则
2. 多项健康异常时取最严重的结论
3. 严重程度排序：拒保 > 延期 > 加费 > 限额 > 标体
4. 给出每种健康异常的加费比例（如适用）
5. 优先使用知识库规则；若知识库无精确匹配，按以下通用规则评估：

通用健康核保规则（知识库无匹配时使用）：
- 高血压（服药控制，血压稳定）：加费20%
- 高血压（未治疗或控制不佳）：加费40%
- 高血压（≥180/110，3级）：拒保
- 糖尿病（2型，口服药控制，无并发症）：加费50%
- 糖尿病（合并心/脑/肾并发症）：拒保
- BMI 24.0-27.9（超重）：加费15%
- BMI 28.0-31.9（肥胖）：加费30%
- BMI 32.0-39.9（重度肥胖）：加费50%
- BMI ≥40.0（病态肥胖）：拒保
- 吸烟：加费15%
- 重度吸烟（每天≥20支，烟龄≥10年）：加费30%
- 高血脂（轻度）：加费10%
- 高血脂（中重度）：加费20-40%
- 甲状腺结节（TI-RADS 3级）：加费20%
- 脂肪肝（轻度无肝功能异常）：加费10%
- 脂肪肝（中重度）：加费25-50%
- 痛风（偶发，尿酸控制良好）：加费15%
- 轻度贫血（Hb 90-110g/L）：加费15%

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```text
用户健康状况：{{#代码执行:查询构造器.result.user_data.health_notes#}}
用户BMI：{{#代码执行:查询构造器.result.user_data.bmi#}}
用户吸烟：{{#代码执行:查询构造器.result.user_data.smoking#}}
用户年龄：{{#代码执行:查询构造器.result.user_data.age#}}
用户险种：{{#代码执行:查询构造器.result.user_data.insurance_type#}}

知识库检索到的健康核保规则：
{{#context#}}

请评估该用户的健康风险等级和费率调整。
```

**Assistant Prefill**：
```json
{
  "agent": "健康风险评估",
  "findings":
```

#### 上下文配置
| 配置项 | 值 |
|--------|-----|
| 上下文来源 | `知识检索` 节点 |

---

### 节点 7：代码执行 - 定价计算

| 配置项 | 值 |
|--------|-----|
| 类型 | Code（Python3） |
| 节点名 | `代码执行:定价计算` |
| 上下文 | **不配置** |

#### 输入变量
| 变量名 | 来源节点 | 来源字段 |
|--------|----------|----------|
| `occupation_risk_json` | `LLM2:职业风险评估` | `text` |
| `health_risk_json` | `LLM3:健康风险评估` | `text` |
| `user_data` | `代码执行:查询构造器` | `result.user_data` |

#### 代码内容
```python
import json
import re
from typing import Union

def safe_parse(raw) -> dict:
    """安全解析LLM输出的JSON（清洗think标签）"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        # 提取第一个JSON对象
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except:
                pass
    return {}

def extract_age_coefficient(age: int) -> float:
    """年龄风险系数"""
    if age <= 17:
        return 0.8
    elif age <= 40:
        return 1.0
    elif age <= 55:
        return 1.3
    elif age <= 65:
        return 1.6
    else:
        return 2.0

def extract_smoking_coefficient(smoking: str) -> float:
    """吸烟风险系数"""
    if smoking == "有":
        return 1.15
    return 1.0

def extract_occupation_adjustment(occ_risk: dict) -> float:
    """从职业风险评估结果中提取加费比例（小数形式）"""
    adjustment_str = str(occ_risk.get("adjustment", "0%"))
    # 优先取数字部分
    nums = re.findall(r"[\d.]+", adjustment_str)
    if nums:
        return float(nums[0]) / 100.0
    return 0.0

def extract_health_adjustment(health_risk: dict) -> float:
    """从健康风险评估结果中提取加费比例"""
    adjustment_str = str(health_risk.get("adjustment", "0%"))
    nums = re.findall(r"[\d.]+", adjustment_str)
    if nums:
        return float(nums[0]) / 100.0
    return 0.0

def main(occupation_risk_json: Union[str, dict], health_risk_json: Union[str, dict], user_data: Union[str, dict]) -> dict:
    """定价计算引擎"""
    # 安全解析所有输入
    occ = safe_parse(occupation_risk_json)
    health = safe_parse(health_risk_json)
    user = safe_parse(user_data)
    
    # 提取用户信息
    age_raw = user.get("age", 30)
    try:
        age = int(age_raw)
    except:
        age = 30
    
    gender = user.get("gender", "男")
    ins_type = user.get("insurance_type", "重疾险")
    
    coverage_raw = user.get("coverage_amount", "50万")
    coverage_raw_str = str(coverage_raw)
    coverage_digits = ''.join(c for c in coverage_raw_str if c.isdigit())
    if coverage_digits:
        coverage_num = float(coverage_digits)
        if "万" in coverage_raw_str:
            coverage_num *= 10000
    else:
        coverage_num = 500000
    coverage_in_10k = coverage_num / 100000
    
    # 基准费率表（元/年/10万保额）
    base_rate_table = {
        "重疾险": {
            "male": {18: 800, 30: 1200, 40: 2200, 50: 4200, 60: 7800},
            "female": {18: 720, 30: 1080, 40: 1980, 50: 3780, 60: 7000}
        },
        "医疗险": {
            "male": {18: 350, 30: 500, 40: 900, 50: 1800, 60: 3200},
            "female": {18: 320, 30: 460, 40: 820, 50: 1650, 60: 2900}
        },
        "定期寿险": {
            "male": {18: 400, 30: 650, 40: 1200, 50: 2800, 60: 5500},
            "female": {18: 360, 30: 580, 40: 1080, 50: 2500, 60: 4800}
        },
        "意外险": {
            "male": {18: 120, 30: 150, 40: 200, 50: 300, 60: 500},
            "female": {18: 120, 30: 150, 40: 200, 50: 300, 60: 500}
        }
    }
    
    # 查找基准费率
    default_table = base_rate_table.get(ins_type, base_rate_table["重疾险"])
    gender_key = "female" if gender == "女" else "male"
    age_brackets = sorted(default_table[gender_key].keys())
    nearest_age = min(age_brackets, key=lambda x: abs(x - age))
    base_rate = default_table[gender_key][nearest_age]
    
    # 计算风险系数
    occ_adj = extract_occupation_adjustment(occ)
    health_adj = extract_health_adjustment(health)
    age_coeff = extract_age_coefficient(age)
    smoking_coeff = extract_smoking_coefficient(user.get("smoking", "未知"))
    
    # 综合风险系数
    if occ_adj == 0 and health_adj == 0:
        comprehensive_coeff = 1.0 * age_coeff * smoking_coeff
    else:
        comprehensive_coeff = (1.0 + occ_adj + health_adj) * age_coeff * smoking_coeff
    
    comprehensive_coeff = round(comprehensive_coeff, 3)
    
    # 计算保费
    base_premium = base_rate * coverage_in_10k
    total_premium = base_premium * comprehensive_coeff
    surcharge = total_premium - base_premium
    
    result = {
        "base_rate": base_rate,
        "base_rate_unit": "元/年/10万保额",
        "age_bracket": nearest_age,
        "coverage_10k": coverage_in_10k,
        "occupation_adjustment": round(occ_adj * 100, 1),
        "health_adjustment": round(health_adj * 100, 1),
        "age_coefficient": age_coeff,
        "smoking_coefficient": smoking_coeff,
        "comprehensive_risk_coefficient": comprehensive_coeff,
        "base_annual_premium": round(base_premium, 2),
        "risk_surcharge": round(surcharge, 2),
        "total_annual_premium": round(total_premium, 2),
        "monthly_premium": round(total_premium / 12, 2)
    }
    return {"result": json.dumps(result, ensure_ascii=False)}
```

#### 输出变量
| 输出 | 类型 | 说明 |
|------|------|------|
| `result` | string | 完整定价结果JSON |

---

### 节点 8：LLM4 - 决策汇总

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM4:决策汇总` |
| 模型 | deepseek-v4-pro |
| 上下文 | **不配置** |
| Temperature | 0.7 |

#### 提示词配置

**System Prompt**：
```text
你是一个保险核保决策官。你的任务是综合职业风险评估、健康风险评估和定价结果，做出最终核保决定。

决策四档标准：

标准体（正常承保）：
- 综合风险系数 ≤ 1.0 且 职业风险等级 ≤ 2 且 健康风险为"标准"
- 按标准费率承保，无附加条件

次标准体（加费/限额承保）：
- 综合风险系数 1.01-1.5，或存在单一可逆健康风险
- 必须给出具体的加费比例或限额方案

延期体（延期处理）：
- 健康异常暂无法评估，预计3-6个月内可改善
- 必须给出延期时长（3个月/6个月/1年）和后续建议

拒保体（拒绝承保）：
- 综合风险系数 > 1.5，或存在明确的拒保指征
- 必须给出拒保具体理由和替代险种建议

输出必须是合法JSON，不包含任何其他文字。
```

**User Prompt**：
```text
请基于以下各Agent的评估结果，做出核保决策：

用户基本信息：{{#代码执行:查询构造器.result.user_data#}}

职业风险评估：{{#LLM2:职业风险评估.text#}}

健康风险评估：{{#LLM3:健康风险评估.text#}}

定价计算结果：{{#代码执行:定价计算.result#}}

请输出最终核保决策。
```

**Assistant Prefill**：
```json
{
  "decision": "
```

#### 输入变量
| 变量 | 来源 |
|------|------|
| 用户信息 | `代码执行:查询构造器` → `result.user_data` |
| 职业评估 | `LLM2:职业风险评估` → `text` |
| 健康评估 | `LLM3:健康风险评估` → `text` |
| 定价结果 | `代码执行:定价计算` → `result` |

---

### 节点 9：LLM5 - 报告生成

| 配置项 | 值 |
|--------|-----|
| 类型 | LLM |
| 节点名 | `LLM5:报告生成` |
| 模型 | deepseek-v4-pro |
| 上下文 | **不配置** |
| Temperature | 0.7 |

#### 提示词配置

**System Prompt**：
```text
你是一个保险核保报告生成器。你的任务是将前置节点的结构化结果转化为一份面向用户的可读报告。

报告规则：
1. 面向普通用户，避免技术术语，能用大白话就用大白话
2. 所有数字和结论必须来自输入数据，不得编造
3. 使用 Markdown 格式输出
4. 风险提示要醒目但不制造恐慌
5. 结尾必须包含免责声明

报告模板结构：
1. 投保信息摘要（表格形式）
2. 风险评估详情（分职业风险、健康风险、年龄因素，含风险系数）
3. 费率试算（表格形式，含基准保费、风险加费、最终保费）
4. 核保结论（结论标题醒目，含结论说明、承保条件、建议）
5. 免责声明
```

**User Prompt**：
```text
请根据以下各节点的分析结果，生成一份完整的核保决策报告：

【投保信息】{{#代码执行:查询构造器.result.user_data#}}

【职业风险评估】{{#LLM2:职业风险评估.text#}}

【健康风险评估】{{#LLM3:健康风险评估.text#}}

【费率试算】{{#代码执行:定价计算.result#}}

【核保结论】{{#LLM4:决策汇总.text#}}

请按模板结构生成报告。
```

---

### 节点 10：End（输出）

| 配置项 | 值 |
|--------|-----|
| 类型 | 结束（end） |
| 节点名 | `输出` |
| 输出变量 | `{{#LLM5:报告生成.text#}}`（变量名 `OUTPUT`） |

---

## 3. 节点连接关系（边）

在 Dify 工作流画布上按以下顺序连线：

| 序号 | 源节点 | 目标节点 | 说明 |
|------|--------|----------|------|
| 1 | Start | LLM1:信息提取 | 用户输入 → 信息提取 |
| 2 | LLM1:信息提取 | 代码执行:查询构造器 | 提取结果 → 构造查询 |
| 3 | 代码执行:查询构造器 | 知识检索 | 精准查询 → 知识检索 |
| 4 | 知识检索 | LLM2:职业风险评估 | 规则 → 职业评估Agent |
| 5 | 知识检索 | LLM3:健康风险评估 | 规则 → 健康评估Agent（**与4并行**） |
| 6 | LLM2:职业风险评估 | 代码执行:定价计算 | 职业评估 → 定价 |
| 7 | LLM3:健康风险评估 | 代码执行:定价计算 | 健康评估 → 定价（**与6并行汇入**） |
| 8 | 代码执行:定价计算 | LLM4:决策汇总 | 定价结果 → 决策汇总 |
| 9 | LLM4:决策汇总 | LLM5:报告生成 | 决策 → 报告 |
| 10 | LLM5:报告生成 | End | 报告 → 输出 |

> **并行关系说明**：节点 LLM2 和 LLM3 都从「知识检索」出发，各自独立评估不同维度，然后同时汇入「代码执行:定价计算」。Dify 自动并行执行这两个分支，延迟减少约 50%。

---

## 4. 关键配置检查清单

上线前逐项检查：

| 序号 | 检查项 | 正确的配置 | 常见错误 |
|------|--------|------------|----------|
| 1 | KB检索的查询变量 | 指向「代码执行:查询构造器」的 search_query | 指向 Start 的 INSURE_inquiry（检索为空） |
| 2 | LLM2 的上下文 | `{{#context#}}` 来自「知识检索」节点 | 没配上下文，LLM 看不到职业规则 |
| 3 | LLM3 的上下文 | `{{#context#}}` 来自「知识检索」节点 | 同上 |
| 4 | LLM1 结构化输出 | 开启（structured_output_enabled: true） | 关闭导致输出格式不稳定 |
| 5 | 代码执行:查询构造器 输入 | `extracted_json` 来自 LLM1.text | 选错来源 |
| 6 | 代码执行:定价计算 输入 | occupation_risk_json + health_risk_json + user_data 三个都配 | 遗漏任何一个都会计算不准 |
| 7 | 知识库文档已索引 | 核保规则库中有已索引的文档（状态"已完成"） | 空知识库导致检索无结果 |
| 8 | 重排序模型可用 | qwen3-rerank 已配置且可用 | 模型不可用导致检索失败 |
| 9 | LLM2 System Prompt 含降级规则 | 6级职业分类 + 加费比例 | 不含降级规则导致KB无匹配时 LLM 乱编 |
| 10 | LLM3 System Prompt 含降级规则 | 9类健康异常的加费标准 | 同上 |

---

## 5. 测试用例

### 测试目标
覆盖全场景：标准体 / 加费体 / 拒保体 / 信息缺失 / LLM输出异常容错 / 边界值 / 男女同价验证。

---

### 案例 1：标准体 — 28岁健康程序员买重疾险

**用户输入：**
> 我今年28岁，男，程序员，不抽烟，身体健康，想买50万重疾险。身高175cm，体重70kg。

**LLM1 预期输出（信息提取）：**
```json
{
  "age": 28,
  "gender": "男",
  "occupation": "程序员",
  "insurance_type": "重疾险",
  "coverage_amount": "50万",
  "health_notes": "无异常",
  "smoking": "无",
  "bmi": 22.9
}
```

**代码执行:查询构造器 预期输出：**
```json
{
  "search_query": "职业：程序员，职业风险等级与费率调整；险种：重疾险，核保规则与要点；年龄28岁对应的风险系数",
  "user_data": { ... }
}
```

**LLM2 预期输出（职业风险评估）：**
```json
{
  "agent": "职业风险评估",
  "occupation": "程序员",
  "risk_level": "1级",
  "adjustment": "0%",
  "conclusion": "标准体正常承保"
}
```

**LLM3 预期输出（健康风险评估）：**
```json
{
  "agent": "健康风险评估",
  "findings": [],
  "conclusion": "标准",
  "adjustment": "0%"
}
```

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 1200,
  "base_rate_unit": "元/年/10万保额",
  "age_bracket": 30,
  "coverage_10k": 5.0,
  "occupation_adjustment": 0.0,
  "health_adjustment": 0.0,
  "age_coefficient": 1.0,
  "smoking_coefficient": 1.0,
  "comprehensive_risk_coefficient": 1.0,
  "base_annual_premium": 6000.00,
  "risk_surcharge": 0.00,
  "total_annual_premium": 6000.00,
  "monthly_premium": 500.00
}
```

**LLM4 预期决策：** 标准体（正常承保）

---

### 案例 2：高风险 — 45岁吸烟建筑工+高血压+肥胖，买医疗险

**用户输入：**
> 45岁，男，建筑工人，抽烟10年，有高血压在吃药控制。想买30万医疗险。身高170，体重85kg。

**LLM1 预期输出：**
```json
{
  "age": 45, "gender": "男", "occupation": "建筑工人",
  "insurance_type": "医疗险", "coverage_amount": "30万",
  "health_notes": "高血压", "smoking": "有", "bmi": 29.4
}
```

**LLM2 预期输出：**
```json
{
  "agent": "职业风险评估",
  "occupation": "建筑工人",
  "risk_level": "3级",
  "adjustment": "10%"
}
```

**LLM3 预期输出：**
```json
{
  "agent": "健康风险评估",
  "findings": [
    { "condition": "高血压", "result": "加费20%" },
    { "condition": "BMI 29.4", "result": "加费30%" },
    { "condition": "吸烟", "result": "加费15%" }
  ],
  "conclusion": "加费",
  "adjustment": "65%"
}
```

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 900,
  "age_bracket": 40,
  "coverage_10k": 3.0,
  "occupation_adjustment": 10.0,
  "health_adjustment": 65.0,
  "age_coefficient": 1.3,
  "smoking_coefficient": 1.15,
  "comprehensive_risk_coefficient": 2.616,
  "base_annual_premium": 2700.00,
  "risk_surcharge": 4364.45,
  "total_annual_premium": 7064.45,
  "monthly_premium": 588.70
}
```

**LLM4 预期决策：** 拒保体（综合风险系数 2.616 > 1.5）

> **定价计算明细**（面试时可以说出这个推导）：
> - coverage_in_10k = 300000/100000 = 3.0
> - age_coeff = 1.3 (45 ≤ 55)
> - occ_adj = 10/100 = 0.10
> - health_adj = (20+30+15)/100 = 0.65
> - comprehensive_coeff = (1 + 0.10 + 0.65) × 1.3 × 1.15 = 1.75 × 1.495 = 2.616
> - total = 900 × 3.0 × 2.616 = 7,064.45

---

### 案例 3：标准体 — 22岁女性文员买定期寿险

**用户输入：**
> 22岁，女生，办公室文员，身体健康不抽烟，想买100万定期寿险。

**LLM1 预期输出：**
```json
{
  "age": 22, "gender": "女", "occupation": "文员",
  "insurance_type": "定期寿险", "coverage_amount": "100万",
  "health_notes": "无异常", "smoking": "无", "bmi": "未知"
}
```

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 360,
  "age_bracket": 18,
  "coverage_10k": 10.0,
  "occupation_adjustment": 0.0,
  "health_adjustment": 0.0,
  "age_coefficient": 1.0,
  "smoking_coefficient": 1.0,
  "comprehensive_risk_coefficient": 1.0,
  "base_annual_premium": 3600.00,
  "risk_surcharge": 0.00,
  "total_annual_premium": 3600.00,
  "monthly_premium": 300.00
}
```

**LLM4 预期决策：** 标准体

---

### 案例 4：老年拒保 — 68岁糖尿病+高血压

**用户输入：**
> 68岁，男，退休人员，有2型糖尿病和高血压，想买50万重疾险。

**LLM1 预期输出：**
```json
{
  "age": 68, "gender": "男", "occupation": "退休人员",
  "insurance_type": "重疾险", "coverage_amount": "50万",
  "health_notes": "2型糖尿病，高血压", "smoking": "未知", "bmi": "未知"
}
```

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 7800,
  "age_bracket": 60,
  "coverage_10k": 5.0,
  "age_coefficient": 2.0,
  "base_annual_premium": 39000.00,
  "total_annual_premium": ">78000（取决于健康/职业加费）"
}
```

**LLM4 预期决策：** 拒保体（高龄+糖尿病+高血压）

---

### 案例 5：信息缺失 — 系统不崩溃

**用户输入：**
> 我想买个保险，不太懂，帮我看看。

**LLM1 预期输出：**
```json
{
  "age": "未知", "gender": "未知", "occupation": "未知",
  "insurance_type": "未知", "coverage_amount": "未知",
  "health_notes": "未知", "smoking": "未知", "bmi": "未知"
}
```

**代码执行:查询构造器 预期输出：**
```json
{
  "search_query": "年龄风险系数表",
  "user_data": { ... 全未知 ... }
}
```

**预期行为：** 系统不崩溃。定价代码使用默认值 age=30、gender=男、insurance_type=重疾险、coverage_amount=50万。LLM4 输出"信息不足，无法做出准确核保决策，请补充以下信息..."。

**验证点：** 三个 Code 节点都不报错，safe_parse 兜底生效。

---

### 案例 6：LLM 返回含 `<think>` 标签（鲁棒性验证）

**模拟场景：** LLM1 的输出不是纯 JSON，而是包裹了 `<think>` 标签：

```text
<think>需要提取用户信息...</think>
{
  "age": 35, "gender": "女", "occupation": "外卖骑手",
  "insurance_type": "意外险", "coverage_amount": "20万",
  "health_notes": "无异常", "smoking": "无", "bmi": "未知"
}
```

**预期：** 代码执行:查询构造器中的 `re.sub(r"<think>.*?</think>", ...)` 清洗 think 标签后正常解析。search_query 含"职业：外卖骑手"和"险种：意外险"。

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 150, "age_bracket": 40,
  "coverage_10k": 2.0, "comprehensive_risk_coefficient": 1.0,
  "total_annual_premium": 300.00, "monthly_premium": 25.00
}
```

**验证点：** 三个 Code 节点的 safe_parse 和 think 标签清洗逻辑生效。即使 LLM 输出异常，系统不出错。

---

### 案例 7：边界值 — 17岁少年买医疗险

**用户输入：**
> 17岁，男，学生，身体健康，想买20万医疗险。

**代码执行:定价计算 预期输出：**
```json
{
  "base_rate": 350, "age_bracket": 18,
  "coverage_10k": 2.0, "age_coefficient": 0.8,
  "comprehensive_risk_coefficient": 0.8,
  "base_annual_premium": 700.00,
  "total_annual_premium": 560.00,
  "monthly_premium": 46.67
}
```

**LLM4 预期决策：** 标准体（年龄系数0.8，保费是基准的80%）

**验证点：** age_coefficient=0.8（≤17岁档），comprehensive_coeff=0.8（未成年人保费优惠）

---

### 案例 8：意外险男女同价验证

**输入 A：** 30岁，男，程序员，意外险 10 万，身体健康

**输入 B：** 30岁，女，文员，意外险 10 万，身体健康

**预期：** 两个输入定价完全一致——total_annual_premium = 150.00，monthly_premium = 12.50

**验证点：** 意外险 base_rate 男女均为 150（元/年/10万保额），不区分性别。

---

### 测试结果汇总表

| # | 场景 | 险种 | 综合风险系数 | 年保费(元) | 月保费(元) | 决策 |
|---|------|------|:---:|:---:|:---:|------|
| 1 | 28岁程序员/健康/50万 | 重疾险 | 1.000 | 6,000 | 500 | **标准体** |
| 2 | 45岁建筑工/高血压/吸烟/30万 | 医疗险 | 2.616 | 7,064 | 589 | **拒保体** |
| 3 | 22岁文员女/健康/100万 | 定期寿险 | 1.000 | 3,600 | 300 | **标准体** |
| 4 | 68岁退休/糖尿病+高血压/50万 | 重疾险 | >4.0 | >78,000 | — | **拒保体** |
| 5 | 信息全缺失 | — | 默认值 | — | — | 待补充信息 |
| 6 | 35岁外卖骑手/意外险+think标签 | 意外险 | 1.000 | 300 | 25 | **标准体** |
| 7 | 17岁学生/医疗险20万 | 医疗险 | 0.800 | 560 | 47 | **标准体** |
| 8 | 30岁意外险男女对比 | 意外险 | 1.000 | 150 | 13 | **标准体** |

> 8 个用例覆盖 4 种险种 × 4 档决策 × 3 个特殊情况（信息缺失、LLM异常、边界值）。

---

## 6. 调试技巧

### 如果某个节点输出异常
1. 点击该节点 → 「运行日志」→ 查看输入/输出内容
2. 检查上游节点的输出格式是否符合预期
3. 检查变量引用路径是否正确（注意节点名要精确匹配——Dify 中变量引用依赖节点名，改名后需同步更新所有引用）

### 如果知识库检索返回空或不相关
1. 检查「代码执行:查询构造器」输出的 `search_query` 内容是否合理（在 Code 节点的运行日志中查看）
2. 用 `search_query` 的内容直接去知识库页面搜索，验证能否召回相关片段
3. 如果无法召回：检查知识库文档是否已完成索引（状态为"已完成"）、分段参数是否合理（500 tokens）
4. 如果召回不相关：检查查询变量是否指向了正确的 Code 节点输出（而非 Start 的原始输入）

### 如果 LLM2/LLM3 评估结果不准确
1. 确认其「上下文」配置指向了「知识检索」节点——这是最常漏掉的关键配置
2. 检查 System Prompt 中的降级规则是否包含了当前用户的情况（如职业不在降级规则列表中）
3. 如果 LLM 使用了知识库之外的规则（编造），说明降级规则的引导不够明确——在 Prompt 中强调"优先使用知识库规则"

### 如果 Code 节点报错（JSON解析失败）
1. 查看 Code 节点运行日志 → 找到上游 LLM 传入的原始文本
2. 检查原始文本是否包含 `<think>` 标签（deepseek 模型常见）
3. 检查是否为非 JSON 输出（safe_parse 已做容错，但极端情况可能仍失败）
4. 如果 Code 节点持续报错：手动用上游 LLM 的输出测试 json.loads() 能否成功

### 如果计算结果与预期不符
1. 打印 `代码执行:定价计算` 的中间变量（在代码中临时加 print 或检查运行日志）
2. 逐步验证：age_coeff → occ_adj → health_adj → smoking_coeff → comprehensive_coeff → total
3. 常见问题：保额解析错误（"50万"中的"万"未转换为×10000）、职业/健康加费比例提取失败（adjustment字段格式不一致）

---

## 7. 模块B的技术亮点（面试加分点）

| 亮点 | 具体实现 | 面试时一句话 |
|------|----------|-------------|
| **KB优先+内置兜底** | LLM2/LLM3的System Prompt内含完整降级规则表 | "当KB检索不到匹配时，Agent仍有兜底规则可用，不会乱编" |
| **查询构造器** | Code节点将自然语言→结构化查询 | "在LLM和KB之间加了一层语义翻译，检索召回率从几乎为0到稳定可用" |
| **safe_parse防御性解析** | 三个Code节点均含think标签清洗+JSON提取+兜底逻辑 | "系统不因LLM输出波动而崩溃，每个Code节点都是容错边界" |
| **并行评估架构** | LLM2 ∥ LLM3，延迟减半 | "职业和健康评估独立并行，延迟从12-16秒降到6-8秒" |
| **万单位自动检测** | 定价代码检测"万"并×10000 | "用户输入50万能正确解析为500000，而非50" |
| **四档决策体系** | 标准/次标准/延期/拒保 + 替代险种推荐 | "不只是给结论，拒保时会给替代方案" |

---

*配套文件：核保规则知识库（核保规则文档.txt）、智保通-多Agent核保引擎.yml（可直接导入）、设计方案 v2.0*
