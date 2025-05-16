#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sqlite3

if __name__ == "__main__":
    db_uri = "sqlite:///config.db"
    db_file = "config.db"
    query = "select * from user"
    with sqlite3.connect(db_file) as db_con:
        cursor = db_con.cursor()
        print(f"execute_query {query}")
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = cursor.fetchall()
        dt = json.dumps({"columns": columns, "data": data}, ensure_ascii=False)
        print(f"dt {dt}")