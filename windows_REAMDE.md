# 1. 环境配置

下面介绍下 windows 环境下的运行环境配置。

## 1.1 python

下载 python 3.12.3

https://www.python.org/downloads/release/python-3123/

下载 `exe` 文档，进行安装。

## 1.2 pip

windows 下安装了 python， `pip` 命令也自动安装了。 完成 1.1 和1.2 后，在windows 的 `cmd`（**`Win + R`** → 输入 `cmd` → 回车 ) 里应该可以执行以下命令，并看到相应的结果。

```sh
# 执行下面的命令
python -V
# 看到这个结果
Python 3.12.3

# 执行下面的命令
pip -V
# 看到这个结果
pip 24.3.1 from
```



## 1.3 python package

连接公共互联网，下载安装包，大约耗费流量10GB。执行以下的命令。

```cmd
pip install gunicorn flask langchain_openai langchain_community langchain langchain_text_splitters langchain_unstructured unstructured langchain_core pydantic python-docx python-pptx pillow concurrent_log_handler pydub pycryptodome wheel tabulate chromadb lxml websockets markdown pypandoc pandas openpyxl
```



## 1.4 安装 `pandoc`

涉及到 Word `docx` 文档的操作，需要依赖这个组件， window 下安装说明详见  https://www.pandoc.org/installing.html#windows。

```
```

## 1.5 SQLite browser

系统使用了 SQLite 数据库进行相关的配置，为了通过GUI界面对 `SQLite` 数据库进行操作，需要下载`SQLite browser`。 window系统下的安装说明详见链接  https://sqlitebrowser.org/dl/，下载 “DB Browser for SQLite - Standard installer for 64-bit Windows”。

# 2. 配置

源代码根目录下的 cfg.db.template 是 `SQLite` 配置数据库模板，拷贝这个文件，并命名为 cfg.db，如果程序报错，大概率是 cfg.db 缺少相应的配置。

# 3. 运行

以运行`应用` `docx` 为例， 执行以下命令。

```
python -m apps.docx.app
```

源代码结构如下所示, apps 目录下的每一个名称都是一个独立的 `应用`。

```
.
├── apps
│   ├── chat
│   ├── chat2db
│   ├── csm
│   ├── docx
│   ├── embedding
│   ├── gateway
│   ├── llm
│   ├── mcp_client
│   ├── mcp_server
│   ├── mt_report
│   ├── ord_gen
│   ├── paper_review
│   ├── portal
│   ├── pptx
│   └── team_building
├── common
│   ├── build
│   ├── cert
│   ├── cfg_db_schema
│   ├── output_doc
│   ├── __pycache__
│   ├── sh
│   ├── static
│   └── templates
├── tests
│   ├── apps
│   ├── __pycache__
│   └── shared
└── upload_doc


```





