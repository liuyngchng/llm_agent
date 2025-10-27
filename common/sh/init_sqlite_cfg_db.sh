#!/bin/bash
# 创建数据库文件
touch cfg.db

# 执行多个 SQL 脚本创建表结构
for sql_file in ../cfg_db_schema/*.sql; do
    sqlite3 cfg.db < "$sql_file"
done

echo "数据库初始化完成"