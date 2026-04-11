"""
tools/buffer_tools.py
─────────────────────
Plain Python functions that interact with the Buffer API v1.

Also exported as LangChain @tool wrappers (PUBLISHER_TOOLS) in case they
are ever needed inside an agent. Right now the publisher_node calls the plain
functions directly — no LLM in the loop.
"""

import os
import json
import mimetypes
import logging
from pathlib import Path

import requests
from langchain_core.tools import tool


logger = logging.getLogger("buffer_tools")

_BUFFER_BASE = "https://api.bufferapp.com/"


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _auth_params() -> dict:
    token = os.getenv("BUFFER_ACCESS_TOKEN")
    if not token:
        raise EnvironmentError(
            "BUFFER_ACCESS_TOKEN is not set. "
            "Get a token at https://buffer.com/developers/apps and add it to your .env."
        )
    return {"access_token": token}


def _raise_for_status(resp: requests.Response) -> None:
    if not resp.ok:
        try:
            body = resp.json()
            message = body.get("message") or body.get("error") or resp.text
        except Exception:
            message = resp.text
        raise RuntimeError(f"Buffer API error {resp.status_code}: {message}")


def get_buffer_instagram_profile_id() -> dict:
    """
    Return the Buffer profile ID for the connected Instagram account.

    Returns:
        {"profile_id": str, "username": str}

    Raises:
        EnvironmentError: if BUFFER_ACCESS_TOKEN is missing.
        RuntimeError:     if no IG profile found or Buffer API errors.
    """
    resp = requests.get(
        f"{_BUFFER_BASE}/profiles.json",
        params=_auth_params(),
        timeout=15,
    )
    _raise_for_status(resp)

    profiles = resp.json()
    ig_profiles = [p for p in profiles if p.get("service", "").lower() == "instagram"]

    if not ig_profiles:
        raise RuntimeError(
            "No Instagram profile found in your Buffer account. "
            "Connect one at buffer.com."
        )

    chosen = ig_profiles[0]
    return {
        "profile_id": chosen["id"],
        "username":   chosen.get("service_username", "unknown"),
    }


