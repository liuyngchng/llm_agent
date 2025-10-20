# 1. 应用清单

本工程的 apps 目录下各个应用的功能如下所示，各个工程下的程序入口为 app.py。 

项目 github 地址：[https://github.com/liuyngchng/llm_agent](https://gitee.com/liuyngchng/gitee_llm_agent)，  

gitee 平台地址为：[https://gitee.com/liuyngchng/gitee_llm_agent](https://gitee.com/liuyngchng/gitee_llm_agent)

通过 `IDE`（`Pycharm`, `VsCode` 等）直接启动 `debug`，为 `HTTP` 服务，通过脚本部署的 `docker` 应用为`HTTPS` 服务。

| No.   | 名称      | 服务类型 | 端口 | 描述         |
|---------| --- |------------|------------|------------|
| 1 | apps/db_svc | HTTP/HTTPS | 18000 | 开放平台，提供与其他平台进行集成的接口 |
| 2 | apps/chat2sql | HTTP/HTTPS | 19001 | AI 数据库查询，支持MySQL, Oracle, DM8 |
| 3 | apps/chat | HTTP/HTTPS | 19002 | AI 知识库问答, 提供基于知识库的问答能力 |
| 4 | apps/docx | HTTP/HTTPS | 19003 | AI 文档生成，支持在线生成 Word docx文档 |
| 5 | apps/csm | HTTP/HTTPS | 19004 | AI 客服，提供 AI 辅助人工客服的能力 |
| 6 | apps/mcp_client | HTTP/HTTPS | 19005 | MCP client，通过Web 界面 |
| 7 | apps/mcp_server | HTTP/HTTPS | 19006 | MCP server， 提供 MCP tools 查询服务 |
| 8 | apps/ord_gen | HTTP/HTTPS | 19007 | AI 订单生成    |
| 9 | apps/llm | HTTP/HTTPS | 8000 | 兼容 OpenAI 接口格式的大语言模型服务 |
| 10 | apps/embedding | HTTP/HTTPS | 17000 | 兼容 OpenAI 接口格式的文本嵌入模型服务 |

# 2. 开发环境配置

本工程以 `python` 代码为主， 下面以 `Ubuntu 22.04 LTS` 系统为例，对开发相关配置进行说明。

(1) 安装 `git`, 并配置 `SSH` 公钥 至 `git` 服务器。

```shell
# git-lfs 用于下载大的模型文件
sudo apt install git git-lfs -y
```

(2) 安装 `python`， 版本为 3.12。

```shell
# 系统默认已安装
python -V
Python 3.12.3
```

(3) 安装 `virtualenv`， 用于创建 `python` 虚拟环境，做到隔离环境。

通过使用虚拟环境，不同的工程可以使用不同的`python` 版本以及不同的依赖库，这样后续比较好维护，是一种良好的开发习惯。

```shell
sudo apt install virtualenv -y
```

(4) 安装 `python` 3.12 的 pip。

```shell
sudo apt install python3-pip -y
```

(5)  创建虚拟环境

```shell
cd ~
# 创建工作空间目录，用于放置开发相关项目
mkdir workspace
# 进入工作空间
cd ～/workspace
# -p 指定使用哪个版本的python， llm_py_env 为虚拟环境目录
virtualenv -p python3.12 llm_py_env
# 激活虚拟环境，这样之后执行的下载，使用的命令都首先从这个目录读取，可以看到用户名前有(llm_py_env),说明虚拟环境处于激活状态
source llm_py_env/bin/activate
(llm_py_env) rd@rd-ex:~/workspace$
# 当前目录下自动创建了一个 llm_py_env 目录，后续安装的所有包都安装在 llm_py_env 目录下
llm_py_env) rd@rd-ex:~/workspace$ ls
llm_py_env
# 执行 deactivate 退出虚拟环境
(llm_py_env) rd@rd-ex:~/workspace$ deactivate 
rd@rd-t14:~/workspace$ 
````


# 3. 获取源代码

```sh
cd workspace
# 从 github 获取源代码
git clone https://github.com/liuyngchng/llm_agent.git
# 若无法访问 github，可以从 gitee 获取源代码
git clone https://gitee.com/liuyngchng/gitee_llm_agent.git
```

安装 python whl 依赖包， 详见工程中各个组件./apps/my_app 的 requirements.txt 文件。

```shell
cd workspace
source llm_py_env/bin/activate
cd llm_agent
(llm_py_env) rd@rd-ex:~/workspace/llm_agent$
# 安装 requirements.txt 下的所有依赖
pip install -r ./apps/chat2db/requirements.txt
```

# 4. 运行

以启动 `chat2db` 这个应用（`app`）为例。

**（1）准备日志和 `yaml` 配置文件**

日志配置文件 `logging.conf` 用于配置各个模块的日志级别、输出格式等。`cfg.yml` 用于程序启动时所必需的一些配置，例如大语言模型 `API` 等。

首先拷贝日志配置文件和 `yaml` 配置文件：

```sh
cd ~/workspace/llm_agent

########### IDE debug 所需配置文件 ########
# 生成自己的配置文件
cp ./apps/chat2db/cfg.yml.template ./apps/chat2db/cfg.yml
# 修改相关的配置信息, 数据库连接信息， 大模型API 信息等
vi ./apps/chat2db/cfg.yml
# 将组件所需要的配置文件拷贝到当前目录下，IDE启动使用当前应用下的配置文件

########### 程序独立运行所需配置文件 ########
# 当程序独立运行时，读取的配置文件均需要位于项目根目录下
cp ./apps/chat2db/cfg.yml ./
cp ./apps/chat2db/cfg.db ./
cp ./apps/chat2db/logging.conf ./
```

**（2）准备 `SQLite` 数据库配置文件**

`SQLite`配置数据库文件 `cfg.db` 中存储一些在运行时各个应用所需要的一些运行时参数。

构建`SQLite`配置数据库文件 `cfg.db`。可以通过可视化工具、脚本，也可以直接使用`cfg.db.template`创建文件 `cfg.db` 文件。

1） 直接使用模板

```sh
# 直接使用模板,确保模板 cfg.db.template 中相关表的结构与对应的 SQL 语句、以及程序代码一致 
cp ./apps/chat2db/cfg.db.template ./apps/chat2db/cfg.db
```

2）通过可视化工具创建

下载安装 `SQLite` 数据库的图形可视化工具 `SQLite` browser，在可视化工具中进行 `cfg.db` 的文件创建以及各个表表结构的创建， 表结构详见 ./common/cfg_db_schema 下的各个表的表结构 `SQL`。

```shell
sudo apt-get install sqlitebrowser
```

3）通过脚本生成

```shell
# SQLite 命令行工具用于自动执行脚本
sudo apt-get install sqlite3
cd ~/workspace/llm_agent
# 执行 SQLite 初始化脚本,将在当前目录下创建一个 SQLite 的数据库文件 cfg.db
./common/sh/init_sqlite_cfg_db.sh
```

启动 http 服务

```shell
# 通过将当前目录 ./ 添加至 PYTHONPATH， 保证 common 包加载正常
PYTHONPATH=./:${PYTHONPATH}  ./apps/chat2db/app.py
```

# 5. 测试

```sh
# 在浏览器中测试页面是否可以正常打开，推荐使用 chrome
http://127.0.0.1:19000
```

# 6. 其他

## 6.1 语音识别

在 `chat2db` 中使用了语音输入，需要进行部署。这部分功能是辅助增强功能，如果不需要完全可以忽略，直接进行文本框文本输入即可。

### 6.1.1 基础库安装

应用 chat2db 中使用了语音识别服务，python 的相关库需要依赖操作系统的 ffmpeg 组件， 需在操作系统中进行安装。

```sh
# windows
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
# ubuntu
sudo apt install ffmpeg
```

### 6.1.2 语音识别模型服务部署

如果无法获取到在线的语音识别 `API` 服务，同时本地具有一定的显卡(`GPU`)资源， 那么可以在自己本地部署一个兼容 `OpenAI` 接口数据格式的语音识别服务。

```sh
pip install "vllm[audio]"

CUDA_LAUNCH_BLOCKING=1 CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 \
vllm serve whisper-large-v3-turbo \
--tensor-parallel-size 1 \
--max-model-len 448 \
--gpu-memory-utilization 0.7 \
--enforce-eager \
--swap-space 0 \
--device cuda
```

部署完成后，可以进行语音识别自测，目前页面输入的语音流行是 `webm` 格式的。测试语音生成。

```sh
pip install edge-tts 

# 生成默认音频：
edge-tts -t "测试语句" --write-media temp.webm
# 转码为真实webm：
ffmpeg -i temp.webm -c:a libopus asr_test.webm
```

对语音识别的 `HTTP` 接口进行测试

```sh
curl -X 服务POST http://127.0.0.1:19000/trans/audio \
  -F "audio=@static/asr_test.webm;type=audio/webm" \
  -H "Content-Type: multipart/form-data"
```

## 6.2 SSH 使用密钥登录服务器

有些服务器需要使用密钥而不是密码口令进行登录，可以使用下面的命令进行。

```sh
ssh -i your_private_key_file_path your_user@your_host -p ssh_port

scp -i your_private_key_file_path -P ssh_port your_file_want_to_be_uploaed devbox@your_host:/your_host_dir

```

## 6.3 大语言模型(`LLM`) 服务
### 6.3.1 使用在线 `API`

所有的服务均需要使用大语言模型服务， 可以使用目前市面上一些服务，作为测试足够用，例如 deepseek 提供的在线 API, 详见 https://platform.deepseek.com/。

### 6.3.2 本地部署

如果本地有可用的显卡（`GPU`）资源，也可以自行部署自己的本地的兼容 `OpenAI` 接口数据格式的大语言模型。

```sh
# 一张显卡， 则并行化=1 即tensor-parallel-size=1, 
# max-model-len 表示模型上下文token长度为32k，
vllm serve ../DeepSeek-R1-Distill-Qwen-7B \
    --tensor-parallel-size 1 \
    --max-model-len 32768 \
    --enforce-eager \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --served-model-name DeepSeek-R1 &
```

测试
```sh
curl -s http://127.0.0.1:8000/v1/models | jq
```

本地部署的服务，如果模型本身的参数和精度不高，则其智能化水平较低，部分应用的实际效果会大大下降。除测试外，推荐使用在线的大语言模型 `API` 服务。

## 6.4 DM8

`chat2db` 中如果需要访问`达梦数据库`(DM8) ， 由于访问`达梦数据库`的python 组件 `dmPython` 并非独立的驱动，还需要依赖底层的 C 语言动态库，需要在 `LD_LIBRARY_PATH` 中安装`达梦数据库`的客户端驱动 so 文件。

# 7. 服务部署

在服务器上部署本工程，详见 

[服务部署说明文件]: ./deploy_README.md

./deploy_README.md 。
