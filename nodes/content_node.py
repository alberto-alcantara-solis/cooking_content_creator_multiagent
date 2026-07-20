"""
nodes/content_node.py
─────────────────────
The Content Generation Node — third node in the content pipeline (parallel branch with image_agent).

Role in the graph (from builder.py):
                         ┌─  [CONTENT NODE] ─┐
    recipe_node ─────────┤                   ├──► human_review
                         └─   image_agent   ─┘

    On edit loop (human_review → edit_requested):
    human_review ──► [CONTENT NODE] ──► human_review

Responsibility:
    1. Receive `recipe` (RecipeData), `selected_topic`, and `trending_topics` from state.
    2. Detect whether this is a first-pass generation or an edit-loop re-entry
       by inspecting state["human_review"]["status"] and ["feedback"].
    3. Generate a platform-ready Instagram caption + hashtag set via a direct LLM call.
    4. Write a validated `PlatformContent` dict back into ContentState["instagram_content"].

Architecture: Direct LLM chain (no ReAct loop)
    Caption writing is purely generative — no external tools are needed.
    This node is built around a single structured prompt with retry logic mirroring the design of recipe_node.py.

Edit loop awareness:
    builder.py routes human_review → content_node when status == "edit_requested".
    This node handles that case by switching to CONTENT_NODE_EDIT_PROMPT, which
    passes the reviewer's feedback alongside the previous caption so the LLM
    makes targeted revisions instead of starting from scratch.
"""

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import ContentState, PlatformContent
from prompts.content import (
    CONTENT_NODE_SYSTEM_PROMPT,
    CONTENT_NODE_RETRY_PROMPT,
    build_content_human_message,
    build_content_edit_message,
)


# ── Logger ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("content_node")


# ─────────────────────────────────────────────────────────────────────────────
#  LLM setup
# ─────────────────────────────────────────────────────────────────────────────
def _build_content_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.75,   # More creative than recipe_node; captions need voice and personality
        max_tokens=4096,    # Caption + hashtags fit comfortably within this budget
    )


# Build once at import time
_llm = _build_content_llm()

_SYSTEM_MESSAGE = SystemMessage(content=CONTENT_NODE_SYSTEM_PROMPT)

# Instagram hard limits (used in validation)
_IG_CAPTION_MAX_CHARS = 2000
_HASHTAG_MIN = 5


