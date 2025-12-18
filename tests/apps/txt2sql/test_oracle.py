#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

import oracledb
from sys_init import init_yml_cfg
import logging.config

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    # 设置默认的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
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