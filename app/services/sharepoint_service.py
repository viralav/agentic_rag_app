from __future__ import annotations
import json
import asyncio
import traceback
import os
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)
from langchain_core.runnables import (
    ConfigurableFieldSpec,
    Runnable,
    RunnablePassthrough,
)
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain.chains.llm import LLMChain
from langchain_core.runnables import RunnableParallel, RunnableLambda
from langchain.schema import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import numpy as np
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient as AsyncSearchClient
from azure.search.documents.models import VectorizedQuery
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from azure.search.documents.indexes import SearchIndexClient
from app.config.set_logger import set_logger

logger = set_logger(name=__name__)


if TYPE_CHECKING:
    from azure.search.documents.aio import SearchClient as AsyncSearchClient


from app.config.constants import (
    OPEN_AI_BASE_URL,
    OPEN_AI_DEPLOYMENT_NAME,
    OPEN_AI_KEY,
    OPEN_AI_VERSION,
    OPEN_AI_TEMPERATURE,
    OPEN_AI_MAX_TOKENS,
    OPEN_AI_EMBEDDING_DEPLOYED_MODEL,
    OPEN_AI_SHAREPOINT_PROMPT_EN,
    SELECT_DOCUMENT_COUNT,
    FIELDS_CONTENT,
    FIELDS_CONTENT_VECTOR,
    FIELDS_HEADER,
    FIELDS_METADATA,
    FIELDS_URL,
    FIELDS_METADATA_UPLOAD,
    FIELDS_METADATA_UPLOAD_SOURCE,
    AZURE_SEARCH_SERVICE_ENDPOINT,
    AZURE_SEARCH_ADMIN_KEY,
    AZURE_OPENAI_GPT4o_MODEL,
    UPLOAD_INDEX
)


class GPTModel:
    def __init__(
        self,
        azure_endpoint,
        azure_deployment,
        openai_api_version,
        openai_api_key,
        temperature,
        max_tokens,
    ):
        self.azure_endpoint = azure_endpoint
        self.azure_deployment = azure_deployment
        self.openai_api_version = openai_api_version
        self.openai_api_key = openai_api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    def create_llm_instance(self):
        """
        Creates and returns an AzureChatOpenAI instance using the model's attributes.
        """
        return AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            azure_deployment=self.azure_deployment,
            openai_api_version=self.openai_api_version,
            openai_api_key=self.openai_api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            # streaming=True,
            # callbacks=[StreamingStdOutCallbackHandler()],
        )


class GPT4oModel(GPTModel):
    """
    Specific configuration for GPT-4 model.
    """

    def __init__(self, location="ch"):
        self.swiss_dict = dict(
            azure_endpoint=os.getenv(OPEN_AI_BASE_URL),
            azure_deployment=os.getenv(OPEN_AI_DEPLOYMENT_NAME),  # Update deployment for GPT-4
            openai_api_version=os.getenv(OPEN_AI_VERSION),
            openai_api_key=os.getenv(OPEN_AI_KEY),
            temperature=OPEN_AI_TEMPERATURE,
            max_tokens=OPEN_AI_MAX_TOKENS,
        )
        self.sweden_dict = dict(
            azure_endpoint=os.getenv(OPEN_AI_BASE_URL),
            azure_deployment=os.getenv(OPEN_AI_DEPLOYMENT_NAME),  # Update deployment for GPT-4
            openai_api_version=os.getenv(OPEN_AI_VERSION),
            openai_api_key=os.getenv(OPEN_AI_KEY),
            temperature=OPEN_AI_TEMPERATURE,
            max_tokens=OPEN_AI_MAX_TOKENS,
        )

        match location:
            case "ch":
                super().__init__(**self.swiss_dict)
            case "se":
                super().__init__(**self.sweden_dict)
            case _:
                super().__init__(**self.swiss_dict)


