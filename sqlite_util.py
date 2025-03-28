#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import json
import pandas as pd

def db_query_tool(db, query: str) -> str:
    try:
        cursor = db.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        return json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

def output_data(db, sql:str) -> str:
    result = db_query_tool(db, sql)
    # print(result)
    data = json.loads(result)
    # 生成表格
    df = pd.DataFrame(data['data'], columns=data['columns'])
    return df.to_markdown(index=False)  # 控制台打印美观表格
    # 生成网页表格
    # df.to_html("table.html")  # 生成可交互网页表格

if __name__ == "__main__":
    # sql = "SELECT * FROM customer_info LIMIT 2"
    sql = "SELECT T1.`用户姓名`, T2.`订单ID`, T2.`支付金额` FROM customer_info AS T1 INNER JOIN order_info AS T2 ON T1.`用户ID` = T2.`用户ID` WHERE T2.`创建时间` LIKE '2025%' AND T1.`用户姓名` = '张三' LIMIT 5"
    conn = sqlite3.connect("test2.db")
    output_data(conn, sql)