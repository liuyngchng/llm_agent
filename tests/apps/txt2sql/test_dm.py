#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.
"""
# 编辑 ~/.bashrc 或 ~/.profile
echo 'export DM_HOME=/dm8' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=$DM_HOME/bin:$DM_HOME/drivers/dpi:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
"""
import os
from urllib.parse import urlparse, unquote

import dmPython
import sys


def test_dm_connection():
    try:
        print("Python版本:", sys.version)
        print("尝试连接达梦数据库...")
        print(f"DM_HOME: {os.environ.get('DM_HOME', '未设置')}")
        print(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', '未设置')}")

        db_uri = "dm://SYSDBA:SYSDBA001@127.0.0.1:5236/SYSDBA"
        parsed_uri = urlparse(db_uri)

        conn = dmPython.connect(
            host=unquote(parsed_uri.hostname),
            port=parsed_uri.port or 5236,
            user=unquote(parsed_uri.username),
            password=unquote(parsed_uri.password),
            schema=unquote(parsed_uri.path[1:]) if parsed_uri.path else None,

        )

        # 连接参数 - 请根据实际情况修改
        # conn = dmPython.connect(
        #     user='SYSDBA',
        #     password='SYSDBA001',
        #     server='127.0.0.1',
        #     schema='SYSDBA',
        #     port=5236,
        #     autoCommit=True
        # )

        print("🎉 连接成功！")

        # 执行简单查询
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM V$DATABASE")
        result = cursor.fetchone()
        print(f"数据库状态: 正常，COUNT = {result[0]}")
        cursor.close()
        # 创建表
        cursor = conn.cursor()
        # cursor.execute("DROP TABLE IF EXISTS test_users")
        # print("✅ 表删除成功（如果存在）")
        create_sql ="""
        CREATE TABLE IF NOT EXISTS test_users (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name VARCHAR(50),
            email VARCHAR(100),
            created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        print(f"exec_create_sql, {create_sql}")
        cursor.execute(create_sql)

        # 插入数据
        insert_sql = "INSERT INTO test_users (name, email) VALUES ('测试用户', 'test@example.com')"
        print(f"exec_insert_sql, {insert_sql}")
        cursor.execute(insert_sql)
        conn.commit()

        # 查询数据
        query_sql = "SELECT * FROM test_users"
        print(f"exec_query_sql, {query_sql}")
        cursor.execute(query_sql)
        rows = cursor.fetchall()
        for row in rows:
            print(row)
        conn.close()
        return True

    except dmPython.Error as e:
        print(f"❌ 达梦数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        return False


if __name__ == "__main__":
    test_dm_connection()