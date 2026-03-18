"""
Test the Content Node in a single uninode setup, without the full graph.
"""

import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.content_node import _parse_content_output, content_node
from graph.state import ContentState
from tests.vars import TEST_STATE_1_PARALLEL

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")


def test_parse_content_output_valid_json():
    """Ensure the parser accepts well-formed JSON (with/without markdown fences)."""
    raw = """```json
{
  "caption": "This is a test caption for Instagram. It's delicious and easy to make!",
  "hashtags": ["#foodie", "#recipe", "#cooking", "#yum", "#easyrecipe"],
  "character_count": 72
}
```"""

    parsed = _parse_content_output(raw)

    assert parsed["caption"] == "This is a test caption for Instagram. It's delicious and easy to make!"
    assert len(parsed["hashtags"]) == 5
    assert parsed["character_count"] == len(parsed["caption"])
    assert all(h.startswith("#") for h in parsed["hashtags"])
    
    print("✅ 1/6 Content Node Test Passed. Correctly parsed content.")


def test_parse_content_output_invalid_json_raises():
    """Invalid/malformed results should raise a ValueError."""
    bad_raw = "No JSON here"
    try:
        _parse_content_output(bad_raw)
        assert False, "Expected ValueError but no exception was raised."
    except ValueError as e:
        assert "No JSON object" in str(e)

    print("✅ 2/6 Content Node Test Passed. Malformed JSON correctly raised ValueError.")


def test_parse_content_output_missing_required_field_raises():
    """Missing or invalid required fields should raise a ValueError."""
    # Missing 'caption'
    raw = """{
        "hashtags": ["#foodie", "#recipe"],
        "character_count": 0
    }
    """

    try:
        _parse_content_output(raw)
        assert False, "Expected ValueError for missing caption field."
    except ValueError as e:
        assert "Missing or empty 'caption' field" in str(e)

    # Invalid hashtags (not a list)
    raw2 = """{
        "caption": "Test caption",
        "hashtags": "#foodie #recipe",
        "character_count": 12
    }
    """

    try:
        _parse_content_output(raw2)
        assert False, "Expected ValueError for invalid hashtags."
    except ValueError as e:
        assert "'hashtags' must be a list" in str(e)

    # Hashtags with spaces or not starting with #
    raw3 = """{
        "caption": "Test caption",
        "hashtags": ["foodie", "#recipe with space", "#validhashtag", "#anotherValid", "#oneMoreValid"],
        "character_count": 12
    }
    """

    try:
        _parse_content_output(raw3)
        assert False, "Expected ValueError for malformed hashtags."
    except ValueError as e:
        assert "All hashtags must be strings starting with '#' and containing no spaces" in str(e)

    print("✅ 3/6 Content Node Test Passed. Missing or invalid fields correctly raised ValueError.")


def test_content_node_fails_with_missing_recipe():
    """The content node should fail gracefully when recipe is missing."""
    state: ContentState = {
        "run_id": "content_node_test_run_001",
        "current_step": "recipe_generation_complete",
        "trending_topics": ["Topic1", "Topic2"],
        "selected_topic": "Topic1",
        "recipe": None,
        "instagram_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "published": False,
        "errors": [],
    }

    updated_state = content_node(state)

    assert updated_state["current_step"] == "content_generation_failed"
    assert any("recipe" in e for e in updated_state["errors"])

    print("✅ 4/6 Content Node Test Passed. Missing recipe correctly handled with error message.")


def test_content_node_first_pass_generation():
    """Run the content node end-to-end for first-pass generation."""
    state = TEST_STATE_1_PARALLEL.copy()

    state["run_id"] = "content_node_test_run_002"

    updated_state = content_node(state)

    assert "instagram_content" in updated_state
    content = updated_state["instagram_content"]
    assert isinstance(content, dict)
    assert "caption" in content
    assert "hashtags" in content
    assert "character_count" in content
    assert isinstance(content["hashtags"], list)
    assert len(content["hashtags"]) >= 5
    assert updated_state["current_step"] == "content_generation_complete"
    assert updated_state["human_review"]["status"] == "pending"
    assert updated_state["human_review"]["feedback"] is None

    print("✅ 5/6 Content Node Test Passed. Successfully generated content from recipe:")
    print(updated_state)


def test_content_node_edit_loop():
    """Run the content node end-to-end for edit loop."""
    # Start with the parallel state, add instagram_content and set human_review to edit_requested
    state = TEST_STATE_1_PARALLEL.copy()
    state["instagram_content"] = {
        "caption": "Original caption that needs editing.",
        "hashtags": ["#original", "#needs", "#editing"],
        "character_count": 35
    }
    state["human_review"] = {
        "status": "edit_requested",
        "feedback": "Make it more exciting and add more hashtags."
    }

    updated_state = content_node(state)

    assert "instagram_content" in updated_state
    content = updated_state["instagram_content"]
    assert isinstance(content, dict)
    assert "caption" in content
    assert "hashtags" in content
    assert "character_count" in content
    assert isinstance(content["hashtags"], list)
    assert 5 <= len(content["hashtags"]) <= 8
    assert updated_state["current_step"] == "content_edit_complete"
    assert updated_state["human_review"]["status"] == "pending"
    assert updated_state["human_review"]["feedback"] is None

    print("✅ 6/6 Content Node Test Passed. Successfully edited content based on feedback:")
    print(updated_state)


if __name__ == "__main__":
    test_parse_content_output_valid_json()
    test_parse_content_output_invalid_json_raises()
    test_parse_content_output_missing_required_field_raises()
    test_content_node_fails_with_missing_recipe()
    test_content_node_first_pass_generation()
    test_content_node_edit_loop()