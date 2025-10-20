#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

from pydantic import BaseModel

class BMIResult(BaseModel):
    bmi: float
    category: str
    weight_kg: float
    height_m: float

def calculate_bmi(weight_kg: float, height_m: float) -> BMIResult:
    """计算身体质量指数(BMI)"""
    bmi = weight_kg / (height_m ** 2)

    if bmi < 18.5:
        category = "偏瘦"
    elif bmi < 24:
        category = "正常"
    elif bmi < 28:
        category = "超重"
    else:
        category = "肥胖"

    bmi_result = BMIResult(
        bmi=round(bmi, 2),
        category=category,
        weight_kg=weight_kg,
        height_m=height_m
    )
    return bmi_result