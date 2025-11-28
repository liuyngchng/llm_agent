# 1. 简介

本文档面向没有任何编程经验的读者，在自己的Windows 电脑上部署一个大语言模型智能体，文档提供详细的部署安装步骤，请逐步仔细执行。以下所有操作已在环境 Windows 10 旗舰版操作系统中进行了测试。

* 如果你是一位经验丰富的开发者，则可以跳过 ”2. 运行环境配置“ 章节直接查看后面的文档。
* "./" 表示当前的工作目录（Windows 中的某个文件夹下）

* 本项目为 `Python` 工程，工程下有多个 `Python` 应用， 每个 "./apps/some_app" 都可以独立工作，即”智能体“，实际上是一个Web应用，或者HTTP接口。

*  "./common" 文件夹为公共组件，是各 `Python` 应用的共用部分。详细介绍请阅读项目根目录下的 `README.md` 文件。

# 2. 环境配置

下面介绍下 `Windows` 环境下的运行环境配置，请按照说明文档进行操作。

## 2.1 python

 `Python`语言的工程（代码文件为*.py），需要语言解释器将其翻译为操作系统能理解的可执行文件。

首先下载 `Python`， 版本为 3.12.3

https://www.python.org/downloads/release/python-3123/

下载 `exe` 文件，进行安装。

*** 注意：在安装python时务必勾选 “Add Python to PATH” 选项。若没有勾选，后续需要手动进行环境变量配置。这个操作是在 Windows` CMD` 下输入 python 这个命令时，能够正确被操作系统理解的基础。***

## 2.2 pip 命令

pip 是 `Python` 程序的依赖包管理工具。当工程中的某个 `Python` 文件引用了（import ***）其他工程（不在本工程中） `Python` 文件时，就需要由 pip 来负责自动完成安装。

。`pip` 命令也自动安装了。 接下来在windows 的 `CMD`（**`Win + R`** → 输入 `cmd` → 回车 ) 里执行以下命令，并看到相应的结果，说明安装成功。

```sh
# 执行下面的命令
python -V
# 看到这个结果
Python 3.12.3

# 执行下面的命令
pip -V
# 看到这个结果，24.*
pip 24.3.1 from
```

如果无法执行，可能是安装的时候没有进行环境变量的配置，点击“我的电脑” -> 右键选择“属性” -> 在右侧找到并点击“高级系统设置”，进入环境变量设置，点击右下角的 **“环境变量”** 按钮。

## 2.3 虚拟环境创建

使用 python 虚拟环境，就像你在windows 中安装的是”绿色软件“，用完直接删除而不会影响操作系统，同时不同的工程使用各自独立的虚拟环境，能够减少互相之间的影响，为软件的运行、维护等都带来极大的好处。

不使用 python 虚拟环境，就像你在 Windows 中安装的是 exe或msi 的安装文件，用完之后卸载可能会卸载不干净，导致需要重装操作系统才能修复某些问题。

那么，截至目前，python 虚拟环境带来的好处应该很明确了吧？

配置虚拟环境，有利于管理下载的 python 依赖包，将下载的文件按照你的要求自动放在某个目录下，同时 python 对操作系统的所有操作都在某个沙箱内进行，将其对操作系统的影响降到最低。
（1）打开 Windows CMD 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# 安装创建虚拟环境的命令
pip install virtualenv
C:\workspace>pip install virtualenv
Requirement already satisfied: virtualenv in c:\program files\python312\lib\site-packages (20.35.4)

