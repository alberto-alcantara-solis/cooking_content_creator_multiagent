"""Publisher agent that publishes the generated content."""

from graph.state import ContentState

def publisher_node(state: ContentState) -> ContentState:
    """Publishes the content to the different platforms."""
    print("📢 Publishing content...")
    return