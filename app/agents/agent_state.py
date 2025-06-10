import asyncio
import json
from typing import Annotated, Any, List, Literal
import uuid
import openai
import os
import datetime
from azure.core.exceptions import ServiceResponseError
from app.agents.agent_retrieval import AgentRetrieval, extract_llm_text
from typing_extensions import TypedDict
from app.services.sharepoint_service import semantic_logic_multi_index_retrieval
from app.config.set_logger import set_logger

from app.services.cosmos_service import CosmosService
from app.services.authentication_service import AuthenticationService
from app.services.user_validation_service import UserValidationService
from app.services.team_messaging_service import TeamsMessagingService
from app.services.azure_blob_service import AzureBlobService
from app.services.openai_service import OpenAIService
from app.services.dalle3_service import DallE3Service
from app.services.token_validation_service import TokenValidationService

from app.services.dalle3_service import DallE3Service
from app.utils.util_url_generator import UtilUrlGenerator
from app.utils.util_helper_methods import HelperMethods
from app.config.constants import (
    COSMOS_HOST, 
    COSMOS_KEY, 
    COSMOS_DATABASE, 
    COSMOS_USER_INTERACTIONS_CONTAINER, 
    COSMOS_IMAGES_INFO_CONTAINER, 
    COSMOS_REPLY_TO_ID_CONTAINER,
    MICROSOFT_TENANT_ID, 
    MICROSOFT_APP_ID, 
    MICROSOFT_APP_SECRET, 
    BLOB_ACCOUNT_NAME, 
    BLOB_ACCOUNT_KEY, 
    BLOB_CONTAINER_NAME, 
    OPEN_AI_BASE_URL, 
    OPEN_AI_KEY, 
    OPEN_AI_DEPLOYMENT_NAME, 
    OPEN_AI_VERSION,
    OPEN_AI_DALLE_DEPLOYMENT_NAME
)

logger = set_logger()

agent_retrieval = AgentRetrieval()

cosmos_service = CosmosService(os.getenv(COSMOS_HOST), os.getenv(COSMOS_KEY), os.getenv(COSMOS_DATABASE), os.getenv(COSMOS_USER_INTERACTIONS_CONTAINER), os.getenv(COSMOS_IMAGES_INFO_CONTAINER), os.getenv(COSMOS_REPLY_TO_ID_CONTAINER))
token_validation_service = TokenValidationService(os.getenv(MICROSOFT_TENANT_ID))
authentication_service = AuthenticationService(os.getenv(MICROSOFT_TENANT_ID), os.getenv(MICROSOFT_APP_ID), os.getenv(MICROSOFT_APP_SECRET), token_validation_service)
user_validation_service = UserValidationService(os.getenv(MICROSOFT_TENANT_ID), os.getenv(MICROSOFT_APP_ID), os.getenv(MICROSOFT_APP_SECRET))
team_messaging_service = TeamsMessagingService()
azure_blob_service = AzureBlobService(os.getenv(BLOB_ACCOUNT_NAME), os.getenv(BLOB_ACCOUNT_KEY), os.getenv(BLOB_CONTAINER_NAME))
openai_service = OpenAIService(UtilUrlGenerator.create_open_ai_url(os.getenv(OPEN_AI_BASE_URL), os.getenv(OPEN_AI_DEPLOYMENT_NAME)), os.getenv(OPEN_AI_KEY), os.getenv(OPEN_AI_DEPLOYMENT_NAME), os.getenv(OPEN_AI_VERSION))
dalle3_service = DallE3Service(UtilUrlGenerator.create_open_ai_url(os.getenv(OPEN_AI_BASE_URL), os.getenv(OPEN_AI_DALLE_DEPLOYMENT_NAME)) , os.getenv(OPEN_AI_KEY), os.getenv(OPEN_AI_DALLE_DEPLOYMENT_NAME), os.getenv(OPEN_AI_VERSION))


