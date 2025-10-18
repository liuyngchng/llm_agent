# 系统部署手册
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

## 5. 打包应用

### 5.1 txt2sql
```shell
# 进入项目更目录
cd llm_agent
# 进入 txt2sql 构建目录
cd apps/txt2sql/build
# 创建 python 依赖包的环境
mkdir -p whl_py_dir
# 开始构建，需连接互联网，保持网络畅通
./build_txt2sql.sh



```
