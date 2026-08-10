#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码安全工具 — bcrypt 哈希、验证、密码复杂度校验。
对标 Go 版本 internal/store/crypto.go
"""
import bcrypt

# bcrypt 计算成本，12 是当下推荐的安全值（约 300ms/次）
BCRYPT_COST = 12

# 最小密码长度
MIN_PASSWORD_LEN = 6


def hash_password(password: str) -> str:
    """使用 bcrypt 对密码做哈希"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_COST)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码是否匹配哈希"""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def validate_password(password: str) -> None:
    """验证密码复杂度：长度至少 6 个字符"""
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"密码长度至少 {MIN_PASSWORD_LEN} 个字符")