```
（2）创建自己的工作目录。注意，工作目录路径不要有中文字符，不要有空格等特殊字符，以免引起不必要的麻烦。假定需要在D:\workspace 下进行后续工作，如果没有D: 盘，就在C: 盘下进行操作

```cmd
#（1）# (1)输入D:, 切换盘符到D:，如果在C:盘下操作，忽略这个操作
D:
# （2）进入 D 盘根目录
cd /
# （3）创建文件夹  workspace
mkdir workspace
# （4）查看是否创建成功, 此时能看到有一个 workspace 的目录
dir
# （5）进入 D:\workspace 目录下
cd workspace
```

目前你的 `CMD`  窗口中显示的路径应该为 D:\workspace 或者 C:\workspace，接下来将在盘符C:或者D:下的 workspace\llm_py_env 下创建虚拟环境，这个目录将作为 python.exe 的新家，以及下载的所有关联文件的目录，后续不需要的时候只要删除这个目录就可以把自己的电脑清理干净了。

（3）查看新安装的 `virtualenv` 命令是否能被 Windows `CMD` 窗口理解

```cmd
# virtualenv llm_py_env 命令将自动创建目录 llm_py_env
D:\workspace> virtualenv llm_py_env
```

如果上面的指令无法执行，CMD 窗口报错

```cmd
'virtualenv' 不是内部或外部命令，也不是可运行的程序
或批处理文件。
```

说明 `virtualenv` 没有被添加在环境变量中（一般来说这种情况很少发生），请执行以下操作

```cmd
# （1） 执行 where pip 命令
C:\workspace>where pip
C:\Program Files\Python312\Scripts\pip.exe
#可以看到自己的python 安装在目录 "C:\Program Files\Python312\Script2" 下，那么 virtualenv.exe 应该也在这个目录下，实际按照自己电脑的路径操作
# 打开文件夹 c:\program files\python312\Scripts 会看到有一个 virtualenv.exe， 说明 virtualenv 命令安装成功

#（2）进行环境变量的配置，
# 将 c:\program files\python312\Scripts 添加到环境变量中， 操作如下：点击 我的电脑-> 右键属性 -> （右上角）高级系统设置 -> (右下角)环境变量 -> 系统环境变量 -> 找到 Path ->编辑 -> 新建， 粘贴 
#  c:\program files\python312\Scripts -> 保存
# 关闭已经打开的 CMD 窗口，重新打开 CMD，这样新配置的 Path 环境变量才能生效
```

完成之后，继续在 `CMD` 中执行
```cmd
# (1)进行相应盘符
D:
#(2) 进入盘符根目录
cd /
# (3) 进入工作目录
cd workspace
# (4) 执行命令 virtualenv llm_py_env ，这个命令将自动创建目录 llm_py_env
D:\workspace> virtualenv llm_py_env
```

## 2.4 虚拟环境激活

```cmd
# (1)进行相应盘符
D:
#(2) 进入盘符根目录
cd /
# (3) 进入工作目录
cd workspace
# （4）进入虚拟环境目录
cd llm_py_env
# （5）进入脚本目录
cd Scripts
# （6）执行 activate 命令激活虚拟环境，
activate
# 此时会看到下面的界面， 盘符前面有 (llm_py_env)， 说明虚拟环境激活成功
(llm_py_env) D:\workspace\llm_py_env\Scripts>
```

## 2.5 下载 python 源代码

 打开页面 https://gitee.com/liuyngchng/gitee_llm_agent， 点击 ”克隆/下载“ 按钮， 选择右上角的 ”下载ZIP“， 浏览器会下载一个文件 gitee_llm_agent-master.zip。 将这个zip包拷贝至 D:\workspace 下，点击这个 zip 文件， 右键-> 解压到当前目录， 会看到 生成新的目录 D:\workspace\gitee_llm_agent-master。

## 2.7 安装 pip 依赖包

接下来安装 python 应用程序的依赖包，进入你在网络上下载的  gitee_llm_agent 包的文件夹，假定在 目录 D:\workspace\gitee_llm_agent-master 下，继续在 Windows `CMD` 窗口中执行命令

```cmd
# （1）进入D: 盘符
D:
# （2）进入根目录
cd /
# （3）进入源代码目录
cd workspace\gitee_llm_agent-master
# （4）使用 dir 查看文件， 会看到有个文件 requirements.txt
dir
2025/11/28  17:05             5,302 requirements.txt

