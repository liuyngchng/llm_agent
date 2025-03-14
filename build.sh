docker build --rm -f ./Dockerfile ./ -t llm_agent:1.1
docker images | grep '<none>' | awk -F ' ' '{print $3}' | xargs docker rmi
docker images
