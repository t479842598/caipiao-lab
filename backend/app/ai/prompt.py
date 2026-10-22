"""把预测凭据压成结构化 prompt：确定性统计先算好，LLM 只做解读。"""

from __future__ import annotations

import json
from typing import Any

from ..games import get_game

SYSTEM = (
    "你是一名彩票数据分析师。用户会给你一份来自统计模型的结构化预测凭据，"
    "包含频率、遗漏、马尔可夫转移、贝叶斯后验和机器学习模型给出的边际概率，以及若干注号码。\n"
    "请完成三件事：\n"
    "1. 用中文解释这份凭据说明了什么（哪些号码被模型偏好、为什么）。\n"
    "2. 对给出的号码做结构性点评（奇偶、大小、和值、跨度、区间分布、连号），指出问题。\n"
    "3. 给出 2-4 条可执行的选号建议。\n"
    "硬性要求：明确说明彩票每期独立同分布、历史数据不改变下一期的真实概率，"
    "任何模型都只是对随机序列的描述而非预测力，不要暗示存在必然规律，不要承诺中奖。"
    "不要使用 Markdown 标题层级，用短段落和短列表，控制在 600 字内。"
)


def build_payload(game: str, insight: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    spec = get_game(game)
    tickets = prediction.get("tickets") or []
    return {
        "彩种": spec.name,
        "目标期号": prediction.get("target_issue") or insight.get("target_issue"),
        "基于期号": prediction.get("based_on") or insight.get("based_on"),
        "历史期数": insight.get("draws"),
        "引擎": prediction.get("engine"),
        "策略": prediction.get("strategy"),
        "窗口": prediction.get("window"),
        "冷热": {
            "最热": insight.get("hot", [])[:8],
            "最冷": insight.get("cold", [])[:8],
        },
        "遗漏前列": insight.get("omission_top", [])[:8],
        "结构分布": insight.get("structure", {}),
        "随机性检验": insight.get("randomness", ""),
        "号码边际概率": (prediction.get("marginals") or [])[:1],
        "推荐号码": [
            {"序号": t.get("index"), "红/主": t.get("numbers", {}).get("red"),
             "蓝/次": t.get("numbers", {}).get("blue"), "评分": t.get("score")}
            for t in tickets
        ],
    }


def build_user_message(payload: dict[str, Any], question: str = "") -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    text = "以下是模型给出的预测凭据（JSON）：\n" + body
    if question:
        text += "\n\n用户额外的问题：" + question.strip()[:500]
    return text


def fallback_answer(payload: dict[str, Any]) -> str:
    """没有可用 AI 供应商时的本地解读，保证接口永远有内容返回。"""
    hot = payload.get("冷热", {}).get("最热", [])
    cold = payload.get("冷热", {}).get("最冷", [])
    struct = payload.get("结构分布", {}) or {}
    lines = [
        f"本次以 {payload.get('历史期数')} 期历史为样本，目标期 {payload.get('目标期号')}。",
        "热号（近窗口出现最多）：" + "、".join(str(h.get("n")) for h in hot[:6] if isinstance(h, dict)) if hot else "热号：样本不足",
        "冷号（近窗口出现最少）：" + "、".join(str(c.get("n")) for c in cold[:6] if isinstance(c, dict)) if cold else "冷号：样本不足",
    ]
    odd = struct.get("odd")
    if isinstance(odd, dict):
        lines.append("奇偶比峰值：" + str(odd.get("mode", "—")))
    total = struct.get("sum")
    if isinstance(total, dict):
        lines.append("和值区间：" + f"{total.get('min', '—')} ~ {total.get('max', '—')}")
    lines.append("提醒：彩票每期独立同分布，历史频率不改变下一期真实概率，以上仅为统计描述。")
    return "\n".join(lines)
