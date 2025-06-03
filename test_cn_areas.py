#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3


def get_random_region(db_path='data.sqlite'):
    """
    从SQLite数据库随机获取一个省市区三级对应正确的组合
    :param db_path: SQLite数据库文件路径
    :return: (province, city, county) 元组
    """
    with sqlite3.connect(db_path) as conn:
        try:
            # 连接数据库
            cursor = conn.cursor()
            # 1. 随机选择一个省
            cursor.execute("SELECT code, name FROM province ORDER BY RANDOM() LIMIT 1")
            province = cursor.fetchone()
            if not province:
                raise ValueError("省级数据表 province 中没有数据")
            p_code, p_name = province
            # 2. 在该省下随机选择一个地级市
            cursor.execute(
                "SELECT code, name FROM city WHERE provinceCode = ? ORDER BY RANDOM() LIMIT 1",
                (p_code,)
            )
            city = cursor.fetchone()
            if not city:
                raise ValueError(f"在市级数据表 city 中没有省级编码为 {p_code} 的地级市数据")
            c_code, c_name = city

            # 3. 在该地级市下随机选择一个区县
            cursor.execute(
                "SELECT name FROM area WHERE cityCode = ? ORDER BY RANDOM() LIMIT 1",
                (c_code,)
            )
            county = cursor.fetchone()
            if not county:
                raise ValueError(f"在区县数据表 area 中没有地级市编码为 {c_code} 的区县数据")

            return p_name, c_name, county[0]

        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return None


# 示例使用
if __name__ == "__main__":
    db_file = "../Administrative-divisions-of-China-2.7.0/dist/data.sqlite"
    result = get_random_region(db_file)

    if result:
        p, cit, cty = result
        print("\n随机生成的省市区组合：")
        print(f"{p} {cit} {cty}")
    else:
        print("未能生成省市区组合")
