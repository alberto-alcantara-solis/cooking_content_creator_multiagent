from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from graph.state import ContentState
from nodes.orchestrator import orchestrator_node
from nodes.trend_agent import trend_node
from nodes.recipe_node import recipe_node
from nodes.content_node import content_node
from nodes.image_agent import image_node
from nodes.publisher_node import publisher_node
from graph.human_approval import get_checkpointer


def human_review_node(state: ContentState) -> ContentState:
    """
    This node does nothing by itself.
    LangGraph will interrupt HERE and wait for external input.
    The graph resumes when you call graph.invoke() again
    with updated state containing human_review.status = "approved" (or "rejected"/"edit_requested")
    """
    return state


def route_after_review(state: ContentState) -> str:
    """Conditional edge after human review."""
    status = state["human_review"]["status"]
    if status == "approved":
        return "publisher"
    elif status == "rejected":
        return END
    elif status == "edit_requested":
        return "content_node"   # Re-generate content with feedback
    return END


def build_graph():
    graph = StateGraph(ContentState)

    # --- Add nodes ---
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("trend_agent", trend_node)
    graph.add_node("recipe_node", recipe_node)
    graph.add_node("content_node", content_node)
    graph.add_node("image_agent", image_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("publisher", publisher_node)

    # --- Entry point ---
    graph.set_entry_point("orchestrator")

    # --- Edges ---
    graph.add_edge("orchestrator", "trend_agent")
    graph.add_edge("trend_agent", "recipe_node")

    # Parallel execution: after recipe, run content_node AND image_agent simultaneously
    graph.add_edge("recipe_node", "content_node")
    graph.add_edge("recipe_node", "image_agent")

    # Merge both parallel branches at human_review
    graph.add_edge("content_node", "human_review")
    graph.add_edge("image_agent", "human_review")

    # Conditional edge after human reviews
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "publisher": "publisher",
            "content_node": "content_node",   # edit loop
            END: END
        }
    )

    graph.add_edge("publisher", END)

    # Checkpointer enables interrupt + persistence
    checkpointer = get_checkpointer()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]   # Human in the loop
    )