```
此时已经在 python 源代码根目录下了，而且虚拟环境是生效的（在盘符前面会有 (llm_py_env)）,如下所示

```cmd
# 工作目录在 D: 盘
(llm_py_env) C:\workspace\gitee_llm_agent-master>
# 工作目录在 D: 盘
(llm_py_env) D:\workspace\gitee_llm_agent-master>
```

如果虚拟环境未生效，请按照 2.4节重新进行操作。

 接下来开始安装依赖， 保持网络畅通，这个过程消耗时间1~2小时，具体取决于你的网络环境，请耐心等待。

```cmd
# 执行 pip install 命令, 中途若终端，则可以重新发起执行，或者从2.7节开头开始重新操作一遍
(llm_py_env) D:\workspace\gitee_llm_agent-master>pip install -r requirements.txt
```

执行成功后， `D:\workspace\llm_py_env` 这个文件夹（虚拟环境文件夹）大约为 `4GB`，包含了软件运行的所有依赖。

`requirements.txt` 文件是 `Python` 工程（project）中的依赖包文件清单，说明项目的源代码还依赖哪些第三方组件。

其中部分组件，可能会依赖 `Windows` 操作系统底层的 `dll`（这是 `Python` 语言的特性决定的，`Python` 的 pip 包也是对底层 `C` 语言的封装）。如果在运行时报错，则可以根据报错信息安装 `Windows` 系统的相关组件。

如果使用 `gitee_llm_agent-maste/apps/chat2db`, 读取哪种数据库，就需安装哪种数据库的客户端驱动。

## 2.8 安装 `pandoc`

涉及到文档的转换操作需要依赖这个组件，`pandoc` 是开源社区中较为流行的文档格式转换工具包。 

可以先不安装，如果报错信息中出现 pandoc 的字样再进行安装。

（1）方法1。通过以下命令在Windows 上安装 pandoc

```sh
# 需在Windows上安装Chocolatey，详见 https://docs.chocolatey.org/en-us/choco/setup
choco install pandoc
```

（2）方法2。 通过Windows msi 引导文件安装， 详见  https://www.pandoc.org/installing.html#windows。

## 2.9 `SQLite browser`

`SQLite browser` 是文件数据库 `SQLite` 的图形化管理工具。本系统使用了 `SQLite` 文件数据库进行相关数据的存储，为了通过GUI界面对 `SQLite` 数据库进行操作，需要下载`SQLite browser`。

 `Window` 系统下的安装说明详见链接  https://sqlitebrowser.org/dl/，下载 “`DB Browser for SQLite - Standard installer for 64-bit Windows`”。

当然，如果对 `SQLite`的相关命令很熟悉，可以忽略此部分。

# 3. 软件配置

下面以通过命令行启动单个应用`apps/chat`程序为例，进行系统配置说明。

## 3.1 cfg.db

文件 `cfg.db` 是项目中很多关系型数据的 `SQLite` 配置文件，不可或缺，一般存在于项目根目录和各个应用根(例如 `D:\workspace\gitee_llm_agent-master\apps\chat/`)目录

源代码各个应用根目录（apps/chat/）下的 cfg.db.template 是当前应用(chat)的 `SQLite` 配置数据库模板。

拷贝准备启动的应用（apps/chat/）目录下的 `cfg.db.template` 至项目根目录 `D:\workspace\gitee_llm_agent-master`，并命名为 cfg.db，用 `SQLite browser` 打开可操作相关的配置。

cfg.db 中的数据库表结构详见项目根目录下 common/cfg_db_schema 下的各个 sql 文件。

## 3.2 cfg.yml

cfg.yml 是系统运行的配置文件，用于配置各种模型（大语言模型、文本嵌入模型、语音识别模型、图像识别模型）的 API，Key，一级相关提示词等信息。

 拷贝各个应用根目录（apps/chat/）下的 `cfg.yml.template` 文件至项目根目录，重命名为 `cfg.yml`， 配置相应信息。

## 3.3 logging.conf

`logging.conf` 为项目的日志配置文件，用于控制以下信息。

（1）日志信息写入到哪里， 例如控制台、文件、数据库、系统日志等；

（2）输出什么等级的日志，错误、信息、调试(ERROR| INFO|DEBUG)；

（3）输出哪些模块（可以简单理解为哪些python文件、文件夹）的日志。

 拷贝各个应用根目录（apps/chat/）下的 `cfg.yml.template` 文件至项目根目录，重命名为 `cfg.yml`， 配置相应信息。

## 3.4 NLTK

**NLTK**（Natural Language Toolkit）是针对自然语言处理设计的Python开源工具集，集成了处理常见NLP任务的模块和标准化语料库。如果使用到本项目中的知识库（文档向量化）功能（即使调用远程的文本嵌入 API 也需要），则本地还需要安装 `NLTK` 的中英文分词数据包， 详见 `NLTK` 官网（https://www.nltk.org/data.html）。

不使用这部分功能，则可以忽略。

# 4. 运行程序

## 4.1 控制台运行

以运行`应用` `chat` 为例， 可以在 Windows 控制台（`CMD`）中通过执行以下命令启动应用。

```sh
# (1)输入D:, 进入相应盘符, 如果是C盘，就输入 C:
D:
#(2) 进入盘符根目录
cd /
# (3) 进入工作目录
cd workspace
# （4）进入虚拟环境目录
cd llm_py_env
# （5）进入脚本目录
cd Scripts
# （6）执行 activate 命令激活虚拟环境，
activate
# 此时会看到下面的界面， 盘符前面有 (llm_py_env)， 说明虚拟环境激活成功
(llm_py_env) D:\workspace\llm_py_env\Scripts>
# 这样运行，执行的是 apps/chat/app.py 这个文件, 当前目录为项目根目录
python -m apps.chat.app
```

此时，运行时的当前目录 "./" 为项目文件根目录， 读取的 cfg.db, cfg.yml, logging.conf 都是项目根目录下的对应文件。

启动后，会看到日志中显示:

```sh
2025-11-26 10:50:26,981 - 126491346956608 - __main__ - INFO -<module> - [251]- listening_port 19000
 * Serving Flask app 'app'
 * Debug mode: off

