# 1. introduction

 **(1) http_rag.py**

a RAG demo with local knowledge in private domain, you can input question in URI `http://localhost:19000`;

**(2) http_nl2sql.py**

A SQL demo, user can input there question about data, then data returned and be rendered as a chart by chart.js.

 **(3) sql_agent.py**

A SQL agent demo, used so-called TextToSQL. you can ask question about database, and agent will give data back to you

# 2. deploy

env

```sh
Ubuntu 24.02 LTS
Python 3.12.3
pip 24.0
```



you can build docker file as following

```sh
docker build -f ./Dockerfile ./ -t llm_agent:1.0
```

# 3. run

package all your pip package in a docker images named llm_agent with version 1.0.

put all your python script file in dir /data/llm_agent, and run it as followling:

```sh
docker run -dit --name test --network host --rm --security-opt seccomp=unconfined -p 19001:19000 --entrypoint "sh /opt/app/start.sh" -v /data/llm_agent:/opt/app llm_agent:1.0

# maybe you can try set entrypoint to boot procedure automatically
docker run -dit --name test --rm --entrypoint "/opt/app/start.sh" -p 19001:19000 -v /data/llm_agent:/opt/app llm_agent:1.0
```



# 4. test

## 4.1 LLM

test whether your LLM service function normally as following

```sh
#health check for your LLM
curl -X POST http://127.0.0.1:11434/api/generate -d '{
	"model": "llama3.1",
	"prompt": "hi",
	"stream":true
}'
```

## 4.2 LLM agent

 test your LLM agent, have fun!

```sh
# app health check
curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/health' -H "Content-Type: application/json"  -d '{"msg":"who are you?"}'

# submit data
curl -s --noproxy '*' -X POST  'http://127.0.0.1:19000/submit' -H "Content-Type: application/x-www-form-urlencoded"  -d '{"msg":"who are you?"}'
```

# 5. db source config

系统支持自定义数据库配置，目前支持mysql， sqlite，oracle 的支持正在开发中
```html
http://127.0.0.1:19000/cfg/idx?usr=test&tkn=12345
```

# 6. ASR

通过语音转文本，实现再页面上进行语音输入。

## 6.1 基础库安装

安装  ffmpeg

```sh
# windows 
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
# ubuntu
sudo apt install ffmpeg
```



## 6.2 语音识别服务

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

## 6.3 语音识别自测

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

