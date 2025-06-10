from app.agents.agent_state import (
    ChatAgent,
    followup_ambiguous_queries,
    generate_followup_question,
    grade_documents,
    handle_error,
    rephrase_query,
    route_based_on_graded_document,
    route_question,
    route_vector_generation,
    vector_generate,
    vector_retrieve,
    web_based_answer,
    image_based_answer
)
from langgraph.graph import END, START, StateGraph


def decide_ambiguity_next_node(state):
    if state.get("error_occurred"):
        return "handle_error"
    return "followup" if state.get("ambiguity_status") == "ambiguous" else "router"


def decide_router_next_node(state):
    if state.get("error_occurred"):
        return "handle_error"
    if state.get("datasource") == "web_search":
        return "websearch"
    
    if state.get("datasource") == "image_processing":
        return "image_processing"

    return "vectorstore"


def error_handler(state: ChatAgent):
    if state.get("error_occurred"):
        return "handle_error"


def define_agent_workflow() -> StateGraph:
    workflow = StateGraph(ChatAgent)

    # Define the nodes
    workflow.add_node("rephrase_query", rephrase_query)
    workflow.add_node("handle_error", handle_error)
    workflow.add_node("route_question", route_question)
    workflow.add_node("image_based_answer", image_based_answer)
    workflow.add_node("web_based_answer", web_based_answer)
    workflow.add_node("vector_retrieve", vector_retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("vector_generate", vector_generate)
    workflow.add_node("followup_ambiguous_queries", followup_ambiguous_queries)
    workflow.add_node("generate_followup_question", generate_followup_question)
    workflow.add_node("route_vector_generation", route_vector_generation)

    # Set the entry point
    workflow.set_entry_point("rephrase_query")
    workflow.add_edge(START, "rephrase_query")
    workflow.add_conditional_edges(
        "rephrase_query",
        decide_ambiguity_next_node,
        {
            "router": "route_question",
            "followup": "followup_ambiguous_queries",
            "handle_error": "handle_error",
        },
    )
    workflow.add_conditional_edges(
        "route_question",
        decide_router_next_node,
        {
            "vectorstore": "vector_retrieve",
            "websearch": "web_based_answer",
            "handle_error": "handle_error",
            "image_processing": "image_based_answer"
        },
    )
    workflow.add_edge("image_based_answer", END)
    workflow.add_edge("web_based_answer", END)
    workflow.add_edge("vector_retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        route_based_on_graded_document,
        {
            "generate": "vector_generate",
            "followup": "generate_followup_question",
            "handle_error": "handle_error",
        },
    )
    workflow.add_conditional_edges(
        "vector_generate",
        route_vector_generation,
        {
            "handle_error": "handle_error",
            "generate_followup": "generate_followup_question",
            "end": END,
        },
    )

    return workflow
