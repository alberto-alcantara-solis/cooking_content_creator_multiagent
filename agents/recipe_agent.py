"""Recipe agent that generates cooking recipes."""

from graph.state import ContentState

def recipe_node(state: ContentState) -> ContentState:
    """Generates a cooking recipe based on the selected trending topic."""
    print("👩‍🍳 Generating recipe...")
    return