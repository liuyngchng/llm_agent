# 1. 功能

 **(1) http_rag.py**

提供 RAG 知识库检索， 以 AI 客服的形式对外提供服务。

**(2) http_nl2sql.py**

通过 Txt2SQL，实现通过自然语言对数据库数据的查询，支持 SQLite, Oracle, MySQL 和 Doris 数据库。

 **(3) http_docx.py**

文档生成。 支持上传 Word docx 文档模板，根据每个段落的写作要求进行文档生成。支持上传包含批注的 Word 文档，根据批注对 相应段落的内容进行修改。

# 2. 其他 

（1）DB数据源。 Txt2SQL 支持用户通过页面自定义数据源

（2）ASR。通过语音转文本，实现在页面上进行语音输入。

# 3. 部署相关

## 3.1 基础库安装

安装  ffmpeg

```sh
# windows 
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
# ubuntu
sudo apt install ffmpeg
```



## 3.2 语音识别服务

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

```sh

```

## 3.3 语音识别自测

目前页面输入的语音流行是webm格式的。测试语音生成

```sh
pip install edge-tts 

# 生成默认音频：
edge-tts -t "测试语句" --write-media temp.webm
# 转码为真实webm：
ffmpeg -i temp.webm -c:a libopus asr_test.webm
```

对http 接口进行测试

```sh
curl -X POST http://127.0.0.1:19000/trans/audio \
  -F "audio=@static/asr_test.webm;type=audio/webm" \
  -H "Content-Type: multipart/form-data"
```

## 3.4 SSH 使用密钥登录
```sh
ssh -i your_private_key_file_path your_user@your_host -p ssh_port

scp -i your_private_key_file_path -P ssh_port your_file_want_to_be_uploaed devbox@your_host:/your_host_dir

```
