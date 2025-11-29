# 1. 简介

本文档面向没有任何编程经验的用户，在自己的 Windows 10 机器上部署一个大语言模型智能体，文档提供详细的部署安装步骤，请逐步仔细执行。

以下所有操作已在环境 Windows 10 旗舰版操作系统中进行了测试。

* 如果你是一位经验丰富的开发者，则可以跳过 ”`2. 运行环境配置`“ 章节直接查看后面的文档。
* "./" 表示当前的工作目录（Windows 中的某个文件夹下）

* 本项目为 `Python` 工程，工程下有多个 `Python` 应用， 每个 ".`/apps/some_app`" 都可以独立工作，即”`智能体`“，实际上是一个`Web`应用，或者`HTTP`接口。

*  "./common" 文件夹为公共组件，是各 `Python` 应用的共用部分。详细介绍请阅读项目根目录下的 `README.md` 文件。

# 2. 环境配置

下面介绍下 `Windows` 环境下的运行环境配置，请按照说明文档进行操作。

## 2.1 python

 `Python`语言的工程（代码文件为`*.py`），需要语言解释器将其翻译为操作系统能理解的可执行文件。类似打开 `*.docx` 文件需要安装 `Office Word` 一样。 

首先下载 `Python`， 版本为 3.12.3（类似下载 Office Word， 版本为2017）

https://www.python.org/downloads/release/python-3123/

下载 `Windows installer (64-bit)` 文件，进行安装。

*** 注意：在安装过程中务必勾选 “Add Python to PATH” 选项。若没有勾选，后续需要手动进行环境变量配置。这个操作是在 Windows` CMD` 下输入 python 命令能够正确被操作系统理解的基础。***

## 2.2 pip 命令

pip 是 `Python` 程序的依赖包管理工具。当工程中的某个 `Python` 文件引用了（import ***）其他工程（不在本工程中）的 `Python` 文件时，就需要由 pip 来负责自动完成安装这个组件。

Windows 系统中安装了 python 后，`pip` 命令也自动安装了。 接下来在windows 的 `CMD 控制台`（**`Win + R`** → 输入 `cmd` → 回车 ) 里执行以下命令，并可以看到相应的结果，说明安装成功。

```sh
# 执行下面的命令
python -V
# 看到这个结果
Python 3.12.3

# 执行下面的命令
pip -V
# 看到这个结果，24.*
pip 24.3.1 from ****
```

如果无法执行，可能是安装的时候没有进行环境变量的配置，点击“我的电脑” -> 右键选择“属性” -> 在右侧找到并点击“高级系统设置”，进入环境变量设置，点击右下角的 **“环境变量”** 按钮。

## 2.3 工作目录创建

创建自己的工作目录。注意，工作目录路径仅使用英文半角字符，不要使用中文、空格等特殊字符，以免引起不必要的麻烦。假定需要在目录`C:\workspace` 下进行后续工作，请在C 盘根目录下手动创建文件夹 workspace，或在`Windows CMD` 控制台中执行以下命令

```cmd
# （1）输入 cd /,回车，进入 C 盘根目录
C:\Users\your_name>cd /
C:\>
# （2）输入 mkdir workspace， 创建文件夹  workspace
C:\>mkdir workspace
# （3）输入dir， 查看是否创建成功, 此时能看到有一个 workspace 的目录
C:\>dir
 驱动器 C 中的卷是 Windows
 卷的序列号是 C61E-F329

C:\ 的目录
2025/10/01  17:57    <DIR>          workspace
# （4）输入 cd workspace， 进入 C:\workspace 目录下
C:\>cd workspace

C:\workspace>
```

目前你的 `CMD`  窗口中显示的路径应该为 `C:\workspace`。

## 2.4 下载 python 工程源代码

 打开页面 https://gitee.com/liuyngchng/gitee_llm_agent， 点击 ”`克隆/下载`“ 按钮， 选择右上角的 ”`下载ZIP`“， 浏览器会下载一个文件 `gitee_llm_agent-master.zip`。 将这个zip包拷贝至文件夹 `C:\workspace` 下，鼠标选中这个 zip 文件， 右键-> 解压到当前目录， 会看到生成新的目录 `C:\workspace\gitee_llm_agent-master`， 该文件夹下的 文件清单如下所示。

