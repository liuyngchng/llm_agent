# 1. 系统开发手册

## 1. 开发环境配置

(1) 安装 git, 并配置 SSH 公钥 至 git 服务器；  
(2) 安装 python3.12；  
(3) 安装 python3.12 的 virtualenv， 用于创建虚拟环境，做到隔离环境；  
(4) 安装 python3.12 的 pip；  
(5) 安装 python whl 依赖包， 详见各个组件./apps/your_app 的 README.md 文件。

## 2. 获取源代码
```sh
# 从 github 获取源代码
git clone https://github.com/liuyngchng/llm_agent.git
# 无法上 github 的可以从 gitee 获取源代码
git clone https://gitee.com/liuyngchng/gitee_llm_agent.git
```

## 3. 运行代码
以启动 txt2sql 这个组件为例，启动命令如下：
```sh
cd /a/b/your_project_full_path/llm_agent
# 生成自己的配置文件
cp ./apps/txt2sql/cfg.yml.template ./apps/txt2sql/cfg.yml
# 修改相关的配置信息
vi ./apps/txt2sql/cfg.yml
# 将组件所需要的配置文件拷贝到当前目录下
cp ./apps/txt2sql/cfg.yml ./
cp ./apps/txt2sql/logging.conf ./

# 在项目根目录下创建 SQLite 配置数据库 cfg.db，
# 相关SQL 详见 ./apps/txt2sql/db_schema/*.sql
# SqliteBrowser 工具详见 (https://sqlitebrowser.org/dl/) 
create table xxxxxx
# 启动
PYTHONPATH=./:${PYTHONPATH}  ./apps/txt2sql/http_txt2sql.py

```
# 4. test

```sh
#health check for your LLM
http://127.0.0.1:19000
}'
```