def set_gpt_model(model_identifier):
    """
    Takes a model identifier ("gpt4" or "gpt4o" or "gpt-4o-mini") and returns the corresponding GPTModel instance.
    """
    # if model_identifier == AZURE_OPENAI_GPT4_MODEL:
    #     return GPT4Model()
    if model_identifier == AZURE_OPENAI_GPT4o_MODEL:
        return GPT4oModel()
    # elif model_identifier == AZURE_OPENAI_GPT4o_mini_MODEL:
    #     return GPT4oMiniModel()
    else:
        raise ValueError("Invalid GPT model identifier")

def set_embeddings_model() -> AzureOpenAIEmbeddings:
    return AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv(OPEN_AI_BASE_URL),
        openai_api_key=os.getenv(OPEN_AI_KEY),
        azure_deployment=OPEN_AI_EMBEDDING_DEPLOYED_MODEL,
        openai_api_version=os.getenv(OPEN_AI_VERSION),
    )


embeddings: AzureOpenAIEmbeddings = set_embeddings_model()

llm_gpt4o = set_gpt_model(AZURE_OPENAI_GPT4o_MODEL).create_llm_instance()



def get_indexes(search_endpoint, search_key):
    index_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=AzureKeyCredential(search_key),
    )
    indexes_list = index_client.list_index_names()
    return list(indexes_list)


def _get_search_client(
    endpoint: str,
    key: str,
    index_name: str,
    semantic_configuration_name: str,
    async_: str,
) -> AsyncSearchClient:

    credential = AzureKeyCredential(key)

    # Create the search client
    if async_:
        return AsyncSearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
            semantic_configuration_name=semantic_configuration_name,
        )


class CustomAzureSearch:
    """`Azure Cognitive Search` vector store."""

    def __init__(
        self,
        azure_search_endpoint: str,
        azure_search_key: str,
        content_index_name: str,
        embedding_function: Union[Callable, Embeddings],
        **kwargs: Any,
    ):
        """Initialize with necessary components."""
        # Initialize base class
        self.embedding_function = embedding_function

        if isinstance(self.embedding_function, Embeddings):
            self.embed_query = self.embedding_function.aembed_query
        else:
            self.embed_query = self.embedding_function

        self.azure_search_endpoint = azure_search_endpoint
        self.azure_search_key = azure_search_key

        self.content_index_name = content_index_name

        self.content_search_client = self.set_content_search_client()

    @property
    def embeddings(self) -> Optional[Embeddings]:
        # TODO: Support embedding object directly
        return (
            self.embedding_function
            if isinstance(self.embedding_function, Embeddings)
            else None
        )

    async def list_all_indexes(self) -> List[str]:

        async with self._search_index_client as async_client:
            results = await async_client.list_indexes()

        return results

    async def _aembed_query(self, text: str) -> List[float]:
        if self.embeddings:
            return await self.embeddings.aembed_query(text)
        else:
            return cast(Callable, self.embedding_function)(text)

    def set_content_search_client(self):
        return _get_search_client(
            endpoint=self.azure_search_endpoint,
            key=self.azure_search_key,
            index_name=self.content_index_name,
            semantic_configuration_name=self.content_index_name,
            async_=True,
        )

    async def content_semantic_hybrid_search_with_score_and_rerank(
        self, query="*", k: int = 4
    ) -> Tuple[Document, float, float]:
        """Return docs most similar to query with an hybrid query.

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.

        Returns:
            List of Documents most similar to the query and score for each
        """
        logger.debug(
            "### Incoming details for search: index: %s", self.content_index_name
        )
        vector = await self._aembed_query(query)
        async with self.set_content_search_client() as async_client:
            results = await async_client.search(
                search_text=query,
                vector_queries=[
                    VectorizedQuery(
                        vector=np.array(vector, dtype=np.float32).tolist(),
                        k_nearest_neighbors=k,
                        fields=FIELDS_CONTENT_VECTOR,
                    )
                ],
                scoring_profile=f"{self.content_index_name}-score",
                query_type="semantic",
                semantic_configuration_name=self.content_index_name,
                query_caption="extractive",
                query_answer="extractive",
                top=k,
            )
            semantic_answers = (await results.get_answers()) or []
            semantic_answers_dict: Dict = {}
            for semantic_answer in semantic_answers:
                semantic_answers_dict[semantic_answer.key] = {
                    "text": semantic_answer.text,
                    "highlights": semantic_answer.highlights,
                }

            # Convert results to Document objects
            docs = [
                Document(
                    page_content=f"Content header info: {result.get(FIELDS_HEADER, 'content')}: {result[FIELDS_CONTENT]}",
                    metadata={
                        "source": (
                            result.get(FIELDS_METADATA)
                            if result.get(FIELDS_METADATA)
                            else json.loads(
                                result.get(FIELDS_METADATA_UPLOAD, "\{\}")
                            ).get(FIELDS_METADATA_UPLOAD_SOURCE)
                        ),
                        "url": result.get(FIELDS_URL, ""),
                        "score": float(result["@search.reranker_score"]),
                    },
                )
                async for result in results
            ]
            return docs

    def add_texts():
        "Abstract methods filled with nothing"
        return

    @classmethod
    def from_texts():
        "Abstract methods filled with nothing"
        return
    


