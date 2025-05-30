#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip install faker pymysql
"""

import random
import pymysql
from decimal import Decimal
from faker import Faker
from datetime import datetime, timedelta
from sys_init import init_yml_cfg

# MySQL配置
# DB_CONFIG = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': 'yourpassword',
#     'db': 'gas_data',
#     'charset': 'utf8mb4'
# }

DB_CONFIG = {}

fake = Faker('zh_CN')
start_date = datetime(2022, 1, 1)
end_date = datetime(2025, 5, 1)

# 预定义枚举值
ACCOUNT_TYPES = ['居民天然气', '非居民天然气']
CUSTOMER_TYPES = ['居民', '非居民']
ID_TYPES = ['身份证', '护照', '台湾通行证', '港澳通行证', '军官证', '营业执照', '无证件', '租房合同']


def generate_data(db_cfg: dict, total=100000, batch_size=1000,):
    conn = pymysql.connect(**db_cfg)
    cursor = conn.cursor()

    SQL = """INSERT INTO user_info (
        data_id,province,city,district,company,account_type,year,month,day,
        payment,payment_unit,gas_usage,gas_unit,new_users,new_users_unit,
        new_accounts,new_accounts_unit,new_meters,new_meters_unit,balance,
        balance_unit,id_type,customer_type,meter_type,low_income_households,
        discount_households,rate_policy,location_type,blacklist_users,
        closed_accounts,closed_accounts_unit,insured_users,residence_type,
        special_user_type
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

    try:
        for _ in range(total // batch_size):
            batch = []
            for _ in range(batch_size):
                date = fake.date_between(start_date, end_date)
                province = fake.province()[:3]

                record = (
                    f"{date:%Y%m%d}-{random.randint(10000, 99999)}-{province}-{random.choice(ACCOUNT_TYPES)}",
                    # data_id
                    province,  # 省
                    fake.city(),  # 市
                    fake.district(),  # 区县
                    f"{fake.company_prefix()}燃气公司",  # 公司名称
                    random.choice(ACCOUNT_TYPES),  # 账户类型
                    date.year, date.month, date.day,  # 年月日
                    float(Decimal(random.uniform(100, 100000)).quantize(Decimal('0.00'))),  # 支付金额
                    '元',  # 支付单位
                    float(Decimal(random.uniform(10, 1000)).quantize(Decimal('0.000'))),  # 用气量
                    random.choice(['方', '立方米']),  # 用气单位
                    random.randint(0, 50), '户',  # 新增用户
                    random.randint(0, 50), '个',  # 新增账户
                    random.randint(0, 50), '个',  # 新增表具
                    float(Decimal(random.uniform(0, 1000000)).quantize(Decimal('0.00'))),  # 当前余额
                    '元',  # 余额单位
                    random.choice(ID_TYPES),  # 证件类型
                    random.choice(CUSTOMER_TYPES),  # 客户类型
                    random.choice(['基表/流量计', 'IC卡表/流量计', '远传表/流量计']),  # 表具类型
                    random.randint(0, 100),  # 低保户
                    random.randint(0, 100),  # 优惠户
                    f"价格{random.choice([2.5, 3.0, 3.5, 4.0])}元/方",  # 费率
                    random.choice(['楼房', '平房', '别墅', '工厂', '其它']),  # 地点类型
                    random.randint(0, 50),  # 黑名单
                    random.randint(0, 20), '个',  # 销户
                    random.randint(0, 200),  # 保险用户
                    random.choice(['自住', '租赁', '群租', '其它']),  # 住宿类型
                    random.choice(['正常', '学校', '医院', '大排档', '政府机关'])  # 特殊用户
                )
                batch.append(record)

            cursor.executemany(SQL, batch)
            conn.commit()
            print(f'已提交 {(_ + 1) * batch_size} 条数据')

    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    my_cfg = init_yml_cfg()['db']
    my_db_cfg = {
        'host': my_cfg['host'],
        'port': my_cfg['port'],
        'user': my_cfg['user'],
        'password': my_cfg['password'],
        'db': my_cfg['name'],
        'charset': 'utf8mb4'
    }
    print(f"my_db_cfg {my_db_cfg}")
    generate_data(my_db_cfg)