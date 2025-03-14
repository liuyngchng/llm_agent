#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pydantic import BaseModel, Field
from langchain_ollama.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# Define your desired data structure.
class Joke(BaseModel):
    setup: str = Field(description="question to set up a joke")
    punchline: str = Field(description="answer to resolve the joke")

def get_chain():
    chat_model = ChatOllama(model="llama3.2:3B", temperature=0)

    joke_query = "Tell me a joke."

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", "Answer the user query.\n{format_instructions}"),
            ("user", "{query}")
        ])

    chain = prompt_template | chat_model
    #chain.invoke(
    #    {"query": joke_query,
    #     "format_instructions": chat_model.get_output_schema()
    #     })
    print("print ascii of the chain")
    chain.get_graph().print_ascii()

if __name__ == "__main__" :
    """
    output a chain workflow as ascii text in std out.
    """
    get_chain()