```
C:\workspace\gitee_llm_agent-master 的目录

2025/11/01  09:20    <DIR>          .
2025/11/01  09:20    <DIR>          ..
2025/11/01  17:12               607 .gitignore
2025/11/01  17:12    <DIR>          apps
2025/11/01  17:12             3,170 arch.md
2025/11/01  17:12             5,181 CHANGELOG.md
2025/11/01  19:04    <DIR>          common
2025/11/01  17:12             4,258 deploy_README.md
2025/11/01  17:12            35,823 LICENSE
2025/11/01  17:12            11,347 README.md
2025/11/01  17:12             5,302 requirements.txt
2025/11/01  17:12    <DIR>          tests
2025/11/01  19:04    <DIR>          upload_doc
2025/11/01  17:12             9,321 windows_REAMDE.md
```



## 2.5 虚拟环境创建

### 2.5.1 为什么要创建虚拟环境? 

使用 python 虚拟环境，类似在 Windows 中安装的是”绿色软件“ 一样，用完直接删除而不会影响操作系统，同时不同的工程使用各自独立的虚拟环境，能够减少互相之间的影响，为软件的运行、维护等都带来极大的好处。

不使用 python 虚拟环境，类似在 Windows 中安装的是 `exe` 或`msi` 的安装文件，用完之后卸载可能会卸载不干净，导致需要重装操作系统才能修复某些问题。

那么，截至目前，python 虚拟环境带来的好处应该很明确了吧？

配置虚拟环境，有利于管理下载的 python 依赖包，将下载的文件放置在用户指定的目录下，同时 `Python` 对操作系统的所有操作都在某个`沙箱`内进行，将其对操作系统的影响降到最低。

### 2.5.2 创建虚拟环境

接下来将在目录 `C:\workspace\llm_py_env` 下创建虚拟环境，这个目录将作为 `python.exe` 的新家，以及下载的所有关联文件的目录，后续不需要的时候只要删除这个目录就可以把自己的电脑清理干净了。

**（1）安装创建虚拟环境命令 `virtualenv`。**

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspac, 回车，进入工作目录
C:\Users\your_name>cd /workspace

C:\workspace>
# （2）输入 pip install virtualenv， 回车， 安装创建虚拟环境的命令
C:\workspace>pip install virtualenv
Requirement already satisfied: virtualenv in c:\program files\python312\lib\site-packages (20.35.4)

```
**（2）创建虚拟环境**

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspac, 回车，进入工作目录
C:\Users\your_name>cd /workspace

C:\workspace>
# （2）输入 virtualenv llm_py_env，回车，将自动创建目录 llm_py_env，即 C:\workspace\llm_py_env
C:\workspace> virtualenv llm_py_env
```

如果上面的指令无法执行，`CMD` 窗口显示如下报错

```cmd
'virtualenv' 不是内部或外部命令，也不是可运行的程序
或批处理文件。
```

说明 `virtualenv` 没有被添加在环境变量中（一般来说这种情况很少发生），请执行以下操作。

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1） 执行 where pip 命令
C:\Users\your_name>where pip
C:\Program Files\Python312\Scripts\pip.exe

```

可以看到自己的python 安装在目录 "`C:\Program Files\Python312\Script2`" 下，那么 `virtualenv.exe` 应该也在这个目录下，实际按照自己电脑的路径操作

打开文件夹 `c:\program files\python312\Scripts` 会看到有一个 `virtualenv.exe`， 说明 `virtualenv` 命令安装成功。接下来将 `virtualenv.exe` 的路径添加到环境变量 `PATH`的路径中。

操作如下：点击 我的电脑-> 右键属性 -> （右上角）高级系统设置 -> (右下角)环境变量 -> 系统环境变量 -> 找到 Path ->编辑 -> 新建， 粘贴 `c:\program files\python312\Scripts` -> 保存

*** 注意：关闭已经打开的 `CMD` 窗口，重新打开 `CMD`，这样新配置的 Path 环境变量才能生效

完成之后，打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspac, 回车，进入工作目录
C:\Users\your_name>cd /workspace

C:\workspace>
# （2）输入 virtualenv llm_py_env，回车，将自动创建目录 llm_py_env，即 C:\workspace\llm_py_env
C:\workspace> virtualenv llm_py_env
```

此时，打开 `C:\workspace` 文件夹 ，会看到有一个新文件夹 `llm_py_env`，说明虚拟环境创建成功。

## 2.6 虚拟环境激活

创建好虚拟环境后，在使用前需要激活。打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspace/llm_py_env, 回车，进入工作目录下的虚拟环境目录
C:\Users\your_name>cd /workspace/llm_py_env

