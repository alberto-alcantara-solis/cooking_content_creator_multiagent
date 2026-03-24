"""
nodes/image_agent.py
────────────────────
The Image Generation Agent — runs in parallel with content_node.

Role in the graph (from builder.py):
                         ┌─  content_node  ─┐
    recipe_node ─────────┤                  ├──► human_review
                         └─ [IMAGE AGENT]  ─┘

Architecture: ReAct (Reason + Act)

Tools:
    generate_food_image   — wraps ComfyUIClient to generate an image
    critique_food_image   — to evaluate the image quality
"""

import json
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from graph.state import ContentState, ImageData
from tools.comfyui_tools import generate_food_image
from tools.image_critique_tool import critique_food_image
from prompts.image import (
    IMAGE_AGENT_SYSTEM_PROMPT,
    IMAGE_AGENT_RETRY_PROMPT,
    build_image_human_message,
)


logger = logging.getLogger("image_agent")


# ─────────────────────────────────────────────────────────────────────────────
#  Agent setup
# ─────────────────────────────────────────────────────────────────────────────
def _build_image_agent():
    """
    Build and return the ReAct image agent.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.4,   # Moderate: creative enough to write good SD prompts,
        max_tokens=4096,   # focused enough for JSON output and structured reasoning
    )

    agent = create_react_agent(
        model=llm,
        tools=[generate_food_image, critique_food_image],
        prompt=IMAGE_AGENT_SYSTEM_PROMPT,
    )

    return agent


# Build once at import time
_agent = _build_image_agent()


# ─────────────────────────────────────────────────────────────────────────────
#  Output parser
#  Validates JSON, with a retry mechanism if it is malformed.
# ─────────────────────────────────────────────────────────────────────────────
def _parse_image_agent_output(raw_text: str) -> dict:
    """
    Extract and validate the JSON Final Answer from the agent's last message.

    Args:
        raw_text: The full text of the agent's final message.

    Returns:
        Validated dict with: local_path, comfyui_prompt, critique_score,
        critique_feedback, attempts, status.

    Raises:
        ValueError: If JSON is missing or required fields are absent.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines   = [l for l in cleaned.split("\n") if not l.startswith("```")]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in agent's Final Answer.")

    data = json.loads(cleaned[start:end])

    # Required fields
    for field in ("local_path", "comfyui_prompt", "status"):
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in agent output.")

    # Fill optional fields with safe defaults
    data.setdefault("critique_score",    0.0)
    data.setdefault("critique_feedback", "")
    data.setdefault("attempts",          1)

    return data


# ─────────────────────────────────────────────────────────────────────────────
#  Core agent invocation with retry
# ─────────────────────────────────────────────────────────────────────────────
def _invoke_image_agent(recipe, selected_topic: str, run_id: str, max_retries: int = 2) -> dict:
    """
    Run the ReAct agent loop and return a parsed result dict.

    Args:
        recipe:          RecipeData from state.
        selected_topic:  The trending topic string.
        run_id:          Pipeline run ID.
        max_retries:     How many times to re-prompt if the Final Answer JSON is bad.

    Returns:
        Validated result dict.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    human_message = build_image_human_message(
        recipe=recipe,
        selected_topic=selected_topic,
        run_id=run_id,
    )

    agent_input  = {"messages": [HumanMessage(content=human_message)]}
    last_error   = None
    raw_response = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.warning(
                "Image agent output retry %d/%d due to malformed JSON: %s",
                attempt, max_retries, last_error,
            )
            
            agent_input["messages"].append(
                HumanMessage(
                    content=IMAGE_AGENT_RETRY_PROMPT.format(
                        error_message=str(last_error),
                        bad_response=raw_response,
                    )
                )
            )

        # Invoke the agent (full ReAct loop)
        result = _agent.invoke(agent_input)

        last_message = result["messages"][-1]
        raw_response = (
            last_message.content
            if isinstance(last_message.content, str)
            else last_message.content[0].get("text", "")
        )
        logger.debug("Image agent raw Final Answer (attempt %d):\n%s", attempt + 1, raw_response)

        try:
            parsed = _parse_image_agent_output(raw_response)
            logger.info(
                "Image agent Final Answer parsed (attempt %d). "
                "status=%s | score=%.1f | path=%s",
                attempt + 1,
                parsed["status"],
                parsed.get("critique_score", 0),
                parsed["local_path"],
            )
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e

    raise RuntimeError(
        f"Image agent Final Answer parsing failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────
def image_node(state: ContentState) -> dict:
    """
    LangGraph node: run the image ReAct agent and write ImageData into state.

    This node runs in parallel with content_node

    Args:
        state: The current ContentState.
            Reads: recipe, selected_topic, run_id

    Returns:
        - image        : ImageData
        - current_step : str

    Error handling:
        On failure, we append to state["errors"] and return the state
        unchanged rather than crashing the graph.  The orchestrator or
        a supervisor can inspect errors[] and decide whether to retry.
    """
    run_id = state.get("run_id", "unknown")
    logger.info("=== Image Agent START (run_id=%s) ===", run_id)

    recipe = state.get("recipe")
    if not recipe:
        error_msg = "image_agent: 'recipe' missing from state — recipe_node may have failed."
        logger.error(error_msg)
        return {
            "image": ImageData(comfyui_prompt="", local_path="", status="failed"),
            "errors":       (state.get("errors") or []) + [error_msg],
            "current_step": "image_generation_failed",
        }

    selected_topic = state.get("selected_topic", "")

    try:
        result = _invoke_image_agent(
            recipe=recipe,
            selected_topic=selected_topic,
            run_id=run_id,
        )

        status     = result.get("status", "failed")
        local_path = result.get("local_path", "")

        logger.info(
            "Image Agent DONE. status=%s | score=%.1f | attempts=%d | path=%s",
            status,
            result.get("critique_score", 0),
            result.get("attempts", 1),
            local_path,
        )

        image_data = ImageData(
            comfyui_prompt=result.get("comfyui_prompt", ""),
            local_path=local_path,
            status=status,
        )

        # If the agent marked it failed, also record the feedback in errors
        extra_errors = []
        if status == "failed":
            feedback = result.get("critique_feedback", "No feedback available.")
            extra_errors = [f"image_agent: generation marked failed. Feedback: {feedback}"]

        return {
            "image":        image_data,
            "errors":       (state.get("errors") or []) + extra_errors,
            "current_step": "image_generation_complete" if status == "ready" else "image_generation_failed",
        }

    except Exception as e:
        logger.exception("Image Agent FAILED with unhandled exception: %s", e)
        return {
            "image": ImageData(comfyui_prompt="", local_path="", status="failed"),
            "errors":       (state.get("errors") or []) + [f"image_agent: {str(e)}"],
            "current_step": "image_generation_failed",
        }