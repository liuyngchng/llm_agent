import os
import uuid
from typing import Literal
import pprint  # 引入格式化打印模块

from deepagents.backends import StateBackend,FilesystemBackend, CompositeBackend, StoreBackend
from langgraph.checkpoint.memory import MemorySaver, InMemorySaver
from langgraph.store.memory import InMemoryStore
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_deepseek import ChatDeepSeek
from langchain.tools import tool
from dotenv import load_dotenv


load_dotenv()  # 加载.env文件
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DEEPSEEK_API_KEY = os.getenv("API_DEEPSEEK_KEY")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """运行网络搜索，返回Tavily API的搜索结果

    参数:
        query: 搜索关键词
        max_results: 返回的最大结果数
        topic: 搜索主题类型，仅支持 "general"(通用)/"news"(新闻)/"finance"(财经)
        include_raw_content: 是否包含原始页面内容

    返回:
        包含搜索结果的字典，若失败返回error字段
        """
    try:
        return tavily_client.search(
            query=query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
    except Exception as e:
        return {"error": f"搜索失败：{str(e)}"}


# 3. 打印InMemoryStore内容的核心方法
def print_in_memory_store(store: InMemoryStore):
    """打印InMemoryStore的所有内容（兼容不同版本）"""
    # 步骤1：获取底层存储字典（核心：_data 或 data 属性）
    try:
        # 主流版本（0.3.x）：_data 是底层存储字典
        store_data = store._data
    except AttributeError:
        # 旧版本：data 是底层存储字典
        store_data = store.data

    # 步骤2：打印内容（友好格式）
    print("===== InMemoryStore 内容 =====")
    if not store_data:
        print("InMemoryStore 为空")
        return

    # 遍历键值对，清晰打印
    for key, value in store_data.items():
        print(f"🔑 键：{key}")
        print(f"📝 值：{value}\n")


# 用于引导智能体成为专业研究员的系统提示词
research_instructions = """你是一名专业研究员。核心工作是开展全面深入的调研，进而撰写一份高质量的研究报告并将最终的报告以markdown格式输出到本地路径中。
将报告的文件名和摘要保存到/memories/summery.md中，方便下次调用方面。
你可使用一款互联网搜索工具，作为搜集信息的主要途径。
internet_search 工具说明
该工具用于针对指定的查询内容执行互联网搜索。你可以设定需要返回的最大结果数量、指定搜索主题，以及选择是否需要包含原始内容。
"""
# 初始化DeepSeek大语言模型
llm =ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=8192,
        api_key=DEEPSEEK_API_KEY,
        )
#创建内存存储和检查点
memory_store = InMemoryStore()
checkpointer = InMemorySaver()

#创建复合型的后端
composite_backend = lambda rt: CompositeBackend(
        default=FilesystemBackend(root_dir="./fs", virtual_mode=True),
        routes={
            "/memories/": StoreBackend(rt)
        }
    )

agent = create_deep_agent(
    model=llm,
    tools=[internet_search],
    backend = composite_backend,
    store=memory_store, #为StoreBackend指定物理存储方式
    checkpointer=checkpointer,
    system_prompt=research_instructions
)

# 执行智能体
if __name__ == "__main__":
    config1 = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = agent.invoke({"messages": [{"role": "user", "content": "请介绍一下人工智能的发展历史。"}]}, config=config1)
    # result = agent.invoke(HumanMessage(content="请介绍一下人工智能的发展历史。"))

    # Thread 2: Read from long-term memory (different conversation!)
    config2 = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result1=agent.invoke({"messages": [{"role": "user", "content": "你刚在做什么研究?"}]}, config=config2
    )

    # Print the agent's response
    # 格式化打印全部内容
    pp = pprint.PrettyPrinter(indent=2)  # 设置缩进为2，更美观
    print("=== 格式化后的完整 result 内容 ===")
    pp.pprint(result)
    print_in_memory_store(memory_store)
    pp.pprint(result1)