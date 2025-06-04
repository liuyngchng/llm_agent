#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

# 枚举值映射字典
CHARGE_CHANNEL_MAP = {0: '微信', 1: '支付宝', 2: '微信公众号', 3: '营业厅'}
USER_TYPE_MAP = {0: '居民', 1: '非居民/工业用户'}
METER_TYPE_MAP = {0: '基表/流量计', 1: 'IC卡表/流量计', 2: '远传表/流量计'}


def generate_data(db_cfg: dict, total=500000, batch_size=5000):
    conn = pymysql.connect(**db_cfg)
    cursor = conn.cursor()

    # 修改为user_charge_info表的插入语句
    SQL = """INSERT INTO user_charge_info (
        charge_id, user_id, user_name, charge_channel, amount, 
        province, city, district, company, user_type, 
        charge_time, gas_meter_type
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    try:
        for i in range(total // batch_size):
            batch = []
            for _ in range(batch_size):
                batch.append(generate_charge_record())
            cursor.executemany(SQL, batch)
            conn.commit()
            print(f'已提交 {(i + 1) * batch_size} 条数据')
    finally:
        cursor.close()
        conn.close()


def generate_charge_record() -> tuple:
    # 生成充值记录核心字段
    charge_time = fake.date_between(start_date, end_date)
    province, city, district = get_random_region("../Administrative-divisions-of-China-2.7.0/dist/data.sqlite")

    # 生成唯一充值ID（SHA256哈希简化版）
    charge_id = f"CHG_{fake.unique.random_number(digits=10)}"
    user_id = f"USER_{random.randint(10000000, 99999999)}"

    return (
        charge_id,  # 充值流水号
        user_id,  # 用户ID
        fake.name(),  # 用户姓名
        random.choice(list(CHARGE_CHANNEL_MAP.keys())),  # 充值渠道
        float(Decimal(random.uniform(10, 5000)).quantize(Decimal('0.000'))),  # 金额
        province,  # 省
        city,  # 市
        district,  # 区县
        f"{province}{random.choice(['燃气', '新能源', '天然气'])}有限公司",  # 公司
        random.choice(list(USER_TYPE_MAP.keys())),  # 用户类型
        charge_time,  # 充值时间
        random.choice(list(METER_TYPE_MAP.keys()))  # 表具类型
    )


if __name__ == '__main__':
    my_cfg = init_yml_cfg()['db']
    db_cfg = {
        'host': my_cfg['host'],
        'port': my_cfg['port'],
        'user': my_cfg['user'],
        'password': my_cfg['password'],
        'db': my_cfg['name'],
        'charset': 'utf8mb4'
    }
    generate_data(db_cfg)