"""
InsureFlow 全链路编排脚本
==========================
替代 Dify HTTP Request 节点，用 Python 实现三模块 API 级联调用。
解决 Dify Cloud 沙箱禁止 HTTP 节点出站请求的问题。

用法：
  1. 填写下方三个模块的 API Key
  2. python insureflow_orchestrator.py
  3. 按提示输入个人信息和保险需求

面试价值：
  - 展示 API Gateway + Service Orchestrator 模式的实现能力
  - 展示对 Dify 平台限制的定位与替代方案设计能力
"""

import json
import sys
import time
import urllib.request
import urllib.error

# ============================================================
# 配置区 —— 替换为你的三个模块 API Key
# ============================================================
DIFY_BASE_URL = "https://cloud.dify.ai"

API_KEY_MODULE_A = "app-xxxxxxxxxxxxx"  # 智保通-智能产品配置助手
API_KEY_MODULE_B = "app-xxxxxxxxxxxxx"  # 智保通-多Agent核保引擎
API_KEY_MODULE_C = "app-xxxxxxxxxxxxx"  # 智保通-智能保单管家

# ============================================================
# 工具函数
# ============================================================

def call_dify_workflow(api_key: str, inputs: dict, user: str = "insureflow") -> dict:
    """调用 Dify Workflow API，blocking 模式，返回完整响应 JSON"""
    url = f"{DIFY_BASE_URL}/v1/workflows/run"
    body = json.dumps({
        "inputs": inputs,
        "response_mode": "blocking",
        "user": user,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"_error": True, "http_status": e.code, "body": body[:500]}
    except Exception as e:
        return {"_error": True, "exception": str(e)}


def safe_get_outputs(resp: dict) -> dict:
    """安全提取 Dify 响应中的 outputs"""
    if resp.get("_error"):
        return resp
    data = resp.get("data", {})
    return data.get("outputs", {})


# ============================================================
# 步骤 1：获取用户输入
# ============================================================

def get_user_input() -> str:
    """交互式获取用户输入，也支持命令行参数直接传入"""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])

    print("=" * 60)
    print("  InsureFlow 全链路智能保险中台")
    print("  产品配置 → 核保决策 → 保单服务")
    print("=" * 60)
    print()
    print("请输入你的个人信息和保险需求（输入完成后按 Ctrl+Z 回车）：")
    print()
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines)


# ============================================================
# 步骤 2：构造模块A请求 —— 产品配置
# ============================================================

def build_module_a_prompt(user_input: str) -> str:
    """将原始用户输入整理为产品需求描述"""
    return (
        f"请根据以下用户需求，配置一款合适的保险产品：\n\n"
        f"{user_input}\n\n"
        f"请输出产品定义JSON、产品说明书、产品摘要。"
    )


# ============================================================
# 步骤 3：构造模块B请求 —— 核保评估
# ============================================================

def build_module_b_input(user_input: str, product_brief_json: str) -> str:
    """基于用户信息和产品参数，构造核保咨询文本"""
    base = user_input
    if product_brief_json:
        try:
            brief = json.loads(product_brief_json) if isinstance(product_brief_json, str) else product_brief_json
            product_name = brief.get("product_name", brief.get("产品名称", ""))
            sum_assured = brief.get("sum_assured_range", brief.get("保额范围", ""))
            waiting_period = brief.get("waiting_period", brief.get("等待期", ""))
            product_info = f"\n\n【已配置产品信息】\n产品名称：{product_name}\n保额范围：{sum_assured}\n等待期：{waiting_period}"
            return base + product_info
        except (json.JSONDecodeError, TypeError):
            pass
    return base


# ============================================================
# 步骤 4：构造模块C请求 —— 保单服务
# ============================================================

def build_module_c_input(user_input: str, uw_report: str, product_brief_json: str) -> str:
    """基于核保结论和产品信息，构造保单咨询文本"""
    inquiry = "请根据以下信息，提供保单服务指引（条款解读、理赔流程、续保规则）：\n\n"
    inquiry += f"用户情况：{user_input[:300]}\n\n"

    if product_brief_json:
        try:
            brief = json.loads(product_brief_json) if isinstance(product_brief_json, str) else product_brief_json
            product_name = brief.get("product_name", brief.get("产品名称", "该产品"))
            inquiry += f"关联产品：{product_name}\n"
        except (json.JSONDecodeError, TypeError):
            pass

    if uw_report:
        inquiry += f"\n核保结论摘要：{uw_report[:500]}\n"

    return inquiry


# ============================================================
# 主流程
# ============================================================

