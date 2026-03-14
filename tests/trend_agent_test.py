"""
Test the Trend Agent in a single uninode setup, without the full graph.

IMPORTANT:
The google API calls are limited to 20 per day:
    One full execution of the trend agent (without retries) uses 20 calls to the API,resulting in the consumption of the daily quota.
"""

from asyncio import run
import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.trend_agent import trend_node
from graph.state import ContentState

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

AVOID_TOPICS = []

def test_basic_trend_agent():
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

    AVOID_TOPICS.extend(updated_state["trending_topics"][:2])

    print("✅ 1/4 Trend Agent Test Passed. Basic run State:")
    print(updated_state)

def test_trend_agent_with_avoid_topics():
    """Test the trend agent's handling of avoid_topics."""
    
    print(f"Using the first two trending topics of previous test as avoid_topics for the second run: {AVOID_TOPICS}")

    state_with_avoid: ContentState = {
        "run_id":"trend_agent_test_run_002",
        "current_step": "orchestration_finished",
        "avoid_topics": AVOID_TOPICS,
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

    updated_state = trend_node(state_with_avoid)

    # Ensure that none of the avoid topics are in the trending topics or selected topic
    for avoid in state_with_avoid["avoid_topics"]:
        assert avoid not in updated_state["trending_topics"], f"Avoid topic '{avoid}' found in trending topics"
        assert avoid != updated_state["selected_topic"], f"Avoid topic '{avoid}' was selected"

    print("✅ 2/4 Trend Agent Test Passed. Avoid Topics State:")
    print(updated_state)

def test_trend_agent_with_topic_override():
    """Test the trend agent's handling of a topic override."""
    state_with_override: ContentState = {
        "run_id":"trend_agent_test_run_003",
        "current_step": "orchestration_finished",
        "topic_override": "muffins filled with white chocolate",
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

    updated_state = trend_node(state_with_override)

    # Ensure that the selected topic is the override value
    assert updated_state["selected_topic"] == state_with_override["topic_override"], "Selected topic does not match the topic override"

    print("✅ 3/4 Trend Agent Test Passed. Topic Override State:")
    print(updated_state)

def test_trend_agent_with_both_avoid_and_override():
    """Test the trend agent's handling of both avoid_topics and a topic override."""
    
    print(f"Using the first two trending topics of previous test as avoid_topics for the second run: {AVOID_TOPICS}")


    state_with_both: ContentState = {
        "run_id":"trend_agent_test_run_004",
        "current_step": "orchestration_finished",
        "avoid_topics": AVOID_TOPICS,
        "topic_override": "three chocolate cake",
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

    updated_state = trend_node(state_with_both)

    # Ensure that the selected topic is the override value and not in the avoid topics
    assert updated_state["selected_topic"] == state_with_both["topic_override"], "Selected topic does not match the topic override"
    for avoid in state_with_both["avoid_topics"]:
        assert avoid != updated_state["selected_topic"], f"Avoid topic '{avoid}' was selected"
    
    print("✅ 4/4 Trend Agent Test Passed. Both Avoid and Override State:")
    print(updated_state)

if __name__ == "__main__":
    test_basic_trend_agent()
    test_trend_agent_with_avoid_topics()
    test_trend_agent_with_topic_override()
    test_trend_agent_with_both_avoid_and_override()