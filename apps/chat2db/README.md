# TXT2SQL 服务
提供自然语言查询数据服务

## 1. 依赖

```sh
pip install gunicorn flask flask_cors \
    concurrent-log-handler langchain_openai langchain_ollama langchain_core langchain_community \
    openai pandas tabulate pymysql oracledb dmPython sounddevice pydub pycryptodome wheel sympy markdown

```