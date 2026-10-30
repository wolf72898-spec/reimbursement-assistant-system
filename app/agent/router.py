# -*- coding: utf-8 -*-
"""
意图路由：判断用户想"制度问答"还是"发起报销"。
一期用关键词规则（快、零成本、可解释）；二期叠加 LLM 兜底分类。
对应架构方案 app/agent/router.py。
"""
import re

# 命中即认为是报销意图
_EXPENSE_PATTERNS = re.compile(r"报销|发票|票据|贴票|报账")


def classify_intent(question: str) -> str:
    """
    返回 "expense"（发起报销）或 "qa"（制度问答）。
    """
    if _EXPENSE_PATTERNS.search(question):
        return "expense"
    return "qa"
