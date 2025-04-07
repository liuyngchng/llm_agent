docker stop llm_agent_app
#docker run -dit --name llm_agent_app --network host --rm \
docker run -dit --name llm_agent_app  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 19001:19000 \
  llm_nl2sql:1.1
