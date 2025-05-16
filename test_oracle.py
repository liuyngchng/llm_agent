#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import oracledb
from sys_init import init_yml_cfg
import logging.config

logging.config.fileConfig('logging.conf', encoding="utf-8")
logger = logging.getLogger(__name__)

if __name__ == "__main__":

    my_cfg = init_yml_cfg()

    # 连接数据库
    dsn = oracledb.makedsn(my_cfg['db']['host'], my_cfg['db']['port'], service_name=my_cfg['db']['name'])
    conn = oracledb.connect(user=my_cfg['db']['user'], password=my_cfg['db']['password'], dsn=dsn)
    cursor = conn.cursor()

    # 查询表名
    cursor.execute("SELECT table_name FROM user_tables")
    tables = cursor.fetchall()
    list_table = [table[0] for table in tables]
    print(list_table)

    # 关闭连接
    cursor.close()
    conn.close()