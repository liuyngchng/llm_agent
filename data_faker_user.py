#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import random
import pymysql
from decimal import Decimal
from faker import Faker
from datetime import datetime
# 注意：需确保sys_init和cn_areas模块存在
from sys_init import init_yml_cfg
from cn_areas import get_random_region

fake = Faker('zh_CN')
start_date = datetime(2022, 1, 1)
end_date = datetime(2025, 5, 1)

# 枚举值映射字典
USER_TYPE_MAP = {'居民天然气': 0, '非居民天然气': 1}
ID_TYPE_MAP = {
    '身份证': 0, '护照': 1, '台湾通行证': 2, '港澳通行证': 3,
    '军官证': 4, '营业执照': 5, '无证件': 6, '租房合同': 7
}
METER_TYPE_MAP = {
    '基表/流量计': 0, 'IC卡表/流量计': 1, '远传表/流量计': 2
}
RESIDENCE_TYPE_MAP = {'自住': 0, '租赁': 1, '群租': 2, '其它': 3}
ARCHITECTURE_TYPE_MAP = {
    '楼房': 0, '平房': 1, '别墅': 2, '工厂': 3, '其它': 4
}


def generate_data(db_cfg: dict, total=500000, batch_size=2000):
    conn = pymysql.connect(**db_cfg)
    cursor = conn.cursor()

    SQL = """INSERT INTO user_info (
        user_id, user_name, contact, family_members, province, city, district, 
        company, user_type, create_time, id_type, meter_type, residence_type, 
        residence_tag, architecture_type, gas_usage, balance, is_low_income, 
        is_discount, rate_policy, is_in_blacklist, is_closed, is_insured
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    try:
        for i in range(total // batch_size):
            batch = []
            for _ in range(batch_size):
                batch.append(get_fake_record())
            cursor.executemany(SQL, batch)
            conn.commit()
            print(f'已提交 {(i + 1) * batch_size} 条数据')
    finally:
        cursor.close()
        conn.close()


def get_fake_record() -> tuple:
    create_time = fake.date_between(start_date, end_date)
    province, city, district = get_random_region("../Administrative-divisions-of-China-2.7.0/dist/data.sqlite")

    # 随机生成关键字段
    user_id = f"USR_{fake.unique.random_number(digits=8)}"
    user_name = fake.name()
    contact = fake.phone_number()
    family_members = random.randint(1, 5)

    # 公司名称（简化处理）
    company = f"{province}{city}{random.choice(['燃气', '能源', '天然气'])}有限公司"

    # 类型字段映射
    account_type_str = random.choice(['居民天然气', '非居民天然气'])
    user_type = USER_TYPE_MAP[account_type_str]
    id_type = ID_TYPE_MAP[random.choice(list(ID_TYPE_MAP.keys()))]
    meter_type = METER_TYPE_MAP[random.choice(list(METER_TYPE_MAP.keys()))]
    residence_type = RESIDENCE_TYPE_MAP[random.choice(list(RESIDENCE_TYPE_MAP.keys()))]
    architecture_type = ARCHITECTURE_TYPE_MAP[random.choice(list(ARCHITECTURE_TYPE_MAP.keys()))]

    # 特殊字段处理
    residence_tag = random.choice([
        None,  # 允许NULL
        *list(range(0, 22))  # 0-21的整数
    ])

    return (
        user_id, user_name, contact, family_members,
        province, city, district, company, user_type,
        create_time, id_type, meter_type, residence_type,
        residence_tag, architecture_type,
        float(Decimal(random.uniform(10, 1000)).quantize(Decimal('0.000'))),  # gas_usage
        float(Decimal(random.uniform(0, 10000)).quantize(Decimal('0.00'))),  # balance
        random.randint(0, 1),  # is_low_income
        random.randint(0, 1),  # is_discount
        f"{random.choice([2.5, 3.0, 3.5])}元/方",  # rate_policy
        random.randint(0, 1),  # is_in_blacklist
        random.randint(0, 1),  # is_closed
        random.randint(0, 1)  # is_insured
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