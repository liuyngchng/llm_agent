#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
pip install transformers Pillow torch requests
"""
import os

import requests
from transformers import RTDetrV2ForObjectDetection, RTDetrImageProcessor, RTDetrForObjectDetection
import torch
from PIL import Image

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe


def visualize_detection(image, results, threshold=0.6):
    """可视化检测结果"""
    fig, ax = plt.subplots(1, figsize=(15, 10))
    ax.imshow(image)

    table_count = 0
    for result in results:
        for score, label_id, box in zip(result["scores"], result["labels"], result["boxes"]):
            if score.item() < threshold:
                continue

            score_value = round(score.item(), 2)
            label = classes_map[label_id.item()]
            box_coords = box.tolist()

            # 绘制边界框
            x1, y1, x2, y2 = box_coords
            width = x2 - x1
            height = y2 - y1

            # 为不同类别使用不同颜色
            if label == "Table":
                color = 'red'
                table_count += 1
            elif label == "Text":
                color = 'blue'
            elif label == "Form":
                color = 'green'
            else:
                color = 'gray'

            rect = patches.Rectangle((x1, y1), width, height,
                                     linewidth=2, edgecolor=color,
                                     facecolor='none', alpha=0.8)
            ax.add_patch(rect)

            # 添加标签
            label_text = f"{label}: {score_value}"
            text = ax.text(x1, y1 - 5, label_text, fontsize=8,
                           color='white', verticalalignment='top')
            text.set_path_effects([pe.withStroke(linewidth=2, foreground='black')])

            # 在框内显示类别
            ax.text(x1 + width / 2, y1 + height / 2, label,
                    fontsize=9, ha='center', va='center',
                    color='white',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.7))

    plt.title(f'目标检测结果 - 检测到 {table_count} 个表格', fontsize=14)
    plt.axis('off')
    plt.tight_layout()
    plt.show()


classes_map = {
    0: "Caption",
    1: "Footnote",
    2: "Formula",
    3: "List-item",
    4: "Page-footer",
    5: "Page-header",
    6: "Picture",
    7: "Section-header",
    8: "Table",
    9: "Text",
    10: "Title",
    11: "Document Index",
    12: "Code",
    13: "Checkbox-Selected",
    14: "Checkbox-Unselected",
    15: "Form",
    16: "Key-Value Region",
}

#本地模型的目录
model_name = "/home/rd/workspace/docling-layout-heron"
threshold = 0.6

# 检查模型文件是否存在
if not os.path.exists(model_name):
    print(f"模型路径不存在: {model_name}")
    exit()



# 加载本地图片
try:
    image = Image.open("/home/rd/Downloads/1.png")
    image = image.convert("RGB")
except Exception as e:
    print(f"加载图片失败: {e}")
    exit()

# Initialize the model using transformers
try:
    image_processor = RTDetrImageProcessor.from_pretrained(model_name)
    model = RTDetrForObjectDetection.from_pretrained(model_name)
    print("模型加载成功")
except Exception as e:
    print(f"模型加载失败: {e}")
    exit()

# Run the prediction pipeline
inputs = image_processor(images=[image], return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
results = image_processor.post_process_object_detection(
    outputs,
    target_sizes=torch.tensor([image.size[::-1]]),
    threshold=threshold,
)

# Get the results
for result in results:
    for score, label_id, box in zip(
        result["scores"], result["labels"], result["boxes"]
    ):
        score = round(score.item(), 2)
        label = classes_map[label_id.item()]
        box = [round(i, 2) for i in box.tolist()]
        print(f"{label}:{score} {box}")

visualize_detection(image, results, threshold=threshold)