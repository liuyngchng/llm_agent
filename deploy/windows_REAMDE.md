# 1. 简介

本文档面向没有编程经验的用户，0 基础在自己的 Windows 10 系统日常办公计算机上部署一个大语言模型智能体。  
项目根目录下的[./deploy/install.bat](./install.bat) 脚本提供一键安装启动功能，请下载文件 `install.bat` 至Windows 的任意文件夹后，选中文件点击右键 -> 以管理员身份运行，即可。  

若进行手动安装，请按照下面的文档说明逐步执行。  

文档中的所有操作已在环境 Windows 10 旗舰版操作系统中进行了验证，各个组件版本如表1-1 所示。

<div align="center"><b>表 1-1 系统组件及版本清单</b></div>

| No.  | 组件              | 版本                                  |
| ---- | ----------------- | ------------------------------------- |
| 1    | 操作系统          | `Windows 10 旗舰版`                   |
| 2    | Python            | `python-3.12.3-amd64`                 |
| 3    | pandoc            | `pandoc-3.8.2.1-windows-x86_64`       |
| 4    | `SQLite`          | `3.45.1`                              |
| 5    | `SQLite`  Browser | `DB Browser for SQLite-v3.13.1-win64` |



* 如果你是一位经验丰富的开发者，则可以跳过 ”`2. 运行环境配置`“ 章节直接查看后面的文档。
* "./" 表示当前的工作目录（Windows 中的某个文件夹下）
* 本项目为 `Python` 工程，工程下有多个 `Python` 应用， 每个 ".`/apps/some_app`" 都可以独立工作，即”`智能体`“，实际上是一个`Web`应用，或者`HTTP`接口。
* "./common" 文件夹为公共组件，是各 `Python` 应用的共用部分。详细介绍请阅读项目根目录下的 `README.md` 文件。

# 2. 环境配置

下面介绍下 `Windows` 环境下的运行环境配置，请按照说明文档进行操作。

## 2.1 python

 `Python`语言的工程（代码文件为`*.py`），需要语言解释器将其翻译为操作系统能理解的可执行文件。类似打开 `*.docx` 文件需要安装 `Office Word` 一样。 

首先下载 `Python`， 版本为 3.12.3（类似下载 Office Word， 版本为2017）

https://www.python.org/downloads/release/python-3123/

下载 `Windows installer (64-bit)` 文件，进行安装。

*** 注意：在安装过程中务必勾选 “Add Python to PATH” 选项。若没有勾选，后续需要手动进行环境变量配置。这个操作是在 Windows` CMD` 下输入 python 命令能够正确被操作系统理解的基础。***

接下来在windows 的 `CMD 控制台`（**`Win + R`** → 输入 `cmd` → 回车 ) 里执行以下命令，并可以看到相应的结果，说明安装成功。

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

## 2.2 工作目录创建

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

## 2.3 下载源代码

 打开页面 https://gitee.com/liuyngchng/gitee_llm_agent  ， 点击 ”`克隆/下载`“ 按钮， 选择右上角的 ”`下载ZIP`“， 浏览器会下载一个文件 `gitee_llm_agent-master.zip`。 将这个zip包拷贝至文件夹 `C:\workspace` 下，鼠标选中这个 zip 文件， 右键-> 解压到当前目录， 会看到生成新的目录 `C:\workspace\gitee_llm_agent-master`， 该文件夹下的 文件清单如下所示。

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



## 2.4 虚拟环境

### 2.4.1 创建

接下来将在目录 `C:\workspace\llm_py_env` 下创建虚拟环境，这个目录将作为 `python.exe` 的新家，以及下载的所有关联文件的目录，后续不需要的时候只要删除这个目录就可以把自己的电脑清理干净了。

**（1）安装创建虚拟环境命令 `virtualenv`。**

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspace, 回车，进入工作目录
C:\Users\your_name>cd /workspace

C:\workspace>
# （2）输入 pip install virtualenv， 回车， 安装创建虚拟环境的命令
C:\workspace>pip install virtualenv
Requirement already satisfied: virtualenv in c:\program files\python312\lib\site-packages (20.35.4)

```
**（2）创建虚拟环境**

打开 Windows `CMD 控制台` 窗口（**`Win + R`** → 输入 `cmd` → 回车 )，执行以下命令：

```cmd
# （1）输入 cd /workspace, 回车，进入工作目录
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
# （1）输入 cd /workspace, 回车，进入工作目录
C:\Users\your_name>cd /workspace