def set_vector_store(index_name: str, location: str = "ch") -> CustomAzureSearch:
    vector_store: CustomAzureSearch = CustomAzureSearch(
        azure_search_endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
        azure_search_key=AZURE_SEARCH_ADMIN_KEY,
        content_index_name=index_name,
        embedding_function=embeddings.embed_query
    )
    return vector_store


def set_document_retrievel_count(upload_index: bool) -> int | None:
    """Selects document count based on index type"""
    if upload_index:
        document_to_retrieve = SELECT_DOCUMENT_COUNT

    return document_to_retrieve

async def semantic_logic_multi_index_retrieval(
    query: str,
    data_sources: list,
    upload_index: bool
):
    """Main retrieval function -- get semantic answers from Azure AI search based on rephrased query"""
    total_retrieved_documents = []

    available_indices = get_indexes(
        search_endpoint=AZURE_SEARCH_SERVICE_ENDPOINT, search_key=AZURE_SEARCH_ADMIN_KEY
    )

    logger.debug(f"Indexes available at Vector Store: {available_indices}")

    indices = list(filter(lambda x: x in available_indices, data_sources))

    logger.debug(f"Indexes used to fetch data: {indices}")
    documents_count = set_document_retrievel_count(upload_index)

    tasks = [
        set_vector_store(
            index,
        ).content_semantic_hybrid_search_with_score_and_rerank(
            query=query, k=int(documents_count)
        )
        for index in indices
    ]

    try:
        results = await asyncio.gather(*tasks)
    except Exception:
        logger.error(
            f"Error in multi-index retrieval task execution: {traceback.format_exc()}"
        )
        raise Exception("Invalid index data requested by the user.")

    total_retrieved_documents.extend(results)

    flattened_doc_list = list(chain(*total_retrieved_documents))
    scores = [
        {doc.metadata.get("source"): doc.metadata.get("score")}
        for doc in flattened_doc_list
    ]
    logger.info("### Scoring profiles of all documents: %s", scores)

    sorted_documents = sorted(
        flattened_doc_list, key=lambda x: x.metadata.get("score"), reverse=True
    )

    seen_contents = set()
    unique_documents = []
    for doc in sorted_documents:
        content_hash = hash(doc.page_content.strip())
        if content_hash not in seen_contents:
            seen_contents.add(content_hash)
            unique_documents.append(doc)

    top_n_documents = unique_documents[:documents_count]
    logger.info(
        "### after deduplication and score filter, total documents %s",
        len(top_n_documents),
    )
    return top_n_documents

async def retrieve_documents(user_query):
    documents = await semantic_logic_multi_index_retrieval(
        query=user_query,
        data_sources=[UPLOAD_INDEX,],
        upload_index=True
    )
    return documents