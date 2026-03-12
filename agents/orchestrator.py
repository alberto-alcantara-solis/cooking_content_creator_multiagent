"""Orchestrator agent that manages the execution of multiple agents in a cooking content creation workflow."""

from graph.state import ContentState

def orchestrator_node(state: ContentState) -> ContentState:
    """The orchestrator node is the entry point of the graph. It initializes the state and can perform any setup tasks."""
    print("🎬 Orchestrator starting the content creation process...")
    return