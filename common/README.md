## 1. 简介

本模块为各个应用 ([app](../apps/csm/app.py)) 提供公共的组件和工具函数，旨在提高代码复用性和开发效率。

## 2. 目录结构

```sh

common/
├── build/                 # 构建相关公共组件的脚本和配置
├── cfg_db_schema/         # 配置数据库表结构定义
├── sh/                    # 各类测试和初始化脚本
├── static/                # Web静态资源文件
├── templates/             # Web模板文件
├── *.py                   # Python工具模块
└── README.md              # 本文件
```
## 3. 主要功能模块

### 3.1 文档处理

#### 3.1.1 Word 文档处理 

文件 `docx_*_util.py` 为 Word文档处理工具。

- `docx_md_util.py`: Word(.docx)与Markdown格式互转，支持Mermaid图表修复；
- `docx_para_util.py`: Word文档段落和大纲操作；
- `docx_meta_util.py`: Word文档元数据处理；
- `docx_cmt_util.py`: Word文档评论相关功能。

#### 3.1.2 Excel 文档处理 

文件 `xlsx_*_util.py` 为 Excel文档处理工具。

- `xlsx_md_util.py`: Excel(.xlsx)转换为Markdown格式；
- `xlsx_util.py`: Excel文档基础操作。

#### 3.1.3 其他文档处理
- `txt_util.py`: 文本文件内容检索工具；
- `ocr_util.py`: OCR识别相关功能；
- `html_util.py`: HTML处理和转换工具。

### 3.2 知识库管理 

文件 `vdb_*_util.py` 为知识库管理类工具。

- `vdb_util.py`: 核心向量知识库操作；
- `vdb_meta_util.py`: 知识库元数据管理；
- `vdb_hf_util.py`: HuggingFace模型集成；
- `bp_vdb.py`: 知识库相关Flask蓝图和服务接口。

### 3.3  配置与数据库 

文件 `cfg_util.py`, `db_util.py` 为配置与数据库管理工具。

- 配置信息管理；
- 数据库连接与操作封装；
- `SQLite` 配置数据库初始化。

### 3.4 认证与权限 

文件 `bp_auth.py` 为 Web 认证与权限工具。

- 用户认证机制实现
- 权限控制逻辑

### 3.5  枚举与常量 

文件 `my_enums.py`, `const.py` 为系统中用到的枚举，以及全局性的常量类。

- 系统级枚举类型定义
- 全局常量配置

### 3.6 工具类模块

其他工具类如下所示。

- `agt_util.py`: Agent相关工具函数
- `cm_utils.py`: 通用工具函数集合
- `mcp_util.py`: MCP协议相关实现
- `statistic_util.py`: 统计功能工具

## 4. 核心特性

**（1）文档格式转换**

- 支持Word、Excel、PDF等多种格式转换为Markdown
- 提供Markdown到HTML和Word的反向转换
- 特色Mermaid图表语法修复功能

**（2）向量知识库**

- 文档加载与切片处理
- 多种文件格式支持（txt, pdf, docx）
- 向量存储与相似度搜索

**（3）Web服务支持**

- Flask蓝图实现RESTful API
- 文件上传与验证机制
- 用户认证与会话管理

**（4）配置管理**

- 数据库模式定义与初始化
- 动态配置加载与缓存
- 用户个性化设置支持

## 5. 使用说明

各模块设计为独立的功能单元，可在不同应用中灵活调用。主要依赖包括:
- pandas (数据处理)
- pypandoc (文档转换)
- flask (Web框架)
- sqlite3 (数据库)
- openpyxl (Excel处理)

## 6. 开发规范

- 所有Python文件均遵循统一的编码规范；
- 使用 `logging` 模块进行日志记录；
- 关键函数实现 `LRU` 缓存优化性能；
- 严格的异常处理和错误日志记录。