def main():
    # 检查 API Key 是否已配置
    unconfigured = []
    if "xxx" in API_KEY_MODULE_A:
        unconfigured.append("API_KEY_MODULE_A")
    if "xxx" in API_KEY_MODULE_B:
        unconfigured.append("API_KEY_MODULE_B")
    if "xxx" in API_KEY_MODULE_C:
        unconfigured.append("API_KEY_MODULE_C")
    if unconfigured:
        print("❌ 以下 API Key 未配置，请先填写脚本中的配置区：")
        for k in unconfigured:
            print(f"   - {k}")
        sys.exit(1)

    user_input = get_user_input()
    if not user_input.strip():
        print("❌ 输入为空，退出。")
        sys.exit(1)

    print("\n" + "─" * 50)
    print("🚀 开始全链路编排...\n")

    # ── 阶段1：产品配置 ──
    print("【阶段 1/3】调用智能产品配置助手...")
    t1 = time.time()
    resp_a = call_dify_workflow(API_KEY_MODULE_A, {
        "product_requirement": build_module_a_prompt(user_input)
    })
    outputs_a = safe_get_outputs(resp_a)
    elapsed_a = time.time() - t1

    product_brochure_md = outputs_a.get("product_brochure_md", "")
    product_brief_json = outputs_a.get("product_brief_json", "{}")
    product_definition_json = outputs_a.get("product_definition_json", "{}")
    status_a = outputs_a.get("status", "unknown")

    if outputs_a.get("_error"):
        print(f"  ❌ 模块A 调用失败: {outputs_a}")
        product_brochure_md = "[模块A调用失败]"
        product_brief_json = "{}"
        status_a = "error"
    else:
        print(f"  ✅ 模块A 完成 ({elapsed_a:.1f}s) — 产品状态: {status_a}")

    # ── 阶段2：核保评估 ──
    print("【阶段 2/3】调用多Agent核保引擎...")
    insure_inquiry = build_module_b_input(user_input, product_brief_json)
    t2 = time.time()
    resp_b = call_dify_workflow(API_KEY_MODULE_B, {
        "INSURE_inquiry": insure_inquiry,
        "product_context_json": product_brief_json,
    })
    outputs_b = safe_get_outputs(resp_b)
    elapsed_b = time.time() - t2

    uw_report = outputs_b.get("OUTPUT", "")
    if outputs_b.get("_error"):
        print(f"  ❌ 模块B 调用失败: {outputs_b}")
        uw_report = "[模块B调用失败]"
    else:
        print(f"  ✅ 模块B 完成 ({elapsed_b:.1f}s)")

    # ── 阶段3：保单服务 ──
    print("【阶段 3/3】调用智能保单管家...")
    policy_inquiry = build_module_c_input(user_input, uw_report, product_brief_json)
    t3 = time.time()
    resp_c = call_dify_workflow(API_KEY_MODULE_C, {
        "policy_inquiry": policy_inquiry,
    })
    outputs_c = safe_get_outputs(resp_c)
    elapsed_c = time.time() - t3

    policy_response = outputs_c.get("OUTPUT", "")
    if outputs_c.get("_error"):
        print(f"  ❌ 模块C 调用失败: {outputs_c}")
        policy_response = "[模块C调用失败]"
    else:
        print(f"  ✅ 模块C 完成 ({elapsed_c:.1f}s)")

    total_time = time.time() - t1

    # ── 汇总报告 ──
    print("\n" + "=" * 60)
    print("  InsureFlow 全链路报告")
    print("=" * 60)

    print(f"\n{'─' * 40}")
    print("📋 阶段一：产品配置")
    print(f"{'─' * 40}")
    print(product_brochure_md[:2000] if product_brochure_md else "(无输出)")

    print(f"\n{'─' * 40}")
    print("🩺 阶段二：智能核保")
    print(f"{'─' * 40}")
    print(uw_report[:2000] if uw_report else "(无输出)")

    print(f"\n{'─' * 40}")
    print("🛡️ 阶段三：保单服务")
    print(f"{'─' * 40}")
    print(policy_response[:2000] if policy_response else "(无输出)")

    print(f"\n{'─' * 40}")
    print("📊 执行摘要")
    print(f"{'─' * 40}")
    print(f"  模块A 耗时: {elapsed_a:.1f}s | 状态: {status_a}")
    print(f"  模块B 耗时: {elapsed_b:.1f}s")
    print(f"  模块C 耗时: {elapsed_c:.1f}s")
    print(f"  全链路总耗时: {total_time:.1f}s")
    print(f"  三阶段状态: A={status_a} | B={'✅' if uw_report and '失败' not in str(uw_report) else '⚠️'} | C={'✅' if policy_response and '失败' not in str(policy_response) else '⚠️'}")

    # 也输出一份 JSON，方便后续处理
    json_output = {
        "phase_a": {
            "status": status_a,
            "product_definition_json": product_definition_json,
            "product_brochure_md": product_brochure_md[:500],
            "elapsed_s": round(elapsed_a, 1),
        },
        "phase_b": {
            "uw_report": uw_report[:800] if isinstance(uw_report, str) else str(uw_report)[:800],
            "elapsed_s": round(elapsed_b, 1),
        },
        "phase_c": {
            "policy_response": policy_response[:800] if isinstance(policy_response, str) else str(policy_response)[:800],
            "elapsed_s": round(elapsed_c, 1),
        },
        "total_elapsed_s": round(total_time, 1),
    }

    output_file = "insureflow_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 完整JSON结果已保存至: {output_file}")

    print("\n✅ 全链路执行完毕。")


if __name__ == "__main__":
    main()
