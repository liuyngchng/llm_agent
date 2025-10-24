#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import random
import pymysql
from decimal import Decimal
from faker import Faker
from datetime import datetime
from sys_init import init_yml_cfg
from cn_areas import get_random_region

fake = Faker('zh_CN')
start_date = datetime(2022, 1, 1)
end_date = datetime(2025, 5, 1)

# 常量定义
METER_MANUFACTURERS = [
    '重庆埃创', '安徽鸿凌', '成都千嘉', '成都秦川', '昆明先锋', '重庆精益', '重庆明光',
    '重庆克罗姆', '重庆市界', '重庆山城', '重庆西美', '丹东热工', '杭州贝特', '杭州先锋',
    '河南新天', '江苏中威', '江阴宏源', '廊坊新奥', '辽宁思凯', '辽宁航宇星', '南京中元',
    '青岛积成', '上海克罗姆', '上海真兰', '四川海力', '浙江苍南', '浙江金卡', '浙江蓝宝石',
    '浙江荣鑫', '浙江松川', '浙江威星', '浙江正泰', '河南新开普', '四川鹏翔', '承德博冠',
    '宁夏隆基', '西安旌旗', '金凤来仪', '济南瑞泉', '湖南瑞锋', '航天动力', '上海飞奥',
    '重庆瑞力比', '河北华通', '新奥', '山东建安', '郑州安然', '优艾特', '辽宁安然燃气表',
    '山西华腾', '湖南威铭', '上海罗美特', '天津新科', '大连爱知时', '宁波鹏盛', '浙江天信',
    '重庆神缘智能', '廊坊润能', '郑州引领', '交大瑞森', '上海功尊', '上海众德', '深圳友讯达',
    '上海中核维思', '北京慧源泰', '昆仑数智DTU', '裕顺仪表', '上海埃科', '信东仪表', '宁波创盛',
    '山东思达特'
]
METER_TYPE_MAP = {0: '基表/流量计', 1: 'IC卡表/流量计', 2: '远传表/流量计'}
USER_TYPE_MAP = {0: '居民用户', 1: '非居民用户'}


def generate_data(db_cfg: dict, total=500000, batch_size=5000):
    conn = pymysql.connect(**db_cfg)
    cursor = conn.cursor()

    SQL = """INSERT INTO gas_consume_info (
        gas_consume_id, user_id, user_name, meter_id, meter_manufacture, 
        gas_meter_type, gas_consume_amount, province, city, district, 
        company, user_type, record_time
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    try:
        for i in range(total // batch_size):
            batch = [generate_consume_record() for _ in range(batch_size)]
            cursor.executemany(SQL, batch)
            conn.commit()
            print(f'已提交 {(i + 1) * batch_size} 条数据')
    finally:
        cursor.close()
        conn.close()


def generate_consume_record() -> tuple:
    record_time = fake.date_between(start_date, end_date)
    province, city, district = get_random_region("../Administrative-divisions-of-China-2.7.0/dist/data.sqlite")
    user_type = random.choice([0, 1])

    # 用气量根据用户类型区分范围（居民用户用气量小，工业用户用气量大）
    amount_range = (0.1, 2) if user_type == 0 else (10, 100)

    return (
        f"GAS_{fake.unique.random_number(digits=10)}",  # 用气流水号
        f"USR_{random.randint(10000000, 99999999)}",  # 用户ID
        fake.name(),  # 用户姓名
        f"MT_{fake.unique.random_number(digits=8)}",  # 燃气表ID
        random.choice(METER_MANUFACTURERS),  # 制造商
        random.choice(list(METER_TYPE_MAP.keys())),  # 表具类型
        float(Decimal(random.uniform(*amount_range)).quantize(Decimal('0.000'))),  # 用气量
        province,  # 省
        city,  # 市
        district,  # 区县
        f"{province}{random.choice(['燃气', '能源', '天然气'])}公司",  # 燃气公司
        user_type,  # 用户类型
        record_time  # 记录时间
    )


if __name__ == '__main__':
    cfg = init_yml_cfg()['db']
    db_cfg = {
        'host': cfg['host'],
        'port': cfg['port'],
        'user': cfg['user'],
        'password': cfg['password'],
        'db': cfg['name'],
        'charset': 'utf8mb4'
    }
    generate_data(db_cfg)