C:\workspace>llm_py_env
# （2）输入 cd Scripts， 回车， 进入虚拟环境目录下的脚本目录
C:\workspace>llm_py_env> cd Scripts
# （3）输入activate， 回车， 执行 activate 命令激活虚拟环境，
C:\workspace\llm_py_env\Scripts>activate
# 此时会看到下面的界面， 盘符前面有 (llm_py_env)， 说明虚拟环境激活成功
(llm_py_env) C:\workspace\llm_py_env\Scripts>
```



## 2.7 安装 pip 依赖包

接下来安装 `Python` 应用程序的依赖包，在安装依赖包前，必须先激活虚拟环境。

### 2.7.1 激活虚拟环境并进入工作目录

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspace/llm_py_env, 回车，进入工作目录下的虚拟环境目录
C:\Users\your_name>cd /workspace/llm_py_env

C:\workspace>llm_py_env
# （2）输入 cd Scripts， 回车， 进入虚拟环境目录下的脚本目录
C:\workspace>llm_py_env> cd Scripts
# （3）输入activate， 回车， 执行 activate 命令激活虚拟环境，
C:\workspace\llm_py_env\Scripts>activate

(llm_py_env) C:\workspace\llm_py_env\Scripts>

# （4）输入 cd /workspace/gitee_llm_agent-master, 回车，进入工作目录下的工程目录
(llm_py_env) C:\workspace\llm_py_env\Scripts>cd /workspace/gitee_llm_agent-master

(llm_py_env) C:\workspace\gitee_llm_agent-master>


# （2）输入 dir ，回车，会看到有个文件 requirements.txt
dir
2025/11/28  17:05             5,302 requirements.txt

```
此时已经在 `Python` 源代码根目录下了，而且虚拟环境是生效的（在盘符前面会有 (`llm_py_env`)）,如下所示.

```cmd
(llm_py_env) C:\workspace\gitee_llm_agent-master>

```

### 2.7.2 安装pip 依赖包

 接下来开始安装依赖， 保持网络畅通，这个过程消耗时间1~2小时，具体取决于你的网络环境，请耐心等待。

```cmd
# 执行 pip install 命令, 中途若中断或窗口关闭，则从2.6节开始重新一步一步执行
(llm_py_env) C:\workspace\gitee_llm_agent-master>pip install -r requirements.txt
```

执行成功后， `C:\workspace\llm_py_env` 这个文件夹（虚拟环境文件夹）大约为 `4GB`，包含了软件运行的所有依赖。

## 2.8 安装 `pandoc`

工程下的 `apps/docx`, `apps/papre_review`, `apps/team_building` 需要依赖此组件进行文件的格式转换，`pandoc` 是开源社区中较为流行的文档格式转换工具包。 

可以先不安装，如果报错信息中出现 `pandoc` 的字样再进行安装。

（1）方法1（推荐新手使用）。通过Windows msi 引导文件安装， 详见  https://www.pandoc.org/installing.html#windows。

（2）方法2（高级用法，新手勿碰）。通过以下命令在Windows 上安装 pandoc

```sh
# 需在Windows上安装Chocolatey，详见 https://docs.chocolatey.org/en-us/choco/setup
choco install pandoc
```

## 2.9 安装`SQLite browser`

此组件非必须，除非您想查看系统的运行数据， 可暂时跳过。

`SQLite browser` 是文件数据库 `SQLite` 的图形化管理工具。本系统使用了 `SQLite` 文件数据库进行相关数据的存储，为了通过GUI界面对 `SQLite` 数据库进行操作，需要下载`SQLite browser`。

 `Window` 系统下的安装说明详见链接  https://sqlitebrowser.org/dl/，下载 “`DB Browser for SQLite - Standard installer for 64-bit Windows`”。

当然，如果对 `SQLite`的相关命令很熟悉，可以忽略此部分。

# 3. 软件配置

下面以启动单个应用`apps\chat`程序为例，进行系统配置说明。如果启动别的应用，例如 `apps\chat2db`， 则将下面所有路径中的 `apps\chat`替换为 `apps\chat2db`。

## 3.1 `cfg.db`

