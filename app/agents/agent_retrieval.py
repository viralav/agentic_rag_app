import threading
from typing import Any, AsyncGenerator, Dict, Iterator, List, Optional
from langchain_core.documents.base import Document
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from app.services.sharepoint_service import set_gpt_model
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from app.utils.utils_openai_prompt import (
    DOCUMENT_RETRIEVAL_PROMPT,
    FOLLOWUP_QUESTION_PROMPT,
    VECTOR_STORE_RETRIEVAL_PROMPT,
    CREATIVE_WRITING_PROMPT,
    AZURE_OPENAI_GPT4o_mini_MODEL,
    OPENAI_PROMPT_CREATE_QUERY,
    AZURE_OPENAI_GPT4o_MODEL,
    FINAL_FOLLOWUP_QUESTION_PROMPT,
    QUERY_ROUTER,
    AMBIGUITY_FOLLOWUP_PROMPT,
)
from app.config.set_logger import set_logger

logger = set_logger()

llm_gpt4o_mini = set_gpt_model(AZURE_OPENAI_GPT4o_MODEL).create_llm_instance()
llm_gpt4o = set_gpt_model(AZURE_OPENAI_GPT4o_MODEL).create_llm_instance()


def extract_llm_text(text: str) -> str:
    """Extract Gremlin code from a text."""
    text = text.replace("`", "")
    if text.startswith("gremlin"):
        text = text[len("gremlin") :]
    if text.startswith("json"):
        text = text[len("json") :]
    return text.replace("\n", "")


class AgentRetrieval:
    def __init__(self):
        self.llm_gpt4o_mini = llm_gpt4o_mini
        self.llm_gpt4o = llm_gpt4o

    def rephrase_user_query(self):  # -> RunnableSerializable[dict, str]:
        rephrase_query_generator = PromptTemplate(
            input_variables=["chat_history", "raw_query"],
            template=OPENAI_PROMPT_CREATE_QUERY,
        )
        return rephrase_query_generator | self.llm_gpt4o | JsonOutputParser()

    def ambiguity_resolver(self):  # -> RunnableSerializable[dict, str]:
        ambiguity_resol = PromptTemplate(
            input_variables=["raw_query"],
            template=AMBIGUITY_FOLLOWUP_PROMPT,
        )
        return ambiguity_resol | self.llm_gpt4o_mini | StrOutputParser()

    def query_type_finder(self):
        query_router = PromptTemplate(
            input_variables=["rephrased_query"],
            template=QUERY_ROUTER,
        )
        return query_router | self.llm_gpt4o | JsonOutputParser()

    def retrieved_documents_grader(self):
        prompt = PromptTemplate(
            template=DOCUMENT_RETRIEVAL_PROMPT,
            input_variables=["rephrased_query", "vector_doc"],
        )

        return prompt | self.llm_gpt4o_mini | JsonOutputParser()

    def vector_based_final_answer_generation(self):
        final_answer_generation_prompt = PromptTemplate(
            input_variables=[
                "vector_doc",
                "rephrased_query",
                "raw_query",
                "chat_history",
            ],
            template=VECTOR_STORE_RETRIEVAL_PROMPT,
        )
        return final_answer_generation_prompt | self.llm_gpt4o | StrOutputParser()

    def web_based_final_answer_generation(self):
        final_answer_generation_prompt = PromptTemplate(
            input_variables=["rephrased_query", "raw_query"],
            template=CREATIVE_WRITING_PROMPT,
        )
        return final_answer_generation_prompt | self.llm_gpt4o_mini | StrOutputParser()

    def followup_question_generator(self):
        prompt = PromptTemplate(
            template=FOLLOWUP_QUESTION_PROMPT,
            input_variables=["raw_query", "vector_doc", "final_answer"],
        )
        return prompt | self.llm_gpt4o_mini | StrOutputParser()

    def response_when_no_document(self):
        prompt = PromptTemplate(
            template=FINAL_FOLLOWUP_QUESTION_PROMPT,
            input_variables=["raw_query"],
        )
        return prompt | self.llm_gpt4o_mini | StrOutputParser()