# ─────────────────────────────────────────────────────────────────────────────
#  Output Parser
#  Validates JSON against the PlatformContent TypedDict schema.
# ─────────────────────────────────────────────────────────────────────────────
def _parse_content_output(raw_text: str) -> PlatformContent:
    """
    Extract and validate the JSON payload from the LLM's response.

    Args:
        raw_text: Full text returned by the LLM.

    Returns:
        A validated PlatformContent-compatible dict ready to be stored in state.

    Raises:
        ValueError: If JSON is missing, malformed, or fails schema checks.
    """
    # Strip markdown fences and surrounding whitespace
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Locate JSON boundaries (handles any LLM preamble)
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response.")

    data = json.loads(cleaned[start:end])

    # Caption
    if "caption" not in data or not isinstance(data["caption"], str) or not data["caption"].strip():
        raise ValueError("Missing or empty 'caption' field.")

    caption = data["caption"].strip()

    if len(caption) > _IG_CAPTION_MAX_CHARS:
        raise ValueError(
            f"Caption exceeds Instagram's {_IG_CAPTION_MAX_CHARS}-character limit "
            f"(got {len(caption)})."
        )

    # Hashtags
    if "hashtags" not in data or not isinstance(data["hashtags"], list):
        raise ValueError("'hashtags' must be a list.")

    hashtags = data["hashtags"]

    if not (len(hashtags) >= _HASHTAG_MIN):
        raise ValueError(
            f"'hashtags' must contain at least {_HASHTAG_MIN} items, "
            f"got {len(hashtags)}."
        )

    if not all(isinstance(h, str) and h.startswith("#") and " " not in h for h in hashtags):
        raise ValueError(
            "All hashtags must be strings starting with '#' and containing no spaces."
        )

    # Character_count
    actual_count = len(caption)
    if "character_count" in data and isinstance(data["character_count"], int):
        if data["character_count"] != actual_count:
            logger.warning(
                "LLM reported character_count=%d but actual len(caption)=%d — correcting.",
                data["character_count"],
                actual_count,
            )

    return PlatformContent(
        caption=caption,
        hashtags=hashtags,
        character_count=actual_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Core LLM invocation with retry
# ─────────────────────────────────────────────────────────────────────────────
def _invoke_content_node(human_turn_message: str, max_retries: int = 3) -> PlatformContent:
    """
    Call the LLM to generate (or revise) Instagram content and return a
    validated PlatformContent dict.

    Args:
        human_turn_message:      The human-turn message for this invocation.
        max_retries:        How many times to retry on bad/malformed JSON output.

    Returns:
        Validated PlatformContent dict.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    messages = [
        _SYSTEM_MESSAGE,
        HumanMessage(content=human_turn_message),
    ]

    last_error = None
    raw_response = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.warning(
                "Content node retry %d/%d due to: %s", attempt, max_retries, last_error
            )
            messages.append(
                HumanMessage(
                    content=CONTENT_NODE_RETRY_PROMPT.format(
                        error_message=str(last_error),
                        bad_response=raw_response,
                    )
                )
            )

        result = _llm.invoke(messages)

        raw_response = (
            result.content
            if isinstance(result.content, str)
            else result.content[0].get("text", "")
        )
        logger.debug("Content node raw response (attempt %d):\n%s", attempt + 1, raw_response)

        try:
            parsed = _parse_content_output(raw_response)
            logger.info(
                "Content node succeeded on attempt %d. Caption: %d chars, %d hashtags.",
                attempt + 1,
                parsed["character_count"],
                len(parsed["hashtags"]),
            )
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e

    raise RuntimeError(
        f"Content node failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────
def content_node(state: ContentState) -> dict:
    """
    LangGraph node: generate (or revise) Instagram content from the recipe.

    Handles two distinct execution paths:

    - First-pass generation (recipe_node → content_node):
       state["human_review"]["status"] is "pending" (or not yet set).
       Builds a fresh generation prompt from the recipe + selected_topic.

    - Edit loop (human_review → content_node):
       state["human_review"]["status"] == "edit_requested".
       Passes the previous caption + reviewer feedback to the LLM for
       targeted revisions, preserving everything that wasn't criticised.

    Args:
        state: The current ContentState.
            Reads from state:
                - recipe             : RecipeData
                - selected_topic     : str
                - trending_topics    : list[str]
                - human_review       : HumanReview  (status + optional feedback)
                - instagram_content  : Optional[PlatformContent]  (edit loop only)

    Returns:
        - instagram_content  : PlatformContent — new or revised content
        - human_review       : reset to {"status": "pending", "feedback": None}
        - current_step       : str      — pipeline breadcrumb

    On failure, appends an error message to state["errors"] and updates
    current_stepto signal failure without crashing the graph.
    """
    run_id = state.get("run_id", "unknown")
    logger.info("=== Content node START (run_id=%s) ===", run_id)
    logger.debug("State before content_node: %s", json.dumps(state, indent=2, default=str))

    recipe = state.get("recipe")
    if not recipe:
        error_msg = "content_node: 'recipe' is missing from state — recipe_node may have failed."
        logger.error(error_msg)
        existing_errors = state.get("errors") or []
        return {
            "errors":       existing_errors + [error_msg],
            "current_step": "content_generation_failed",
        }

    selected_topic = state.get("selected_topic", "")
    trending_topics = state.get("trending_topics", [])
    human_review   = state.get("human_review", {})
    review_status  = human_review.get("status", "pending")
    feedback       = human_review.get("feedback", None)

    # Logic to determine if we're in the edit loop or first-pass generation
    is_edit_loop = (
        review_status == "edit_requested"
        and feedback
        and state.get("instagram_content")
    )

    if is_edit_loop:
        logger.info(
            "Content node: edit loop triggered. Feedback: '%s'", feedback
        )
        human_message = build_content_edit_message(
            previous_content=state["instagram_content"],
            feedback=feedback,
        )
        step_label = "content_edit_complete"
    else:
        logger.info("Content node: first-pass generation for topic '%s'.", selected_topic)
        human_message = build_content_human_message(
            recipe=recipe,
            selected_topic=selected_topic,
            trending_topics=trending_topics,
        )
        step_label = "content_generation_complete"

    # Invoke LLM
    try:
        instagram_content = _invoke_content_node(human_message)

        logger.info(
            "Content node DONE (%s). Caption: %d chars | Hashtags: %d",
            step_label,
            instagram_content["character_count"],
            len(instagram_content["hashtags"]),
        )

        result = {
            "instagram_content": instagram_content,
            "human_review": {
                "status":   "pending",
                "feedback": None,
            },
            "current_step": step_label,
        }
        logger.debug("Content node result: %s", json.dumps(result, indent=2, default=str))
        return result

    except Exception as e:
        logger.exception("Content node FAILED: %s", e)

        existing_errors = state.get("errors") or []
        result = {
            "errors":       existing_errors + [f"content_node: {str(e)}"],
            "current_step": "content_generation_failed",
        }
        logger.debug("Content node error result: %s", json.dumps(result, indent=2, default=str))
        return result