#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import os
import shutil
from pathlib import Path

# 你的本地模型路径
local_model_path = "/home/rd/workspace/docling-layout-heron"

# docling可能期望的模型路径
# 通常HuggingFace模型缓存在 ~/.cache/huggingface/hub/
cache_dir = Path.home() / '.cache' / 'huggingface' / 'hub'

print("检查模型目录结构...")
print(f"本地模型路径: {local_model_path}")

# 检查本地模型文件
if os.path.exists(local_model_path):
    print("\n本地模型目录内容:")
    for item in os.listdir(local_model_path):
        item_path = os.path.join(local_model_path, item)
        if os.path.isfile(item_path):
            size = os.path.getsize(item_path) / 1024 / 1024
            print(f"  📄 {item} ({size:.1f} MB)")
        else:
            print(f"  📁 {item}/")
else:
    print(f"错误: 模型路径不存在 {local_model_path}")
    exit()

# docling可能使用的模型名称
# 根据docling文档，它可能使用以下模型之一：
# - "ds4sd/docling-layout-heron"
# - "ds4sd/docling-base"
model_name = "ds4sd/docling-layout-heron"

print(f"\ndocling可能需要的模型: {model_name}")

# 创建HuggingFace缓存目录结构
cache_model_dir = cache_dir / f"models--{model_name.replace('/', '--')}"
cache_model_dir.mkdir(parents=True, exist_ok=True)

print(f"HuggingFace缓存路径: {cache_model_dir}")

# 复制模型文件到缓存目录
print("\n复制模型文件到缓存目录...")
try:
    # 检查缓存目录是否已经有内容
    if os.listdir(cache_model_dir):
        print(f"缓存目录已有内容，跳过复制")
    else:
        # 复制所有文件
        for item in os.listdir(local_model_path):
            src = os.path.join(local_model_path, item)
            dst = os.path.join(cache_model_dir, item)

            if os.path.isfile(src):
                shutil.copy2(src, dst)
                print(f"  复制: {item}")
            else:
                shutil.copytree(src, dst, dirs_exist_ok=True)
                print(f"  复制目录: {item}/")

        # 创建必要的HuggingFace元数据文件
        snapshot_file = cache_model_dir / "snapshots" / "main"
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)

        # 创建refs文件
        refs_dir = cache_model_dir / "refs"
        refs_dir.mkdir(exist_ok=True)
        with open(refs_dir / "main", "w") as f:
            f.write("main")

        print("✓ 模型复制完成")

except Exception as e:
    print(f"✗ 复制失败: {e}")

# 现在运行docling
print("\n" + "=" * 60)
print("运行docling...")
print("=" * 60)

from docling.document_converter import DocumentConverter

# 设置环境变量
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HOME'] = str(cache_dir)

converter = DocumentConverter()
result = converter.convert("/home/rd/Downloads/1.png")
print(result.document.export_to_markdown())