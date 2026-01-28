import uuid

import httpx
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict, NotRequired
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver


class State(TypedDict):
    topic: NotRequired[str]
    joke: NotRequired[str]


model = ChatOpenAI(
    model="deepseek-chat",  # 你的模型名称
    base_url="https://ai.deepseek.com/v1",  # 私有化API地址
    api_key="sk-****",  # 如果有认证
    temperature=0,
    http_client=httpx.Client(verify=False, proxy=None),
)


def generate_topic(state: State):
    """LLM call to generate a topic for the joke"""
    msg = model.invoke("给我提供一个有趣的笑话标题")
    return {"topic": msg.content}


def write_joke(state: State):
    """LLM call to write a joke based on the topic"""
    my_msg = f"以下面的内容主题写一个短笑话： {state['topic']}"
    print(f"my_msg: {my_msg}")
    msg = model.invoke(my_msg)
    return {"joke": msg.content}


# Build workflow
workflow = StateGraph(State)

# Add nodes
workflow.add_node("generate_topic", generate_topic)
workflow.add_node("write_joke", write_joke)

# Add edges to connect nodes
workflow.add_edge(START, "generate_topic")
workflow.add_edge("generate_topic", "write_joke")
workflow.add_edge("write_joke", END)

# Compile
checkpointer = InMemorySaver()
graph = workflow.compile(checkpointer=checkpointer)

if __name__ == "__main__":
    config = {
        "configurable": {
            "thread_id": uuid.uuid4(),
        }
    }
    state = graph.invoke({}, config)

    print(state["topic"])
    print()
    print(state["joke"])