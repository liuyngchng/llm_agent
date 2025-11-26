# 1. 项目介绍

本项目为 `Python` 工程，工程下有多个 `Python` 应用， 每个 "./apps/some_app" 都可以单独工作，是一个Web应用，或者HTTP接口。

 "./common" 文件夹为公共组件，是各 `Python` 应用的共用部分。详细介绍请阅读项目根目录下的 README.md 文件。

# 2. 运行环境配置

下面介绍下 `Windows` 环境下的运行环境配置。

## 2.1 python

本项目为 `Python`项目（代码文件为*.py），需要语言解释器将其翻译为操作系统能理解的可执行文件。

需要下载 `Python`， 版本为 3.12.3

https://www.python.org/downloads/release/python-3123/

下载 `exe` 文件，进行安装。

## 2.2 pip 命令

pip 是 `Python` 程序的依赖包管理工具。相当于自己写了一个 `Python` 文件，同时在源代码中引用了（import ***）别人的 `Python` 文件，那么别人的这部分 `Python` 文件的安装，就由 pip 来负责完成了。

`Windows` 下安装了 `python`， **在安装时务必勾选 “Add Python to PATH”** 选项。`pip` 命令也自动安装了。 接下来在windows 的 `cmd`（**`Win + R`** → 输入 `cmd` → 回车 ) 里执行以下命令，并看到相应的结果，说明安装成功。

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

如果无法执行，可能是安装的时候没有进行环境变量的配置，点击“我的电脑” -> 右键选择“属性” -> 在右侧找到并点击“高级系统设置”，进入环境变量设置，点击右下角的 **“环境变量”** 按钮。

## 2.3 pip package

下载完了代码后，进入代码的根目录，保持计算机连接公共互联网，下载安装包，大约耗费流量10GB。执行以下的命令。

```cmd
pip install -r requirements.txt
```

`requirements.txt` 文件是 `Python` 工程（project）中的依赖包文件清单，告诉使用这个项目的人，此项目下的源代码还依赖哪些第三方组件。

其中部分组件，可能会依赖 `Windows` 操作系统底层的 dll（这是 `Python` 语言的特性决定的，`Python` 的 pip 包也是封装对底层 `C` 语言的封装）。如果在运行时报错，则可以根据报错信息安装 `Windows` 系统的相关组件。

如果使用 `apps/chat2db`, 读取哪种数据库，就需安装哪种数据库的客户端驱动。

## 2.4 安装 `pandoc`

涉及到文档的转换操作，需要依赖这个组件，`pandoc` 是开源社区中较为流行的文档格式转换工具包， `Window` 下安装说明详见  https://www.pandoc.org/installing.html#windows。

## 2.5 SQLite browser

`SQLite browser` 是文件数据库 `SQLite` 的图形化管理工具。本系统使用了 `SQLite` 数据库进行相关的配置，为了通过GUI界面对 `SQLite` 数据库进行操作，需要下载`SQLite browser`。

 `Window` 系统下的安装说明详见链接  https://sqlitebrowser.org/dl/，下载 “DB Browser for SQLite - Standard installer for 64-bit Windows”。

当然，如果对 `SQLite`的相关命令很熟悉，可以忽略此部分。

# 3. 系统配置

下面以通过命令行启动单个应用`apps/chat`程序为例，进行系统配置说明。

## 3.1 cfg.db

文件 `cfg.db` 是项目中很多关系型数据的 `SQLite` 配置文件，不可或缺，一般存在于项目根目录和各个应用根(apps/some_app/)目录

源代码各个应用根目录（apps/some_app/）下的 cfg.db.template 是 `SQLite` 配置数据库模板。

拷贝准备启动的应用（apps/chat/）目录下的 `cfg.db.template` 至项目根目录，并命名为 cfg.db，用SQLite browser 打开可操作相关的配置。

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

以运行`应用` `chat` 为例， 可以在 Windows 控制台（CMD）中通过执行以下命令启动应用。

```sh
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