async def robust_llm_call(llm_chain, input_data, max_retries=3, backoff_strategy=None):
    """
    Makes a call to the LLM with retry logic and error handling.

    Args:
        llm_chain: The LLM chain to invoke.
        input_data: The input data for the LLM.
        max_retries: Maximum number of retry attempts.
        backoff_strategy: Function to determine backoff time based on attempt number.

    Returns:
        A dictionary with the response or error information.
    """
    if backoff_strategy is None:
        backoff_strategy = lambda attempt: 2**attempt

    for attempt in range(max_retries):
        try:
            response = await llm_chain.ainvoke(
                input_data,
                return_exceptions=True,
            )
            logger.info(f"LLM call succeeded on attempt {attempt + 1}")
            logger.info(f"the response for the poetry prompt is as below: \n\n {response}")
            return {"success": True, "response": response}
        except (openai.RateLimitError, ServiceResponseError) as e:
            logger.error(
                f"Timeout error on attempt {attempt + 1} with input {input_data}: {str(e)}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_strategy(attempt))
            else:
                return {
                    "success": False,
                    "error": "OpenAI API Limit error. Please try again later",
                }

        except Exception as e:
            logger.debug(f"")
            logger.exception("An unexpected error occurred during LLM call.")
            return {
                "success": False,
                "error": "An unexpected error occurred during LLM call. Please contact bot admin if this error persists",
            }


async def grade_document(retrieval_grader, question, document):
    """Helper function to grade a single document."""

    score = await robust_llm_call(
        llm_chain=retrieval_grader,
        input_data={"rephrased_query": question, "vector_doc": document},
    )
    return score, document


class ChatAgent(TypedDict):
    """
    Represents the state of our langraph chat agent.

    Attributes:
        question: question
        generation: LLM generation
        vector_doc: list of vector_store documents
    """

    user_id: str
    ambiguity_status: str
    bool_upload_index: bool
    allowed_index: List[str]
    chat_history: List[str]
    datasource: str
    assessment: List[str]
    raw_query: str
    rephrased_query: str
    vector_doc: List[str]
    filenames: List[str]
    final_answer: str
    awaiting_user_input: bool
    error_occurred: bool
    data: dict
    image_answer: dict


async def handle_error(state: ChatAgent):
    """
    Handles errors that occur during the workflow.

    Args:
        state (dict): The current graph state.

    Returns:
        dict: Updated state with error information.
    """
    logger.error("---ERROR HANDLING---")
    error_message = state.get(
        "final_answer",
        "An unknown error occurred. Please try again or contact bot admin to resolve the issue!",
    )
    state["awaiting_user_input"] = True
    return {
        "final_answer": error_message,
        "error_occurred": True,
    }


async def rephrase_query(state: ChatAgent):
    """
    Generates a rephrased query based on chat history and user query
    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains rephrased query
    """
    logger.info("---REPHRASE QUERY---")
    question = state["raw_query"]
    chat_history = state["chat_history"]
    rephrase_chain = agent_retrieval.rephrase_user_query()
    rephrased_query = await robust_llm_call(
        llm_chain=rephrase_chain,
        input_data={"raw_query": question, "chat_history": chat_history},
    )
    if "error" in rephrased_query:
        return {"final_answer": rephrased_query["error"], "error_occurred": True}

    if isinstance(rephrased_query, dict):
        cleaned_output = rephrased_query
    elif isinstance(rephrased_query, str):
        cleaned_output = json.loads(rephrased_query)
    logger.debug("### Rephrased query: %s", cleaned_output)

    return {
        "rephrased_query": cleaned_output["response"]["output"],
        "ambiguity_status": cleaned_output["response"]["output"],
        "error_occurred": False,
    }


async def followup_ambiguous_queries(state: ChatAgent):
    logger.info("---FOLLOWUP AMBIGUOUS QUESTION---")
    question = state["raw_query"]
    followup_chain = agent_retrieval.ambiguity_resolver()
    followup_query = await robust_llm_call(
        llm_chain=followup_chain,
        input_data={"raw_query": question},
    )
    if "error" in followup_query:
        return {"final_answer": followup_query["error"], "error_occurred": True}
    return {"final_answer": followup_query["response"], "error_occurred": False}


async def route_question(state: ChatAgent):
    logger.info("---ROUTE QUESTION---")
    question = state["rephrased_query"]
    rephrase_chain = agent_retrieval.query_type_finder()
    query_source = await robust_llm_call(
        llm_chain=rephrase_chain,
        input_data={"rephrased_query": question},
    )
    if "error" in query_source:
        return {"final_answer": query_source["error"], "error_occurred": True}

    return {
        "datasource": query_source["response"]["datasource"],
        "error_occurred": False,
    }


async def web_based_answer(state: ChatAgent):
    logger.info("---WEB BASED ANSWERING---")
    rephrased_query = state["rephrased_query"]
    raw_query = state["raw_query"]
    web_chain = agent_retrieval.web_based_final_answer_generation()
    web_answer = await robust_llm_call(
        llm_chain=web_chain,
        input_data={"rephrased_query": rephrased_query, "raw_query": raw_query},
    )
    if "error" in web_answer:
        return {"final_answer": web_answer["error"], "error_occurred": True}

    return {"final_answer": web_answer["response"], "error_occurred": False}


async def vector_retrieve(state: ChatAgent) -> dict[str, Any]:
    """
    Retrieve documents from vectorstore

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains retrieved documents
    """
    logger.info("---VECTOR RETRIEVE---")
    rephrased_query = state["rephrased_query"]
    user_id = state["user_id"]
    bool_upload_index = True
    documents = await semantic_logic_multi_index_retrieval(
        query=rephrased_query,
        data_sources=state["allowed_index"],
        upload_index=bool_upload_index,
    )
    if "vector_doc" in state and documents:
        vector_doc = state["vector_doc"] + documents
    else:
        vector_doc = documents

    logger.debug("### Total Documents retrieved. %s", len(vector_doc))
    return {"vector_doc": vector_doc}


async def image_based_answer(state: ChatAgent):
    data = state["data"]
    rephrased_query =  state["rephrased_query"]
    logger.info(
        "Processing image query", 
        extra=HelperMethods.add_logging_context(data)
    )
    try:
        response = await dalle3_service.generate_image(rephrased_query)
    except Exception as err:
        response = {"response": "Error occured while performing image based processing. Please contact your administrator"}
    blob_name = azure_blob_service.upload_file(response["data"][0]["url"])
    signed_url = azure_blob_service.generate_sas_url(blob_name)
    logger.info(
        f"Image generated and uploaded to blob storage. Blob URL: {signed_url}", 
        extra=HelperMethods.add_logging_context(data)
    )

    return {
        "final_answer": {
            "revised_prompt": response["data"][0]["revised_prompt"],
            "blob_name": blob_name,
            "signed_url": signed_url,
        },
        "error_occurred": False
    }


async def grade_documents(state: ChatAgent):
    """
    Determines whether the retrieved documents are relevant to the question
    If any document is not relevant, we will set a flag to run follow up questions

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Filtered out irrelevant documents and updated web_search state
    """

    logger.info("---CHECK DOCUMENT RELEVANCE TO QUESTION---")
    question = state["rephrased_query"]
    documents = state["vector_doc"]
    filtered_docs = []
    assessment_list = []
    filename_list = []
    awaiting_user_input = False
    retrieval_grader = agent_retrieval.retrieved_documents_grader()
    tasks = [grade_document(retrieval_grader, question, d) for d in documents]
    results = await asyncio.gather(*tasks)
    for score, d in results:

        if "error" in score:
            state["error_occurred"] = True
            logger.debug("### Error status in state: %s", state["error_occurred"])
            return {"final_answer": score["error"], "error_occurred": True}
        cleaned_response = score["response"]
        grade = cleaned_response["score"]
        assessment_list.append(cleaned_response["assessment"])
        if grade.lower() == "yes" or grade.lower() == "maybe":
            logger.info("---GRADE: DOCUMENT RELEVANT---")
            filtered_docs.append(d)
            filename_list.append(cleaned_response["name"])
        else:
            logger.info("---GRADE: DOCUMENT NOT RELEVANT---")
            awaiting_user_input = True

    state["vector_doc"] = filtered_docs
    state["awaiting_user_input"] = awaiting_user_input
    return {
        "vector_doc": filtered_docs,
        "awaiting_user_input": awaiting_user_input,
        "assessment": assessment_list,
        "filenames": filename_list,
        "error_occurred": False,
    }


def route_based_on_graded_document(
    state: ChatAgent,
) -> Literal["generate"] | Literal["followup"]:
    """Routes to follow up or vector generate based on graded documents"""
    logger.info("---ROUTE END NODE---")
    vector_documents = state["vector_doc"]
    if state.get("error_occurred"):
        return "handle_error"
    if vector_documents:
        return "generate"
    else:
        return "followup"


async def vector_generate(state: ChatAgent):
    """Generates answers based on vector query results"""
    logger.info("---VECTOR ANSWER GENERATE---")
    raw_query = state["raw_query"]
    rephrased_query = state["rephrased_query"]
    vector_documents = state["vector_doc"]
    metadata = [
        f'{d.metadata["source"]}-score:{d.metadata["score"]}' for d in vector_documents
    ]
    logger.debug("### Fetched documents: %s", metadata)
    chat_history = state["chat_history"]
    generation = "No vector results"
    if vector_documents:
        logger.debug(
            "Number of documents for answer generation: %s", len(vector_documents)
        )
        rag_chain = agent_retrieval.vector_based_final_answer_generation()
        generation = await robust_llm_call(
            llm_chain=rag_chain,
            input_data={
                "raw_query": raw_query,
                "rephrased_query": rephrased_query,
                "vector_doc": vector_documents,
                "chat_history": chat_history,
            },
        )
        if "error" in generation:
            return {"final_answer": generation["error"], "error_occurred": True}

        return {
            "final_answer": generation["response"],
            "error_occurred": False,
            "awaiting_user_input": False,
        }
    else:
        logger.info("## No relevant vector documents retrieved for the query")
        final_followup_chain = agent_retrieval.response_when_no_document()
        final_followup = await robust_llm_call(
            llm_chain=final_followup_chain, input_data={"raw_query": raw_query}
        )
        if "error" in generation:
            return {"final_answer": final_followup["error"], "error_occurred": True}
        return {
            "awaiting_user_input": False,
            "final_answer": final_followup["response"],
            "error_occurred": False,
        }


async def generate_followup_question(state: ChatAgent):
    """
    Generate a follow-up question using the LLM if documents are not found.

    Args:
        state (dict): The current graph state.

    Returns:
        dict: Updated state with the follow-up question.
    """
    original_question = state["raw_query"]
    vector_documents = state["vector_doc"]
    logger.info("original_question %s", original_question)
    llm_response_chain = agent_retrieval.followup_question_generator()
    llm_response = await robust_llm_call(
        llm_chain=llm_response_chain,
        input_data={
            "raw_query": original_question,
            "vector_doc": vector_documents,
            "final_answer": state["final_answer"],
        },
    )
    if "error" in llm_response:
        return {"final_answer": llm_response["error"], "error_occurred": True}
    llm_response_final = llm_response["response"]
    logger.info("Follow up Question %s", llm_response_final)
    return {
        "final_answer": llm_response_final,
        "awaiting_user_input": True,
        "error_occurred": False,
    }


def route_vector_generation(state: ChatAgent):
    """Routes the workflow based on vector_generate output state"""

    error_occurred = state.get("error_occurred", False)
    awaiting_user_input = state.get("awaiting_user_input", False)

    if error_occurred:
        return "handle_error"

    if awaiting_user_input:
        return "generate_followup"
    return "end"


def get_llm_response_from_state(value: dict):
    """
    Extract message text with priority and explicit empty string handling

    Args:
        value (dict): State dictionary

    Returns:
        str: Extracted message text
    """

    if value.get("final_answer") and value["final_answer"].strip():
        return value["final_answer"]
    return "No response generated for your query. Could you please rephrase your query?"
