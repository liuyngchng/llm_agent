
# 进入目录
cd cd llm_agent/apps/llm_api_adapter_java

# 编译打包
mvn clean package

# 运行
在当前目录下的 config.xml.template 重命名为 config.xml，在其中配置兼容 OpenAI 的大语言模型 API
java -jar target/llm_api_adapter.jar
