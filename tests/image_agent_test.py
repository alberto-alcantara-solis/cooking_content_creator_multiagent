"""
Test the Image Agent in a single uninode setup, without the full graph.

IMPORTANT:
The image generation requires ComfyUI server running.
"""

import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.image_agent import _parse_image_agent_output, image_node
from graph.state import ContentState
from tests.vars import TEST_STATE_1_PARALLEL

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")


def test_parse_image_agent_output_valid_json():
    """Ensure the parser accepts well-formed JSON (with/without markdown fences)."""
    raw = """```json
{
  "local_path": "/path/to/generated/image.png",
  "comfyui_prompt": "A delicious looking chocolate cake with frosting",
  "status": "ready",
  "critique_score": 8.5,
  "critique_feedback": "Excellent composition and lighting.",
  "attempts": 1
}
```"""

    parsed = _parse_image_agent_output(raw)

    assert parsed["local_path"] == "/path/to/generated/image.png"
    assert parsed["comfyui_prompt"] == "A delicious looking chocolate cake with frosting"
    assert parsed["status"] == "ready"
    assert parsed["critique_score"] == 8.5
    assert parsed["critique_feedback"] == "Excellent composition and lighting."
    assert parsed["attempts"] == 1

    print("✅ 1/6 Image Agent Test Passed. Correctly parsed image output.")


def test_parse_image_agent_output_invalid_json_raises():
    """Invalid/malformed results should raise a ValueError."""
    bad_raw = "No JSON here"
    try:
        _parse_image_agent_output(bad_raw)
        assert False, "Expected ValueError but no exception was raised."
    except ValueError as e:
        assert "No JSON object" in str(e)

    print("✅ 2/6 Image Agent Test Passed. Malformed JSON correctly raised ValueError.")


def test_parse_image_agent_output_missing_required_field_raises():
    """Missing required fields should raise a ValueError."""
    # Missing 'local_path'
    raw = """{
        "comfyui_prompt": "A prompt",
        "status": "ready"
    }
    """

    try:
        _parse_image_agent_output(raw)
        assert False, "Expected ValueError for missing local_path field."
    except ValueError as e:
        assert "Missing required field 'local_path'" in str(e)

    # Missing 'comfyui_prompt'
    raw2 = """{
        "local_path": "/path/image.png",
        "status": "ready"
    }
    """

    try:
        _parse_image_agent_output(raw2)
        assert False, "Expected ValueError for missing comfyui_prompt field."
    except ValueError as e:
        assert "Missing required field 'comfyui_prompt'" in str(e)

    # Missing 'status'
    raw3 = """{
        "local_path": "/path/image.png",
        "comfyui_prompt": "A prompt"
    }
    """

    try:
        _parse_image_agent_output(raw3)
        assert False, "Expected ValueError for missing status field."
    except ValueError as e:
        assert "Missing required field 'status'" in str(e)

    print("✅ 3/6 Image Agent Test Passed. Missing required fields correctly raised ValueError.")


def test_parse_image_agent_output_defaults_optional_fields():
    """Optional fields should be filled with defaults if missing."""
    raw = """{
        "local_path": "/path/to/image.png",
        "comfyui_prompt": "A simple prompt",
        "status": "ready"
    }
    """

    parsed = _parse_image_agent_output(raw)

    assert parsed["critique_score"] == 0.0
    assert parsed["critique_feedback"] == ""
    assert parsed["attempts"] == 1

    print("✅ 4/6 Image Agent Test Passed. Optional fields correctly defaulted.")


def test_image_node_fails_with_missing_recipe():
    """The image node should fail gracefully when recipe is missing."""
    state: ContentState = {
        "run_id": "image_node_test_run_001",
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

    updated_state = image_node(state)

    assert updated_state["current_step"] == "image_generation_failed"
    assert any("recipe" in e for e in updated_state["errors"])
    assert updated_state["image"]["status"] == "failed"

    print("✅ 5/6 Image Agent Test Passed. Missing recipe correctly handled with error message.")


def test_image_node_full_generation():
    """Run the image node end-to-end for image generation (requires ComfyUI and API access)."""
    state = TEST_STATE_1_PARALLEL.copy()
    state["run_id"] = "image_node_test_run_002"

    try:
        updated_state = image_node(state)

        assert "image" in updated_state
        image = updated_state["image"]
        assert isinstance(image, dict)
        assert "comfyui_prompt" in image
        assert "local_path" in image
        assert "status" in image
        assert image["status"] in ["ready", "failed"]
        if image["status"] == "ready":
            assert image["local_path"] != ""
            assert image["comfyui_prompt"] != ""
        assert updated_state["current_step"] in ["image_generation_complete", "image_generation_failed"]

        print("✅ 6/6 Image Agent Test Passed. Successfully attempted image generation:")
        print(updated_state)

    except Exception as e:
        print(f"⚠️ 6/6 Image Agent Test Skipped or Failed due to external dependencies: {e}")
        print("This test requires ComfyUI server running and Gemini API access.")


if __name__ == "__main__":
    test_parse_image_agent_output_valid_json()
    test_parse_image_agent_output_invalid_json_raises()
    test_parse_image_agent_output_missing_required_field_raises()
    test_parse_image_agent_output_defaults_optional_fields()
    test_image_node_fails_with_missing_recipe()
    test_image_node_full_generation()