文件 `cfg.db` 是项目中很多关系型数据的 `SQLite` 配置文件，不可或缺，一般存在于项目各个应用根目录(例如 `C:\workspace\gitee_llm_agent-master\apps\chat\`)

源代码各个应用根目录（`apps\chat\`）下的 `cfg.db.template` 是当前应用(chat)的 `SQLite` 配置数据库模板。

拷贝准备启动的应用（`C:\workspace\gitee_llm_agent-master\apps\chat\`）目录下的 `cfg.db.template` 至项目根目录 `C:\workspace\gitee_llm_agent-master`，并命名为 `cfg.db`，若想查看数据，需要使用 `SQLite browser` 打开。

`cfg.db` 中的数据库表结构详见项目根目录下的 `C:\workspace\gitee_llm_agent-master\common\cfg_db_schema` 目录下的各个 `SQL` 文件。

## 3.2 `cfg.yml`

`cfg.yml` 是系统运行的配置文件，用于配置各种模型（大语言模型、文本嵌入模型、语音识别模型、图像识别模型）的 `API`、`Key`（即人工智能（AI）的算力、显卡、`GPU` 等类似的说法），以及提示词（即引导AI按照自己的意图输出内容）、数据加密密钥等信息。

 拷贝各个应用根目录（`C:\workspace\gitee_llm_agent-master\apps\chat\`）下的 `cfg.yml.template` 文件至项目根目录`C:\workspace\gitee_llm_agent-master`，重命名为 `cfg.yml`， 配置相应信息。`cfg.yml` 中每个配置项目都有明确的注释说明，请仔细阅读，根据自己的实际需要进行相应的配置。

## 3.3 logging.conf

`logging.conf` 为项目的日志配置文件，用于控制以下信息。

（1）日志信息写入到哪里， 例如控制台（`Windows CMD` 的界面）、文件、数据库、系统日志等；

（2）输出什么等级的日志，错误、信息、调试(ERROR| INFO|DEBUG)；

（3）输出哪些模块（可以简单理解为哪些python文件、文件夹）的日志。

 拷贝各个应用根目录（`C:\workspace\gitee_llm_agent-master\apps\chat\`）下的 `logging.conf` 文件至项目根目录`C:\workspace\gitee_llm_agent-master`即可，默认无须修改。

## 3.4 `NLTK`

使用知识库功能请阅读此部分内容，否则跳过。

**`NLTK`**（Natural Language Toolkit）是针对自然语言处理设计的Python开源工具集，集成了处理常见`NLP`任务的模块和标准化语料库。如果使用到本项目中的知识库（文档向量化）功能（即使调用远程的文本嵌入 `API` 也需要），则本地还需要安装 `NLTK` 的中英文分词数据包， 详见 `NLTK` 官网（https://www.nltk.org/data.html）。

# 4. 运行程序

完成了3. 小节中的各项配置后，可以开始应用了， 以运行`应用` `apps/chat` 为例，打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspace/llm_py_env, 回车，进入工作目录下的虚拟环境目录
C:\Users\your_name>cd /workspace/llm_py_env

C:\workspace>llm_py_env
# （2）输入 cd Scripts， 回车， 进入虚拟环境目录下的脚本目录
C:\workspace>llm_py_env> cd Scripts
# （3）输入activate， 回车， 执行 activate 命令激活虚拟环境，
C:\workspace\llm_py_env\Scripts>activate

(llm_py_env) C:\workspace\llm_py_env\Scripts>

# （4）输入 cd /workspace/gitee_llm_agent-master, 回车，进入工作目录下的工程目录
(llm_py_env) C:\workspace\llm_py_env\Scripts>cd /workspace/gitee_llm_agent-master

(llm_py_env) C:\workspace\gitee_llm_agent-master>

# (5) 输入 python -m apps.chat.app， 回车，执行启动指令，
(llm_py_env) C:\workspace\gitee_llm_agent-master> python -m apps.chat.app

```

此时，运行时的当前目录 "./" 为项目文件根目录`C:\workspace\gitee_llm_agent-maste`， 启动时会读取当前目录下的的 `cfg.db`, `cfg.yml`, `logging.conf` 这3个文件。

启动后，会看到日志中显示:

```sh
2025-11-26 10:50:26,981 - 126491346956608 - __main__ - INFO -<module> - [251]- listening_port 19000
 * Serving Flask app 'app'
 * Debug mode: off

```

说明程序启动了监听端口 19000，启动正常。接下来，在浏览器中输入 http://127.0.0.1:19000，即可看到相应的页面。
如果运行中看到  `ModuleNotFoundError: No module named 'xxxx`， 则在激活虚拟环境（必选项，非常重要）的条件下执行 `pip install xxxx`。

在Windows `CMD` 的控制台界面中按键 `Ctrl + C`，即可终止当前运行的服务（有时候可能按键后没有反应，等待一段时间即可）。



