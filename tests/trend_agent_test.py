"""Test the Trend Agent in a single uninode setup, without the full graph."""

from asyncio import run
import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.trend_agent import trend_node
from graph.state import ContentState

logging.basicConfig(level=logging.INFO)

def test_trend_agent():
    """Test the trend agent node in isolation."""
    state_after_orchestration: ContentState = {
        "run_id":"trend_agent_test_run_001",
        "current_step": "orchestration_finished",
        "trending_topics": [],
        "selected_topic": "",
        "recipe": None,
        "instagram_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "published": False,
        "errors": []
    }

    # Call the trend_node directly with the initial state
    updated_state = trend_node(state_after_orchestration)

    # Check that we got trending topics and a selected topic
    assert "trending_topics" in updated_state, "Missing 'trending_topics' in state"
    assert "selected_topic" in updated_state, "Missing 'selected_topic' in state"
    assert isinstance(updated_state["trending_topics"], list), "'trending_topics' should be a list"
    assert isinstance(updated_state["selected_topic"], str), "'selected_topic' should be a string"

    print("Trend Agent Test Passed. Updated State:")
    print(updated_state)

if __name__ == "__main__":
    test_trend_agent()