"""
nodes/recipe_node.py
──────────────────────
The Recipe Generation Node - second node in the content pipeline.

Role in the graph (from builder.py):
    trend_agent → [RECIPE NODE] → content_node
                                 → image_agent   (parallel)

Responsibility:
    1. Receive `selected_topic` (and context from `trending_topics`) from state.
    2. Generate a single, creative, well-structured recipe for that topic.
    3. Write a validated `RecipeData` dict back into ContentState["recipe"].

Architecture: Direct LLM chain (no ReAct loop)
    Unlike the trend agent, recipe generation requires no external tools —
    the LLM has deep culinary knowledge. A single structured prompt is just as reliable here.
"""

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import ContentState, RecipeData
from prompts.recipe import (
    RECIPE_NODE_SYSTEM_PROMPT,
    RECIPE_NODE_RETRY_PROMPT,
    build_recipe_human_message,
)


# ── Logger ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("recipe_node")


# ─────────────────────────────────────────────────────────────────────────────
#  LLM setup
# ─────────────────────────────────────────────────────────────────────────────
def _build_recipe_llm() -> ChatGoogleGenerativeAI:
    """
    Instantiate the LLM used for recipe generation.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.65,  # More creative than trend agent, but still focused for structured output
        max_tokens=2048,   # A full recipe with steps fits comfortably; no need for 4096
    )


# Build once at import time
_llm = _build_recipe_llm()

_SYSTEM_MESSAGE = SystemMessage(content=RECIPE_NODE_SYSTEM_PROMPT)


# ─────────────────────────────────────────────────────────────────────────────
#  Output Parser
#  Validates JSON against the RecipeData TypedDict schema.
# ─────────────────────────────────────────────────────────────────────────────
_VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}

def _parse_recipe_output(raw_text: str) -> RecipeData:
    """
    Extract and validate the JSON payload from the LLM's response.

    Args:
        raw_text: The full text returned by the LLM.

    Returns:
        A validated RecipeData-compatible dict ready to be stored in state.

    Raises:
        ValueError: If JSON is missing, malformed, or fails schema checks.
    """
    #Strip markdown fences and surrounding whitespace
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        cleaned = "\n".join(lines).strip()

    #Locate JSON boundaries (handles any preamble text the LLM sneaks in)
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response.")

    data = json.loads(cleaned[start:end])

    #Required string fields
    for field in ("title", "description", "prep_time"):
        if field not in data or not isinstance(data[field], str) or not data[field].strip():
            raise ValueError(f"Missing or empty string field: '{field}'.")

    #Ingredients list
    if "ingredients" not in data or not isinstance(data["ingredients"], list):
        raise ValueError("'ingredients' must be a non-empty list.")
    if len(data["ingredients"]) < 2:
        raise ValueError(
            f"'ingredients' must have at least 2 items, got {len(data['ingredients'])}."
        )
    if not all(isinstance(i, str) and i.strip() for i in data["ingredients"]):
        raise ValueError("All items in 'ingredients' must be non-empty strings.")

    #Steps list
    if "steps" not in data or not isinstance(data["steps"], list):
        raise ValueError("'steps' must be a non-empty list.")
    if len(data["steps"]) < 2:
        raise ValueError(
            f"'steps' must have at least 2 items, got {len(data['steps'])}."
        )
    if not all(isinstance(s, str) and s.strip() for s in data["steps"]):
        raise ValueError("All items in 'steps' must be non-empty strings.")

    #Difficulty enum
    if "difficulty" not in data or data["difficulty"] not in _VALID_DIFFICULTIES:
        logger.warning(
            "Invalid difficulty '%s' — defaulting to 'Medium'.", data.get("difficulty")
        )
        data["difficulty"] = "Medium"

    # Return only the keys defined in RecipeData to keep state clean
    return RecipeData(
        title=data["title"].strip(),
        description=data["description"].strip(),
        ingredients=[i.strip() for i in data["ingredients"]],
        steps=[s.strip() for s in data["steps"]],
        prep_time=data["prep_time"].strip(),
        difficulty=data["difficulty"],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Core LLM invocation with retry
# ─────────────────────────────────────────────────────────────────────────────
def _invoke_recipe_node(selected_topic: str, trending_topics: list[str], max_retries: int = 2) -> RecipeData:
    """
    Call the LLM to generate a recipe and return a validated RecipeData dict.

    Args:
        selected_topic:  The topic chosen by the trend agent.
        trending_topics: Full candidate list (gives the LLM context about the
                         broader trend landscape so it can tailor the recipe angle).
        max_retries:     How many times to retry on bad/malformed JSON output.

    Returns:
        Validated RecipeData dict.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    messages = [
        _SYSTEM_MESSAGE,
        HumanMessage(content=build_recipe_human_message(selected_topic, trending_topics)),
    ]

    last_error = None
    raw_response = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.warning(
                "Recipe node retry %d/%d due to: %s", attempt, max_retries, last_error
            )
            
            messages.append(
                HumanMessage(
                    content=RECIPE_NODE_RETRY_PROMPT.format(
                        error_message=str(last_error),
                        bad_response=raw_response,
                    )
                )
            )

        result = _llm.invoke(messages)

        # Gemini may return content as a string or as a list of content blocks
        raw_response = (
            result.content
            if isinstance(result.content, str)
            else result.content[0].get("text", "")
        )
        logger.debug("Recipe node raw response (attempt %d):\n%s", attempt + 1, raw_response)

        try:
            parsed = _parse_recipe_output(raw_response)
            logger.info(
                "Recipe node succeeded on attempt %d. Recipe: '%s' (%s, %s)",
                attempt + 1,
                parsed["title"],
                parsed["difficulty"],
                parsed["prep_time"],
            )
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            # Loop continues to retry

    raise RuntimeError(
        f"Recipe node failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────
def recipe_node(state: ContentState) -> dict:
    """
    LangGraph node: generate a recipe from the selected trend topic.

    Args:
        state: The current ContentState.
            Reads from state:
                - selected_topic   : str        (set by trend_agent)
                - trending_topics  : list[str]  (context for the LLM)

    Returns:
        - recipe           : RecipeData  — the generated recipe
        - current_step     : str         — pipeline breadcrumb

    On failure, appends an error message to state["errors"] and updates
    current_step to signal failure without crashing the graph.
    """
    run_id = state.get("run_id", "unknown")
    logger.info("=== Recipe node START (run_id=%s) ===", run_id)
    logger.debug("State before recipe_node: %s", json.dumps(state, indent=2, default=str))

    selected_topic  = state.get("selected_topic", "")
    trending_topics = state.get("trending_topics", [])

    if not selected_topic:
        error_msg = "recipe_node: 'selected_topic' is empty — trend_agent may have failed."
        logger.error(error_msg)
        existing_errors = state.get("errors", [])
        existing_errors.append(error_msg)
        result = {
            "errors":       existing_errors,
            "current_step": "recipe_generation_failed",
        }
        logger.debug("Recipe node early error result: %s", json.dumps(result, indent=2, default=str))
        return result

    try:
        recipe = _invoke_recipe_node(
            selected_topic=selected_topic,
            trending_topics=trending_topics,
        )

        logger.info(
            "Recipe Node DONE. Title: '%s' | Difficulty: %s | Prep: %s",
            recipe["title"],
            recipe["difficulty"],
            recipe["prep_time"],
        )

        result = {
            "recipe":       recipe,
            "current_step": "recipe_generation_complete",
        }
        logger.debug("Recipe node result: %s", json.dumps(result, indent=2, default=str))
        return result

    except Exception as e:
        logger.exception("Recipe Node FAILED: %s", e)

        existing_errors = state.get("errors") or []
        result = {
            "errors":       existing_errors + [f"recipe_node: {str(e)}"],
            "current_step": "recipe_generation_failed",
        }
        logger.debug("Recipe node error result: %s", json.dumps(result, indent=2, default=str))
        return result