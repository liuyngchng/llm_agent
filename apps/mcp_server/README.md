# 1. goal

提供 一个 MCP serer，为 MCP client 提供可调用工具查询服务。  
相当于一个可调用工具的注册中心， MCP Client 可以从这里获取可调用的工具列表，以及这些工具的调用方法（工具地址、输入参数、输出参数）

# 2. pip 依赖包

```shell
pip install mcp_server mcp_server[cli] concurrent_log_handler pyyaml gunicorn \
  flask
```

# 3. MCP 工作时序

执行过程时序如下所示

```sequence
客户端->>MCP服务框架: 发送用户请求("北京天气？")
MCP服务框架->>大模型: 转发请求(携带工具定义)
大模型-->>MCP服务框架: 返回工具调用请求(结构化MCP格式)
MCP服务框架->>Tool: 自动路由+执行 get_current_weather("北京")
Tool-->>MCP服务框架: 返回天气数据(25°C)
MCP服务框架->>MCP服务框架: 自动封装结果(MCP格式)
大模型-->>MCP服务框架: 返回自然语言响应
MCP服务框架->>客户端: "北京当前气温25摄氏度"
```

**（1）Tool。**在Tool 中，各种工具接口， 由用户自行实现后， 注册（暴露）给 MCP 服务框架。 例如查询天气，查询股票，查询火车票等。

**（2）客户端（GUI）。**当用户输入问题时，将用户的问题提交给 LLM（LLM 需支持 tools 调用），同时获取 MCP 服务框架 上的 tools 清单（接口签名清单）提交给 LLM。

**（3）MCP服务框架（MCP Server、 MCP Client）。** MCP服务框架根据 LLM 返回的消息、工具调用信息，自动调用相应的 tool（MCP server 提供的 API），获取tools 调用结果后，再次提供给 LLM，开启多轮对话。这个过程有多个回合，直到 LLM 返回的信息只有消息，不再进行工具调用为止。

**（4）大语言模型(LLM)。** LLM需支持 tools 调用（function 调用），当输入参数中含有系统信息、用户信息、以及 tools 信息时，在输出参数中会有消息、是否调用 tools 以及 调用哪些tools、调用相应的tools入参清单等。

经过以上几个步骤，最终形成由 MCP服务框架驱动， LLM 提供智能能力的，自动调用客户自行实现的系统能力（工具集合）的一个全自动系统，为用户提供一站式信息服务的能力。
