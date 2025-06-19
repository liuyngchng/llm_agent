#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import sqlite3  # 改为SQLite
from decimal import Decimal
from faker import Faker
from datetime import datetime

# 移除pymysql相关导入
from cn_areas import get_random_region

fake = Faker('zh_CN')
start_date = datetime(2022, 1, 1)
end_date = datetime(2025, 6, 1)

# 常量定义
CHARGE_CHANNEL = ['微信', '支付宝', '微信公众号', '营业厅']
SKU_TYPE = ['居民天然气', '非居民天然气']
EAST_PROVINCES = ['北京', '天津', '河北', '辽宁', '上海', '江苏', '浙江', '福建', '山东', '广东', '海南']


def generate_data(db_file='test1.db', total=500000, batch_size=5000):
    # 使用SQLite连接
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 创建表（如果不存在）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        订单ID INTEGER NOT NULL,
        省 TEXT,
        燃气公司 TEXT,
        燃气类型 TEXT,
        年 INTEGER,
        月 INTEGER,
        日 TEXT,
        支付方式 TEXT,
        支付金额 TEXT,
        支付金额单位 TEXT,
        用气量 TEXT,
        用气量单位 TEXT
    )
    ''')
    conn.commit()

    # SQLite使用?作为占位符
    SQL = """INSERT INTO order_info (
        订单ID, 省, 燃气公司, 燃气类型, 
        年, 月, 日, 支付方式, 支付金额, 
        支付金额单位, 用气量, 用气量单位
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

    try:
        for i in range(total // batch_size):
            batch = []
            for _ in range(batch_size):
                batch.append(generate_order_record())
            cursor.executemany(SQL, batch)
            conn.commit()
            print(f'已提交 {(i + 1) * batch_size} 条数据')
    finally:
        cursor.close()
        conn.close()


def generate_order_record() -> tuple:
    create_time = fake.date_between(start_date, end_date)
    province, _, _ = get_random_region("../Administrative-divisions-of-China-2.7.0/dist/data.sqlite")
    year, month = create_time.year, create_time.month

    # 用气量计算（考虑地区/季节）
    is_east = province in EAST_PROVINCES
    is_winter = month in [12, 1, 2]
    is_summer = month in [6, 7, 8]

    base_gas = random.uniform(80, 120)
    if is_east:
        base_gas *= random.uniform(1.5, 2.0)
    else:
        base_gas *= random.uniform(0.5, 0.8)

    if is_winter:
        base_gas *= random.uniform(1.8, 2.5)
    elif is_summer:
        base_gas *= random.uniform(0.4, 0.7)

    gas_volume = round(base_gas, 2)
    unit_price = 3.2 if random.random() > 0.3 else 2.8
    payment = round(gas_volume * unit_price, 2)

    return (
        random.randint(10000000, 99999999),
        province,
        f"{province}{random.choice(['燃气', '新能源', '天然气'])}有限公司",
        random.choice(SKU_TYPE),
        year,
        month,
        create_time.strftime("%Y-%m-%d"),
        random.choice(CHARGE_CHANNEL),
        str(payment),
        "元",
        str(gas_volume),
        "立方米"
    )


if __name__ == '__main__':
    # 直接指定SQLite数据库文件
    generate_data(db_file='test4.db')