```

说明程序启动了监听端口 19000，启动正常。接下来，在浏览器中输入 http://127.0.0.1:19000，即可看到相应的页面。
如果运行中看到  `ModuleNotFoundError: No module named 'xxxx`， 则执行 pip install xxxx。

在Windows CMD 的控制台界面中按键 Ctrl + C，即可终止当前运行的服务。

## 4.2 IDE 运行

如果使用集成开发环境，如 VS Code, PyCharm 等运行某个app， 例如运行 apps/chat/app.py，那么这时候运行时的当前目录为 apps/chat/, 读取的 cfg.db, cfg.yml, logging.conf 均为  apps/chat/ 下的对应文件。系统配置需要修改 apps/chat/ 目录下的相应文件。

# 5. 虚拟环境设置

如果自己本地计算机上只有一个python 工程，则可以忽略这部分。

## 5.1 介绍

由于不同的工程使用不同的python版本、不同的依赖组件(pip install xxxx)。如果在自己的计算机上同时存在多个工程（project），那么就会有python 版本、依赖包互相之间有冲突的风险，为了避免这种风险， python 中引入了虚拟环境的概念。通过设置虚拟环境，不同的工程（project）之间的python版本、pip 包完全隔离。

## 5.2 virtualenv

执行以下命令

```sh
pip install virtualenv
```

具体使用方法，详见  https://gitee.com/liuyngchng/gitee_rd.lab/blob/master/python.md。



