# -*- coding: utf-8 -*-
"""兼容层：编排逻辑已升级为 AgentHarness（harness.py），此处保留旧入口引用"""
from app.agent.harness import (  # noqa: F401
    MAX_ROUNDS,
    _ALLOWED_PROMPTS,
    _PROMPT_DIR,
    load_prompt_text,
    run_agent,
    seed_prompts,
)
