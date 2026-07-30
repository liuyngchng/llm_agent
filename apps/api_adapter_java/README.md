
# 进入目录
cd cd llm_agent/apps/api_adapter_java

# 编译打包
mvn clean package

# 运行
在当前目录下的 config.yml.template 重命名为 config.yml，在其中配置兼容 OpenAI 的大语言模型 API
java -jar target/api_adapter.jar
