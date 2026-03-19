"""
tools/image_critique_tool.py
────────────────────────────
LangChain @tool that the Image Agent uses to evaluate a generated image.
"""

import base64
import json
import logging
from pathlib import Path

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from prompts.image import CRITIQUE_SYSTEM

logger = logging.getLogger("image_critique_tool")

CRITIQUE_PASS_THRESHOLD = 7.0

_vision_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.2,  # Low temp for consistent, repeatable quality judgments
    max_tokens=512,   # Verdict JSON is short
)


def _load_image_as_base64(image_path: str) -> tuple[str, str]:
    """
    Load an image from disk and return (base64_string, mime_type).

    Supported formats: PNG, JPG, JPEG, WEBP.

    Args:
        image_path: Path to the image.

    Returns:
        Tuple of (base64-encoded image data, MIME type string).

    Raises:
        FileNotFoundError: If the image doesn't exist.
        ValueError: If the file extension is unsupported.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: '{path.resolve()}'")

    ext_to_mime = {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = ext_to_mime.get(path.suffix.lower())
    if not mime_type:
        raise ValueError(
            f"Unsupported image format '{path.suffix}'. "
            "ComfyUI outputs PNG by default — this should not happen."
        )

    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime_type


def _parse_critique_response(raw: str) -> dict:
    """
    Extract and validate the JSON verdict from the vision LLM's response.

    Raises:
        ValueError: If JSON is missing or required fields are absent.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines   = [l for l in cleaned.split("\n") if not l.startswith("```")]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON found in vision LLM response.")

    data = json.loads(cleaned[start:end])

    if "overall_score" not in data:
        raise ValueError("Missing 'overall_score' in critique response.")
    if "approved" not in data:
        raise ValueError("Missing 'approved' in critique response.")

    # Ensure approved is consistent with threshold
    data["approved"] = float(data["overall_score"]) >= CRITIQUE_PASS_THRESHOLD

    return data


# ─────────────────────────────────────────────────────────────────────────────
#  LangChain Tool
# ─────────────────────────────────────────────────────────────────────────────
@tool
def critique_food_image(image_path: str, recipe_title: str, selected_topic: str) -> str:
    """
    Evaluate a generated food photograph for Instagram quality.

    Use this tool AFTER generate_food_image returns a local file path.
    Pass the exact path returned by generate_food_image.

    Args:
        image_path:      Absolute path to the generated image (returned by
                         generate_food_image).
        recipe_title:    The recipe name — helps calibrate expectations for
                         the dish's typical appearance.
        selected_topic:  The trending topic — helps calibrate social media fit.

    Returns:
        A JSON string with keys:
            overall_score (float 0-10)
            approved (bool) — True if score >= 7.0
            scores (dict)   — per-dimension breakdown
            strengths (str)
            weaknesses (str)
            prompt_revision_hint (str | null) — how to fix the prompt if not approved
    """
    logger.info(
        "Critiquing image: '%s' (recipe: %s | topic: %s)",
        image_path, recipe_title, selected_topic,
    )

    try:
        image_b64, mime_type = _load_image_as_base64(image_path)
    except (FileNotFoundError, ValueError) as e:
        error_result = {
            "overall_score":        0.0,
            "approved":             False,
            "scores":               {},
            "strengths":            "",
            "weaknesses":           f"Could not load image: {e}",
            "prompt_revision_hint": "Ensure the image file exists before critiquing.",
            "error":                str(e),
        }
        logger.error("Image load failed: %s", e)
        return json.dumps(error_result)

    # Build the multimodal message: system context + image + text question
    human_message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": CRITIQUE_SYSTEM,
            },
            {
                "type":      "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            },
            {
                "type": "text",
                "text": (
                    f"Recipe: {recipe_title}\n"
                    f"Trending hook: {selected_topic}\n\n"
                    "Evaluate this food photograph and return your JSON verdict."
                ),
            },
        ]
    )

    try:
        result      = _vision_llm.invoke([human_message])
        raw_response = (
            result.content
            if isinstance(result.content, str)
            else result.content[0].get("text", "")
        )
        logger.debug("Vision LLM raw response:\n%s", raw_response)
        verdict = _parse_critique_response(raw_response)

    except Exception as e:
        logger.exception("Vision critique LLM call failed: %s", e)
        verdict = {
            "overall_score":        0.0,
            "approved":             False,
            "scores":               {},
            "strengths":            "",
            "weaknesses":           f"Critique call failed: {e}",
            "prompt_revision_hint": "Retry generation — the critique step itself failed.",
            "error":                str(e),
        }

    logger.info(
        "Critique result: score=%.1f | approved=%s | weakness: %s",
        verdict.get("overall_score", 0),
        verdict.get("approved", False),
        verdict.get("weaknesses", ""),
    )

    return json.dumps(verdict, indent=2)