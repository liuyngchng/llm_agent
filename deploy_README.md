 <center><h1>系统部署手册</h1></center>

## 1. 获取源代码
```sh
# 从 github 获取源代码
git clone https://github.com/liuyngchng/llm_agent.git
# 无法上 github 的可以从 gitee 获取源代码
git clone https://gitee.com/liuyngchng/gitee_llm_agent.git
```
## 2. 部署环境
宿主机需要为 Linux 系统， 安装有 docker 运行环境，应用最终打包为 docker 镜像，在服务器上进行部署。  
宿主机环境为:

```sh
Ubuntu 24.04 LTS
docker: 28.2.2
python: 3.12.3
pip 24.0
virtualenv 20.25.0
```
docker 镜像内部最终的环境如下所示。  
注意需要保持容器内的 python 版本与宿主机一致，这样下载的python依赖包可以直接复用，可以大大缩短打包时间。

```sh
Linux: 6.14.0-33-generic
python: 3.12.3
pip 24.0
virtualenv 20.25.0
```
## 3. 下载基础 docker 镜像

```sh
# 下载 ubuntu:24.04
docker pull ubuntu:24.04
# 查看基础镜像
docker images
REPOSITORY              TAG       IMAGE ID       CREATED        SIZE
ubuntu                  24.04     a04dc4851cbc   8 months ago   78.1MB

```

## 4. 创建 Python 环境镜像
```sh
# 进入项目根目录
cd llm_agent
# 进入build 目录
cd common/build
# 开始构建 python 环境镜像，这里需要连接互联网，需保持网络畅通
./build_py_env.sh
```
构建成功后，查看镜像
```shell
docker images
REPOSITORY              TAG       IMAGE ID       CREATED         SIZE
ubuntu_py               24.04     449ac32f606b   4 minutes ago   1.28GB
```

## 5. 应用打包

### 5.1 准备事项

```sh
# 如果显示无执行权限，执行 
chmod +x ./my_script.sh
# 确保网络环境中无代理，保持网络畅通，可以执行以下脚本清除代理环境变量
unset https_proxy ftp_proxy NO_PROXY FTP_PROXY HTTPS_PROXY HTTP_PROXY http_proxy ALL_PROXY all_proxy no_proxy
env | grep proxy -i
```

### 5.1 数据库查询应用(`chat2db`)
```shell
# 进入项目更目录
cd llm_agent
# 进入 chat2db 构建目录
cd apps/chat2db/build
# 开始构建，需连接互联网，保持网络畅通,
./build_chat2db.sh
```

### 5.2 文档生成应用(`docx`)
```shell
# 进入项目更目录
cd llm_agent
# 进入 chat2db 构建目录
cd apps/docx/build
# 开始构建，需连接互联网，保持网络畅通
./build_docx.sh
```
## 6. 部署

### 6.1 llm_agent 

在服务器的根目录下创建文件夹 /data, 并给予写文件夹的权限。

下面以启动`chat2db` 应用为例, 启动命令如下：

```shell
cd /
# 在文件系统根目录下创建 data文件夹， 
# 如果在其他位置（例如,/opt 等）创建，则需要修改相应的部署、启动等脚本，只要能够匹配就行。
sudo mkdir data
# 将 /data 目录的所有权修改为当前用户，保证当前用户有写权限
sudo chown $USER:$USER /data
# 拷贝部署包到指定的目录下
cp llm_agent.tar /data
# 进入部署目录
cd /data
# 解压部署包
tar -xvf llm_agent.tar
# 进入程序根目录
cd llm_agent
# 执行部署脚本
./apps/chat2db/deploy/deploy_chat2db.sh
```

### 6.2 达梦数据库

部署方法详见 

[达梦数据库部署说明]: https://github.com/liuyngchng/rd.lab/blob/master/dmdb.md

https://github.com/liuyngchng/rd.lab/blob/master/dmdb.md 或

https://gitee.com/liuyngchng/gitee_rd.lab/blob/master/dmdb.md

对于应用 `chat2db`, 如果需要访问达梦数据库，需要将达梦客户端的动态库拷贝至 /data/dm8_client 目录。

### 6.3 `mermaid` 服务

`mermaid` 服务用于将 `mermaid` 脚本转换为对应的图片（`JPG` ，`PNG`）， 在文档生成应用(apps/docx) 中会用到，部署方法详见

https://github.com/liuyngchng/rd.lab/blob/master/all_README.md 或

https://gitee.com/liuyngchng/gitee_rd.lab/blob/master/all_README.md 中的章节 "`77. mermaid 图形服务器`"。 



## 7. 测试

浏览器中打开如下地址，推荐使用 Chrome。
```shell 
https://localhost:19001
```

