"""
nodes/publisher_agent.py
─────────────────────────
The Publisher Node — final node in the content pipeline.

Role in the graph (from builder.py):
    human_review → [PUBLISHER NODE] → END

Responsibility:
    1. Validate that the image is ready and content has been human-approved.
    2. Execute the four Buffer API steps in order:
           get profile ID → upload image → create post → verify post
    3. Write `buffer_ig_post_id` and `published = True` back into ContentState.

Architecture: plain Python node — NO LLM, NO ReAct loop.
"""

import logging

from graph.state import ContentState
from tools.buffer_tools import (
    get_buffer_instagram_profile_id,
    upload_image_to_buffer,
    create_buffer_post,
    verify_buffer_post,
    get_pending_posts,
)


logger = logging.getLogger("publisher_node")


def _validate_state(state: ContentState) -> str | None:
    """
    Return an error string if the state is not ready to publish, else None.

    Checks:
        1. human_review.status must be "approved".
        2. instagram_content must exist with a non-empty caption.
        3. image must exist, have status "ready", and a non-empty local_path.
    """
    review_status = (state.get("human_review") or {}).get("status")
    if review_status != "approved":
        return (
            f"Cannot publish: human_review.status is '{review_status}', expected 'approved'. "
            "The graph should not have routed here without approval."
        )

    ig = state.get("instagram_content")
    if not ig or not ig.get("caption", "").strip():
        return "Cannot publish: instagram_content is missing or has an empty caption."

    image = state.get("image")
    if not image:
        return "Cannot publish: image data is missing from state."
    if image.get("status") != "ready":
        return (
            f"Cannot publish: image status is '{image.get('status')}', expected 'ready'. "
            "The image_agent may have failed."
        )
    if not image.get("local_path", "").strip():
        return "Cannot publish: image.local_path is empty."

    return None


def _find_existing_post(profile_id: str, caption: str) -> dict | None:
    """
    Check Buffer's pending queue to see if our post already exists.

    Called when create_buffer_post() fails or its response can't be parsed,
    to determine whether the post was silently created before the error.

    Args:
        profile_id: Buffer profile ID to query.
        caption:    The caption text we attempted to post.

    Returns:
        The matching post dict if found, else None.
    """
    fingerprint = caption.strip()[:80].lower()
    pending = get_pending_posts(profile_id)

    for post in pending:
        if fingerprint in (post.get("text") or "").lower():
            logger.info(
                "Duplicate-post guard: found existing pending post ID=%s that matches our caption.",
                post.get("post_id"),
            )
            return post

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────
def publisher_node(state: ContentState) -> dict:
    """
    LangGraph node: publish the approved post to Instagram via Buffer.

    Args:
        state: The current ContentState.
            Reads from state:
                - human_review        : must be {"status": "approved"}
                - instagram_content   : {"caption": str, "hashtags": list[str], ...}
                - image               : {"local_path": str, "status": "ready", ...}
                - recipe              : {"title": str, ...}  (for log readability only)

    Returns:
        - buffer_ig_post_id   : str   — Buffer update ID (empty string on failure)
        - published           : bool  — True only on confirmed publish
        - current_step        : str   — pipeline breadcrumb

    On failure, appends an error message to state["errors"] and updates
    current_step to signal failure without crashing the graph.
    """
    run_id = state.get("run_id", "unknown")
    logger.info("=== Publisher Node START (run_id=%s) ===", run_id)

    preflight_error = _validate_state(state)
    if preflight_error:
        logger.error("Publisher pre-flight failed: %s", preflight_error)
        return _failure(state, preflight_error)

    ig     = state["instagram_content"]
    image  = state["image"]
    recipe = state.get("recipe") or {}

    caption          = ig["caption"]
    hashtags         = ig.get("hashtags", [])
    image_local_path = image["local_path"]
    recipe_title     = recipe.get("title", state.get("selected_topic", "Recipe"))

    logger.info("Step 1/4 — Resolving Buffer Instagram profile ID...")
    try:
        profile_result = get_buffer_instagram_profile_id()
        profile_id     = profile_result["profile_id"]
        logger.info("Profile resolved: %s (%s)", profile_id, profile_result.get("username"))
    except Exception as e:
        return _failure(state, f"[step 1 / get_profile] {e}")

    logger.info("Step 2/4 — Uploading image: %s", image_local_path)
    try:
        upload_result = upload_image_to_buffer(image_local_path)
        media_url     = upload_result["media_url"]
        logger.info("Image uploaded: %s", media_url)
    except Exception as e:
        return _failure(state, f"[step 2 / upload_image] {e}")

    logger.info("Step 3/4 — Creating Buffer post for '%s'...", recipe_title)
    post_id = None
    try:
        post_result = create_buffer_post(
            profile_id=profile_id,
            caption=caption,
            hashtags=hashtags,
            media_url=media_url,
        )
        post_id = post_result["post_id"]
        logger.info("Post created. ID: %s | Status: %s", post_id, post_result.get("status"))

    except Exception as e:
        # The create call raised before we got a post_id back — but the HTTP
        # request may have reached Buffer and the post may exist already.
        # Check the pending queue before deciding to fail.
        logger.warning(
            "create_buffer_post raised an exception: %s. "
            "Checking pending queue for duplicate before failing...", e
        )

        existing = _find_existing_post(profile_id, caption)

        if existing:
            # Post was created despite the exception — treat as success.
            post_id = existing["post_id"]
            logger.info(
                "Duplicate-post guard: recovered post ID=%s from pending queue. "
                "Skipping re-create.", post_id,
            )
        else:
            # Genuinely failed and no post found — safe to surface the error.
            return _failure(state, f"[step 3 / create_post] {e}")

    logger.info("Step 4/4 — Verifying post ID: %s", post_id)
    try:
        verify_result = verify_buffer_post(post_id)
        verified_status = verify_result.get("status", "unknown")

        if verified_status == "failed":
            return _failure(
                state,
                f"[step 4 / verify_post] Buffer reported post status 'failed' for ID {post_id}.",
            )

        logger.info("Post verified. Status: %s", verified_status)

    except Exception as e:
        # Verification failed, but the post was already created.
        # Log a warning and continue.
        logger.warning(
            "verify_buffer_post raised an exception for post ID=%s: %s. "
            "Treating post as published (create succeeded).", post_id, e,
        )

    logger.info(
        "=== Publisher Node DONE. Post ID: %s | Recipe: '%s' ===", post_id, recipe_title
    )

    return {
        "buffer_ig_post_id": post_id,
        "published":         True,
        "current_step":      "published",
    }


def _failure(state: ContentState, message: str) -> dict:
    """Append to errors and return a failed-publish partial state."""
    logger.error("Publisher Node FAILED: %s", message)
    existing_errors = state.get("errors") or []
    return {
        "errors":       existing_errors + [f"publisher_node: {message}"],
        "published":    False,
        "current_step": "publishing_failed",
    }