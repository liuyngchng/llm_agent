#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import json
import platform
import sqlite3

def test_update():
    import sqlite3
    import sys

    print(f"Python version: {sys.version}")
    print(f"SQLite version: {sqlite3.sqlite_version}")

    # 创建测试数据库
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()

    # 创建测试表
    cursor.execute('''
    CREATE TABLE test_table (
        id INTEGER PRIMARY KEY,
        name TEXT,
        value INTEGER
    )
    ''')

    # 插入测试数据
    cursor.execute("INSERT INTO test_table (name, value) VALUES ('test1', 100)")
    cursor.execute("INSERT INTO test_table (name, value) VALUES ('test2', 200)")
    conn.commit()

    # 测试UPDATE with LIMIT
    try:
        sql ="UPDATE test_table SET value = 999 WHERE name = 'test1"
        if platform.system() == "Linux":
            sql += " limit 1"
        cursor.execute(sql)
        conn.commit()
        print("✅ UPDATE with LIMIT 执行成功!")
    except sqlite3.OperationalError as e:
        print(f"❌ UPDATE with LIMIT 执行失败: {e}")

    # 测试正常的UPDATE
    try:
        cursor.execute("UPDATE test_table SET value = 888 WHERE name = 'test1'")
        conn.commit()
        print("✅ 正常UPDATE执行成功!")
    except sqlite3.OperationalError as e:
        print(f"❌ 正常UPDATE执行失败: {e}")

    conn.close()

def test_file():
    db_uri = "sqlite:///cfg.db"
    db_file = "cfg.db"
    query = "select * from user"
    with sqlite3.connect(db_file) as db_con:
        cursor = db_con.cursor()
        print(f"execute_query {query}")
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        dt = json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
        print(f"dt {dt}")

if __name__ == "__main__":
    test_update()