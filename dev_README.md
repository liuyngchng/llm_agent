# 1. 系统开发手册

## 1. 开发环境配置
下面以 Ubuntu 22.04 LTS 系统为例，进行系统开发配置说明。
(1) 安装 git, 并配置 SSH 公钥 至 git 服务器；  
```shell
# git-lfs 用于下载大的模型文件
sudo apt install git git-lfs -y
```
(2) 安装 python3.12；
```shell
# 系统默认已安装
python -V
Python 3.12.3

```
(3) 安装 python3.12 的 virtualenv， 用于创建虚拟环境，做到隔离环境；  
```shell
sudo apt install virtualenv -y
```
(4) 安装 python3.12 的 pip；  
```shell
sudo apt install python3-pip -y
```
(5)  创建虚拟环境，并进入虚拟环境；
```shell
cd workspace
virtualenv -p python3.12 llm_py_env
source llm_py_env/bin/activate
(llm_py_env) rd@rd-ex:~/workspace$
# 可见当前目录下有一个 llm_py_env 目录，后续安装的所有包都安装在 llm_py_env 目录下
llm_py_env) rd@rd-ex:~/workspace$ ls
llm_py_env
````


## 2. 获取源代码
```sh
cd workspace
# 从 github 获取源代码
git clone https://github.com/liuyngchng/llm_agent.git
# 无法上 github 的可以从 gitee 获取源代码
git clone https://gitee.com/liuyngchng/gitee_llm_agent.git
```
安装 python whl 依赖包， 详见各个组件./apps/your_app 的 README.md 文件。
```shell
cd workspace
source llm_py_env/bin/activate
cd llm_agent
(llm_py_env) rd@rd-ex:~/workspace/llm_agent$
pip install -r ./apps/txt2sql/requirements.txt
```

## 3. 运行代码
以启动 txt2sql 这个组件为例，首先拷贝日志配置文件和 yaml 配置文件：
```sh
cd ~/workspace/llm_agent
# 生成自己的配置文件
cp ./apps/txt2sql/cfg.yml.template ./apps/txt2sql/cfg.yml
# 修改相关的配置信息, 数据库连接信息， 大模型API 信息等
vi ./apps/txt2sql/cfg.yml
# 将组件所需要的配置文件拷贝到当前目录下
cp ./apps/txt2sql/cfg.yml ./
cp ./apps/txt2sql/logging.conf ./
```
下载安装 sqlite browser
```shell
# sqlite3 命令行工具用于自动执行脚本
sudo apt-get install sqlitebrowser sqlite3
```
创建配置数据库
```
cd ~/workspace/llm_agent
./common/sh/init_sqlite_cfg_db.sh
```
启动 http 服务
```shell
PYTHONPATH=./:${PYTHONPATH}  ./apps/txt2sql/http_txt2sql.py
```
# 4. test

```sh
#health check for your LLM
http://127.0.0.1:19000
```

