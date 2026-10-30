# -*- coding: utf-8 -*-
"""模型包：集中导入，保证 Base.metadata 注册完整"""
from app.models.agent import AgentPendingAction, AgentStepLog  # noqa: F401
from app.models.change import (  # noqa: F401
    Briefing,
    ChangeOrder,
    ChangeVersion,
    Project,
    VisaOrder,
)
from app.models.chat import ChatMessage, ChatSession  # noqa: F401
from app.models.expense import ExpenseDraft  # noqa: F401
from app.models.policy import PolicyChunk, PolicyDocument  # noqa: F401
from app.models.prompt import PromptTemplate  # noqa: F401
from app.models.user import User  # noqa: F401
