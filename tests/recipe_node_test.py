"""
Test the Recipe Node in a single uninode setup, without the full graph.
"""

import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.recipe_node import _parse_recipe_output, recipe_node
from graph.state import ContentState

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")


def test_parse_recipe_output_valid_json():
    """Ensure the parser accepts well-formed JSON (with/without markdown fences)."""
    raw = """```json
{
  "title": "Test Recipe",
  "description": "A short description.",
  "ingredients": ["1 cup flour", "2 eggs"],
  "steps": ["Mix.", "Bake."],
  "prep_time": "15 minutes",
  "difficulty": "Easy"
}
```"""

    parsed = _parse_recipe_output(raw)

    assert parsed["title"] == "Test Recipe"
    assert parsed["difficulty"] == "Easy"
    assert isinstance(parsed["ingredients"], list) and len(parsed["ingredients"]) == 2
    assert isinstance(parsed["steps"], list) and len(parsed["steps"]) == 2
    
    print("✅ 1/5 Recipe Node Test Passed. Correctly parsed recipe.")


def test_parse_recipe_output_invalid_json_raises():
    """Invalid/malformed results should raise a ValueError."""
    bad_raw = "No JSON here"
    try:
        _parse_recipe_output(bad_raw)
        assert False, "Expected ValueError but no exception was raised."
    except ValueError as e:
        assert "No JSON object" in str(e)

    print("✅ 2/5 Recipe Node Test Passed. Malformed JSON correctly raised ValueError.")


def test_parse_recipe_output_missing_required_field_raises():
    """Missing required fields should raise a ValueError."""
    # Missing 'title'
    raw = """{
        "description": "A short description.",
        "ingredients": ["1 cup flour", "2 eggs"],
        "steps": ["Mix.", "Bake."],
        "prep_time": "15 minutes",
        "difficulty": "Easy"
    }
    """

    try:
        _parse_recipe_output(raw)
        assert False, "Expected ValueError for missing title field."
    except ValueError as e:
        assert "Missing or empty string field" in str(e)
    
    print("✅ 3/5 Recipe Node Test Passed. Missing required field correctly raised ValueError.")


def test_recipe_node_fails_with_empty_selected_topic():
    """The recipe node should fail gracefully when selected_topic is empty."""
    state: ContentState = {
        "run_id": "recipe_node_test_run_001",
        "current_step": "orchestration_finished",
        "trending_topics": [],
        "selected_topic": "",
        "recipe": None,
        "instagram_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "published": False,
        "errors": [],
    }

    updated_state = recipe_node(state)

    assert updated_state["current_step"] == "recipe_generation_failed"
    assert any("selected_topic" in e for e in updated_state["errors"])

    print("✅ 4/5 Recipe Node Test Passed. Empty selected_topic correctly handled with error message.")


def test_recipe_node_generates_recipe():
    """Run the recipe node end-to-end"""
    state: ContentState = {
        "run_id": "recipe_node_test_run_002",
        "current_step": "trend_research_complete",
        "trending_topics": ["Charli's Zero-Sugar Cheesecake", "Spring Pea Crostini", "Rhubarb Desserts", "Miso Butter Cabbage", "Nostalgic Sparkling Water", "Spring Pea Crostini with Ricotta"],
        "selected_topic": "Spring Pea Crostini with Ricotta",
        "recipe": None,
        "instagram_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "published": False,
        "errors": [],
    }

    updated_state = recipe_node(state)

    assert "recipe" in updated_state
    recipe = updated_state["recipe"]
    assert isinstance(recipe, dict)
    assert recipe["title"] != "Spring Pea Crostini with Ricotta"
    assert updated_state["current_step"] == "recipe_generation_complete"

    print("✅ 5/5 Recipe Node Test Passed. Successfully generated recipe from selected topic:")
    print(updated_state)


if __name__ == "__main__":
    test_parse_recipe_output_valid_json()
    test_parse_recipe_output_invalid_json_raises()
    test_parse_recipe_output_missing_required_field_raises()
    test_recipe_node_fails_with_empty_selected_topic()
    test_recipe_node_generates_recipe()