C:\workspace>
# （2）输入 virtualenv llm_py_env，回车，将自动创建目录 llm_py_env，即 C:\workspace\llm_py_env
C:\workspace> virtualenv llm_py_env
```

此时，打开 `C:\workspace` 文件夹 ，会看到有一个新文件夹 `llm_py_env`，说明虚拟环境创建成功。

### 2.4.2 激活

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

## 2.5 安装依赖组件

接下来安装 `Python` 应用程序的依赖包，在安装依赖包前，必须先激活虚拟环境。

### 2.5.1 激活虚拟环境

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

### 2.5.2 安装依赖

 接下来开始安装依赖， 保持网络畅通，这个过程消耗时间1~2小时，具体取决于你的网络环境，请耐心等待。

```cmd
# 执行 pip install 命令, 中途若中断或窗口关闭，则从2.6节开始重新一步一步执行
(llm_py_env) C:\workspace\gitee_llm_agent-master>pip install -r requirements.txt
```

执行成功后， `C:\workspace\llm_py_env` 这个文件夹（虚拟环境文件夹）大约为 `4GB`，包含了软件运行的所有依赖。

### 2.5.3 安装 `pandoc`

通过Windows msi 引导文件安装， 详见  https://www.pandoc.org/installing.html#windows 。

# 3. 软件配置

下面以启动单个应用`apps\chat`程序为例，进行系统配置说明。每次选定将要启动的应用(例如 `apps/chat`)后, 需要将 `apps/chat`目录下的 `cfg.db.template`, `cfg.yml.template`, `logging.conf` 这三个文件拷贝至项目根目录，并重新命名为 `cfg.db`, `cfg.yml`, `logging.conf` ，以 `apps/chat` 为例，如表 3-1 所示。

<div align='center'> <b>表 3-1 配置文件操作清单</b> </div>

| No.  | 原来的目录                                                   | 新目录                                             | 操作                                       |
| ---- | ------------------------------------------------------------ | -------------------------------------------------- | ------------------------------------------ |
| 1    | `C:\workspace\gitee_llm_agent-master\apps\chat\cfg.db.template` | `C:\workspace\gitee_llm_agent-master\cfg.db`       | 拷贝、粘贴、重命名即可                     |
| 2    | `C:\workspace\gitee_llm_agent-master\apps\chat\cfg.yml.template` | `C:\workspace\gitee_llm_agent-master\cfg.yml`      | 拷贝、粘贴、重命名后，还需配置大模型 `API` |
| 3    | `C:\workspace\gitee_llm_agent-master\apps\chat\logging.conf` | `C:\workspace\gitee_llm_agent-master\logging.conf` | 拷贝、粘贴即可                             |

如果启动别的应用，例如 `apps\chat2db`， 则将文档中所有路径中的 `apps\chat`替换为 `apps\chat2db`。

## 3.1 `cfg.db`

拷贝需要启动的应用目录下的 cfg.db （例如， `apps/chat`下的 `cfg.db`）至项目根目录即可， 如表 3-1所示。

## 3.2 `cfg.yml`

 拷贝各个应用根目录（`C:\workspace\gitee_llm_agent-master\apps\chat\`）下的 `cfg.yml.template` 文件至项目根目录`C:\workspace\gitee_llm_agent-master`，重命名为 `cfg.yml`， 配置相应信息。`cfg.yml` 中的*** 大语言模型 `API` 相关配置是必须配置的，否则软件无法正常运行。***算力资源可以使用企业内部部署的算力资源，或公共互联网【 Deepseek官网 (https://platform.deepseek.com/) 或其他大厂 】`API`。

## 3.3 logging.conf

`logging.conf` 为项目的日志配置文件，用于记录日志， 拷贝需要启动的应用目录下的 cfg.db （例如， `apps/chat`下的 `logging.conf`）至项目根目录即可， 如表 3-1所示。

# 4. 运行程序

## 4.1 运行

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

# (5) 输入 pythonw -m apps.chat.app， 回车，执行启动指令，
(llm_py_env) C:\workspace\gitee_llm_agent-master> python -m apps.chat.app

```

此时，运行时的当前目录 "./" 为项目文件根目录`C:\workspace\gitee_llm_agent-maste`， 启动时会读取当前目录下的的 `cfg.db`, `cfg.yml`, `logging.conf` 这3个文件。

启动后，会看到控制台或者根目录下的文本文件 apps.xxxx.log  中看到:

```powershell
2025-11-01 10:50:26,981 - 126491346956608 - __main__ - INFO -<module> - [251]- listening_port 19000
 * Serving Flask app 'app'
 * Debug mode: off
```

说明程序启动了监听端口 19000，启动正常。接下来，在浏览器（强烈建议使用Chrome 浏览器，其他浏览器未进行验证）中输入 http://127.0.0.1:19000 ，即可看到相应的页面。
如果运行中看到  `ModuleNotFoundError: No module named 'xxxx`， 则在激活虚拟环境（必选项，非常重要）的条件下执行 `pip install xxxx`。

## 4.2 停止

按`Ctrl + C`键，等待程序从控制台窗口退出（需要等待一会儿）。或者，进入 Windows 的进程管理器，按照名称进行排序，杀死名称为 Python 的进程即可。



