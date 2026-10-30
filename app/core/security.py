# -*- coding: utf-8 -*-
"""
安全工具：密码哈希（PBKDF2，零外部依赖）+ JWT 签发与校验。
说明：PBKDF2-SHA256 迭代 12 万次，骨架阶段够用；上等保时换 bcrypt/argon2。
"""
import hashlib
import hmac
import os
import time
from typing import Optional

import jwt  # PyJWT

from app.core.config import settings

_ITERATIONS = 120_000


def hash_password(plain: str) -> str:
    """PBKDF2 哈希，输出格式: iterations$salt$hexdigest"""
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode(), salt.encode(), _ITERATIONS
    ).hex()
    return f"{_ITERATIONS}${salt}${digest}"


def verify_password(plain: str, stored: str) -> bool:
    """按存储格式拆解后重算比对（恒定时间比较防时序攻击）"""
    try:
        iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", plain.encode(), salt.encode(), int(iters)
        ).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, AttributeError):
        return False


def create_token(user_id: int, role: str) -> str:
    """签发 JWT，角色写入 claims 供权限校验"""
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": int(time.time()) + settings.JWT_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """校验 JWT，过期/伪造返回 None"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
