#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
向量库工具函数
"""
import os
import hashlib
from typing import Optional, List, Dict, Any, Callable
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_file_path(file_path: str) -> bool:
    """验证文件路径是否存在且可读"""
    if not file_path or not isinstance(file_path, str):
        return False

    path = Path(file_path)
    return path.exists() and path.is_file() and os.access(path, os.R_OK)


def get_file_hash(file_path: str, algorithm: str = "md5") -> str:
    """计算文件哈希值"""
    hash_func = hashlib.new(algorithm)

    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path}, 错误: {e}")
        return ""


def ensure_directory(directory: str) -> bool:
    """确保目录存在"""
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {directory}, 错误: {e}")
        return False


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名（不带点）"""
    return Path(file_path).suffix.lstrip('.').lower()


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_get(dictionary: Dict, *keys, default=None):
    """安全获取嵌套字典的值"""
    current = dictionary
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def format_file_size(bytes_size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f}TB"


def timeit(func: Callable):
    """计时装饰器"""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        logger.debug(f"函数 {func.__name__} 执行时间: {elapsed:.4f}秒")
        return result

    return wrapper


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, total: int, description: str = "处理进度"):
        self.total = total
        self.description = description
        self.completed = 0
        self.start_time = time.time()

    def update(self, increment: int = 1):
        """更新进度"""
        self.completed += increment

        if self.total > 0:
            percent = (self.completed / self.total) * 100
            elapsed = time.time() - self.start_time

            # 计算预估剩余时间
            if self.completed > 0:
                eta = (elapsed / self.completed) * (self.total - self.completed)
                eta_str = f"ETA: {eta:.1f}秒"
            else:
                eta_str = "ETA: 计算中..."

            logger.info(f"{self.description}: {percent:.1f}% ({self.completed}/{self.total}) {eta_str}")


import time