def upload_image_to_buffer(local_path: str) -> dict:
    """
    Upload a local image to Buffer's media CDN.

    Args:
        local_path: Absolute path to the image file on disk.

    Returns:
        {"media_url": str, "media_type": str, "file_name": str}

    Raises:
        FileNotFoundError: if the file doesn't exist.
        RuntimeError:      on Buffer API error or missing URL in response.
    """
    path = Path(local_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {local_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Path is not a file: {local_path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"

    with open(path, "rb") as f:
        resp = requests.post(
            f"{_BUFFER_BASE}/media/upload.json",
            params=_auth_params(),
            files={"file": (path.name, f, mime_type)},
            timeout=60,
        )
    _raise_for_status(resp)

    data = resp.json()
    media_url = data.get("media", {}).get("picture") or data.get("url")

    if not media_url:
        raise RuntimeError(f"Upload succeeded but no media URL in Buffer response: {data}")

    logger.info("Image uploaded to Buffer CDN: %s", media_url)
    return {
        "media_url":  media_url,
        "media_type": mime_type,
        "file_name":  path.name,
    }


def create_buffer_post(
    profile_id: str,
    caption: str,
    hashtags: list[str],
    media_url: str,
    publish_now: bool = True,
    scheduled_at: str = "",
) -> dict:
    """
    Create an Instagram post via Buffer.

    Args:
        profile_id:   Buffer profile ID (from get_buffer_instagram_profile_id).
        caption:      Post caption text (without hashtags).
        hashtags:     List of hashtag strings — appended after two newlines.
        media_url:    Public CDN URL of the image (from upload_image_to_buffer).
        publish_now:  If True, publish immediately. Otherwise queue.
        scheduled_at: ISO-8601 UTC timestamp for a specific schedule time.

    Returns:
        {"post_id": str, "status": str, "profile_id": str,
         "share_url": str, "scheduled_at": str | None}

    Raises:
        RuntimeError: on Buffer API error or empty response.
    """
    hashtag_string = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags)
    full_text = f"{caption}\n\n{hashtag_string}".strip()

    payload = {
        **_auth_params(),
        "profile_ids[]": profile_id,
        "text":          full_text,
        "media[photo]":  media_url,
    }

    if publish_now:
        payload["now"] = "true"
    elif scheduled_at:
        payload["scheduled_at"] = scheduled_at

    resp = requests.post(
        f"{_BUFFER_BASE}/updates/create.json",
        data=payload,
        timeout=20,
    )
    _raise_for_status(resp)

    data = resp.json()
    updates = data.get("updates", [])
    if not updates:
        raise RuntimeError(f"Buffer returned no update objects: {data}")

    update = updates[0]
    post_id = update.get("id", "")

    logger.info(
        "Buffer post created. ID: %s | Status: %s | Now: %s",
        post_id, update.get("status"), publish_now,
    )

    return {
        "post_id":      post_id,
        "status":       update.get("status", "unknown"),
        "profile_id":   profile_id,
        "share_url":    update.get("shared_url") or f"https://buffer.com/updates/{post_id}",
        "scheduled_at": update.get("due_at") or scheduled_at or None,
    }


def verify_buffer_post(post_id: str) -> dict:
    """
    Fetch a Buffer post by ID and return its current status.

    Args:
        post_id: Buffer update ID.

    Returns:
        {"post_id": str, "status": str, "text": str,
         "due_at": str | None, "created_at": str | None}

    Raises:
        RuntimeError: on Buffer API error.
    """
    resp = requests.get(
        f"{_BUFFER_BASE}/updates/{post_id}.json",
        params=_auth_params(),
        timeout=15,
    )
    _raise_for_status(resp)

    data = resp.json()
    return {
        "post_id":    data.get("id"),
        "status":     data.get("status"),
        "text":       data.get("text", "")[:200],
        "due_at":     data.get("due_at"),
        "created_at": data.get("created_at"),
    }


def get_pending_posts(profile_id: str) -> list[dict]:
    """
    Fetch pending (queued) updates for a Buffer profile.

    Used as a duplicate-post safety check.

    Args:
        profile_id: Buffer profile ID.

    Returns:
        [{"post_id": str, "status": str, "text": str, "created_at": str}, ...]
    """
    try:
        resp = requests.get(
            f"{_BUFFER_BASE}/profiles/{profile_id}/updates/pending.json",
            params=_auth_params(),
            timeout=15,
        )
        _raise_for_status(resp)

        return [
            {
                "post_id":    u.get("id"),
                "status":     u.get("status"),
                "text":       u.get("text", "")[:300],
                "created_at": u.get("created_at"),
            }
            for u in resp.json().get("updates", [])
        ]

    except Exception as e:
        logger.warning("get_pending_posts failed (non-fatal): %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  LangChain @tool wrappers
# ─────────────────────────────────────────────────────────────────────────────
@tool
def tool_get_buffer_instagram_profile_id() -> str:
    """LangChain tool wrapper — get the Buffer Instagram profile ID."""
    try:
        return json.dumps(get_buffer_instagram_profile_id())
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def tool_upload_image_to_buffer(local_path: str) -> str:
    """LangChain tool wrapper — upload a local image to Buffer CDN."""
    try:
        return json.dumps(upload_image_to_buffer(local_path))
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def tool_create_buffer_post(
    profile_id: str,
    caption: str,
    hashtags: list[str],
    media_url: str,
    publish_now: bool = True,
    scheduled_at: str = "",
) -> str:
    """LangChain tool wrapper — create a Buffer post."""
    try:
        return json.dumps(create_buffer_post(
            profile_id, caption, hashtags, media_url, publish_now, scheduled_at,
        ))
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def tool_verify_buffer_post(post_id: str) -> str:
    """LangChain tool wrapper — verify a Buffer post by ID."""
    try:
        return json.dumps(verify_buffer_post(post_id))
    except Exception as e:
        return json.dumps({"error": str(e)})


PUBLISHER_TOOLS = [
    tool_get_buffer_instagram_profile_id,
    tool_upload_image_to_buffer,
    tool_create_buffer_post,
    tool_verify_buffer_post,
]