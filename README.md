# 1. introduction

 **(1) http_rag.py**

a RAG demo with local knowledge in private domain, you can input question in URI `http://localhost:19000`;

 **(2) sql_agent.py**

is a SQL agent demo, used so-called TextToSQL. you can ask question about database, and agent will give question back to you

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

