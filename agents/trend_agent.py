"""
agents/trend_agent.py
─────────────────────
The Trend Research Agent - first agent in the content pipeline.

Role in the graph (from builder.py):
    orchestrator → [TREND AGENT] → recipe_agent → ...

Responsibility:
    1. Use search tools to discover what's trending in food/cooking RIGHT NOW
    2. Evaluate candidates and select the single best topic. The best topic must not be in the avoid_topics list from previous runs (if any) to ensure content diversity.
    3. Write `trending_topics` and `selected_topic` back into ContentState. If the topic_override field is set in state, use that as the selected_topic instead of the best topic from research, but still populate trending_topics with real research results for the human's reference

Architecture: ReAct (Reason + Act)
    The LLM is given tools and reasons in a loop:
        Thought → Tool Call → Observation → Thought → ... → Final Answer
    LangChain's `create_react_agent` handles this loop automatically.
    We just supply: the LLM, the tools, and the prompt.
"""


import json
import logging
from datetime import datetime
    
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.agents import create_agent

from graph.state import ContentState
from tools.search_tools import TREND_TOOLS
from prompts.trend import (
    TREND_AGENT_SYSTEM_PROMPT,
    TREND_AGENT_RETRY_PROMPT,
    build_trend_human_message,
)


# ── Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("trend_agent")


def _build_trend_agent():
    """
    Construct and return the ReAct agent for trend research.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",  # Best balance of speed + reasoning for tool use
        temperature=0.3,    # Low temp = more consistent JSON output; slight creativity for topic selection
        max_tokens=4096,    # Trend research responses are verbose;
    )

    agent = create_agent(
        model=llm,
        tools=TREND_TOOLS,
        system_prompt=TREND_AGENT_SYSTEM_PROMPT,
    )

    return agent


# Build once at import time
_agent = _build_trend_agent()


# ─────────────────────────────────────────────────────────────────────────────
#  Output Parser
#  Validates JSON, with a retry mechanism if it is malformed.
# ─────────────────────────────────────────────────────────────────────────────
def _parse_trend_output(raw_text: str) -> dict:
    """
    Extract and validate the JSON payload from the LLM's final message.

    Args:
        raw_text: The full text of the LLM's last message in the ReAct loop.

    Returns:
        A validated dict with keys: trending_topics, selected_topic, reasoning,
        trend_score, sources_consulted.

    Raises:
        ValueError: If the JSON is missing, malformed, or fails schema checks.
    """
    # Strip common LLM noise: markdown fences, leading/trailing whitespace
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        # Remove first and last fence line
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Find the JSON object boundaries (handles preamble text)
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response.")

    data = json.loads(cleaned[start:end])

    # ── Schema validation ────────────────────────────────────────────────────
    # We check the fields WE care about in ContentState.

    if "trending_topics" not in data or not isinstance(data["trending_topics"], list):
        raise ValueError("Missing or invalid 'trending_topics' list.")

    if len(data["trending_topics"]) < 3:
        raise ValueError(
            f"trending_topics must have at least 3 items, got {len(data['trending_topics'])}."
        )

    if "selected_topic" not in data or not data["selected_topic"]:
        raise ValueError("Missing or empty 'selected_topic'.")

    if data["selected_topic"] not in data["trending_topics"]:
        # Soft fix: add it rather than crashing.
        logger.warning(
            "selected_topic '%s' not in trending_topics list - auto-appending.",
            data["selected_topic"],
        )
        data["trending_topics"].append(data["selected_topic"])

    return data


# ─────────────────────────────────────────────────────────────────────────────
#  Core agent invocation with retry
# ─────────────────────────────────────────────────────────────────────────────
def _invoke_trend_agent(avoid_topics: list[str] | None, topic_override: str | None, max_retries: int = 2) -> dict:
    """
    Invoke the ReAct agent and return parsed trend research results.

    Args:
        avoid_topics: Topics to avoid due to recent usage or other reasons, if any.
        topic_override: A specific topic to focus on, if provided.
        max_retries:     How many times to retry on bad JSON output.

    Returns:
        Validated dict from _parse_trend_output.

    Raises:
        RuntimeError: If all retries fail.
    """
    human_message = build_trend_human_message(avoid_topics, topic_override)

    agent_input = {
        "messages": [HumanMessage(content=human_message)]
    }

    last_error = None
    raw_response = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.warning("Trend agent retry %d/%d due to: %s", attempt, max_retries, last_error)
            
            agent_input["messages"].append(
                HumanMessage(
                    content=TREND_AGENT_RETRY_PROMPT.format(
                        error_message=str(last_error),
                        bad_response=raw_response,
                    )
                )
            )

        # Invoke the agent (full ReAct loop)
        result = _agent.invoke(agent_input)

        raw_response = result["messages"][-1].content[0]["text"]
        logger.debug("Trend agent raw response (attempt %d):\n%s", attempt + 1, raw_response)

        try:
            parsed = _parse_trend_output(raw_response)
            logger.info(
                "Trend agent succeeded on attempt %d. Selected: '%s' (score: %s)",
                attempt + 1,
                parsed.get("selected_topic"),
                parsed.get("trend_score"),
            )
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            # Loop continues to retry

    raise RuntimeError(
        f"Trend agent failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────
def trend_node(state: ContentState) -> dict:
    """
    LangGraph node: run trend research and update state.

    Args:
        state: The current ContentState.

    Returns:
        A partial ContentState dict with these keys updated:
          - trending_topics  : list[str]  - all 5 candidates found
          - selected_topic   : str        - the winner
          - current_step     : str        - advances the pipeline breadcrumb

        LangGraph merges this into the full state automatically.
        Keys NOT included in the return dict are left unchanged.

    Error handling:
        On failure, we append to state["errors"] and return the state
        unchanged rather than crashing the graph.  The orchestrator or
        a supervisor can inspect errors[] and decide whether to retry.
    """
    run_id = state.get("run_id", "unknown")
    logger.info("=== Trend Agent START (run_id=%s) ===", run_id)

    try:
        result = _invoke_trend_agent(
            avoid_topics=state.get("avoid_topics") or None,
            topic_override=state.get("topic_override") or None,
        )

        logger.info(
            "Trend Agent DONE. Selected: '%s' from candidates: %s",
            result["selected_topic"],
            result["trending_topics"],
        )

        return {
            "trending_topics": result["trending_topics"],
            "selected_topic":  result["selected_topic"],
            "current_step":    "trend_research_complete",
        }

    except Exception as e:
        logger.exception("Trend Agent FAILED: %s", e)

        existing_errors = state.get("errors") or []
        return {
            "errors":       existing_errors + [f"trend_agent: {str(e)}"],
            "current_step": "trend_research_failed",
        }