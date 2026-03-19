"""
tools/comfyui_tools.py
──────────────────────
ComfyUI REST API client used by the Image Agent.
"""

import json
import logging
import os
import time
import copy
from pathlib import Path

import requests

from langchain_core.tools import tool

logger = logging.getLogger("comfyui_tools")


# ─────────────────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────────────────
COMFYUI_HOST             = os.getenv("COMFYUI_HOST", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_WORKFLOW_PATH    = os.getenv("COMFYUI_WORKFLOW_PATH", "assets/workflow_api.json")
COMFYUI_OUTPUT_DIR       = os.getenv("COMFYUI_OUTPUT_DIR", "images/")
COMFYUI_INITIAL_WAIT     = float(os.getenv("COMFYUI_INITIAL_WAIT", "30"))  # 30 sec
COMFYUI_POLL_INTERVAL    = float(os.getenv("COMFYUI_POLL_INTERVAL", "3"))    # 3 sec
COMFYUI_TIMEOUT          = float(os.getenv("COMFYUI_TIMEOUT", "180"))  # 180 sec


# ─────────────────────────────────────────────────────────────────────────────
#  Workflow helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load_workflow() -> dict:
    """Load the ComfyUI API-format workflow JSON."""
    path = Path(COMFYUI_WORKFLOW_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"ComfyUI workflow not found at '{path.resolve()}'.\n"
            "Export it from ComfyUI:  Settings → Dev Mode → Save (API Format)\n"
            f"Then set COMFYUI_WORKFLOW_PATH in your .env."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_positive_node_id(workflow: dict) -> str:
    """
    Auto-detect the positive CLIPTextEncode node by tracing the KSampler's
    'positive' input link — no hard-coded node IDs needed.

    Falls back to the first CLIPTextEncode in the workflow if no KSampler
    is found.
    """
    for node_id, node_data in workflow.items():
        if node_data.get("class_type") in {"KSampler", "KSamplerAdvanced"}:
            positive_link = node_data["inputs"].get("positive")
            if isinstance(positive_link, list) and len(positive_link) >= 1:
                found_id = str(positive_link[0])
                logger.debug(
                    "Auto-detected positive prompt node: '%s' (linked from KSampler '%s')",
                    found_id, node_id,
                )
                return found_id

    for node_id, node_data in workflow.items():
        if node_data.get("class_type") == "CLIPTextEncode":
            logger.warning(
                "Could not trace from KSampler — falling back to first "
                "CLIPTextEncode node: '%s'. Verify this is your positive prompt node.",
                node_id,
            )
            return node_id

    raise ValueError(
        "Could not find a positive prompt node in the workflow. "
        "Ensure your workflow_api.json contains a KSampler → CLIPTextEncode connection."
    )


def _inject_prompt(workflow: dict, positive_prompt: str) -> dict:
    """
    Return a deep copy of `workflow` with the prompts injected into the
    correct nodes. The original dict is never mutated.
    """
    wf = copy.deepcopy(workflow)

    wf[_find_positive_node_id(wf)]["inputs"]["text"] = positive_prompt
    logger.debug("Positive prompt injected.")

    return wf


# ─────────────────────────────────────────────────────────────────────────────
#  ComfyUIClient
# ─────────────────────────────────────────────────────────────────────────────
class ComfyUIClient:
    """
    Thin wrapper around the ComfyUI REST API.

    Polling strategy (two-phase):
        - Initial wait: long sleep (e.g. 30s) to allow for image generation.
        - Active polling: short, regular intervals (e.g. every 3s) to

    Usage (from image_agent tools):
        client = ComfyUIClient()
        local_path = client.generate_image(positive_prompt, negative_prompt, run_id)
    """

    def __init__(
        self,
        run_id: str,
        host: str          = COMFYUI_HOST,
        initial_wait: float  = COMFYUI_INITIAL_WAIT,
        poll_interval: float = COMFYUI_POLL_INTERVAL,
        timeout: float       = COMFYUI_TIMEOUT,
        output_dir: str      = COMFYUI_OUTPUT_DIR,
    ):
        self.run_id         = run_id
        self.host          = host.rstrip("/")
        self.initial_wait  = initial_wait
        self.poll_interval = poll_interval
        self.timeout       = timeout
        self.output_dir    = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._session   = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _queue_prompt(self, workflow: dict) -> str:
        url = f"{self.host}/prompt"
        payload = {"prompt": workflow, "client_id": self.run_id}
        try:
            resp = self._session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ComfyUIError(
                f"Failed to queue prompt. Is ComfyUI running at {self.host}?\n"
                f"Error: {e}"
            ) from e
        data = resp.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI did not return a prompt_id. Response: {data}")
        return prompt_id

    def _poll_until_done(self, prompt_id: str) -> dict:
        """
        Two-phase wait: long initial sleep, then short active polling.
        """
        deadline      = time.time() + self.timeout
        total_elapsed = 0.0

        # Phase 1: initial sleep
        logger.info(
            "ComfyUI: waiting %.0f min before first poll (prompt_id=%s)...",
            self.initial_wait / 60, prompt_id,
        )
        time.sleep(self.initial_wait)
        logger.info(
            "Initial wait complete. Active polling every %.0fs (prompt_id=%s).",
            self.poll_interval, prompt_id,
        )

        # Phase 2: active polling
        url = f"{self.host}/history/{prompt_id}"

        while time.time() < deadline:
            try:
                resp    = self._session.get(url, timeout=15)
                resp.raise_for_status()
                history = resp.json()
            except requests.RequestException as e:
                logger.warning("Poll request failed (will retry): %s", e)
                time.sleep(self.poll_interval)
                total_elapsed += self.poll_interval
                continue

            if history:
                job_data = history.get(prompt_id, {})

                if job_data.get("status", {}).get("status_str") == "error":
                    raise ComfyUIError(
                        f"ComfyUI error for job {prompt_id}: "
                        f"{job_data.get('status', {}).get('messages', [])}"
                    )

                for node_id, node_output in job_data.get("outputs", {}).items():
                    images = node_output.get("images", [])
                    if images:
                        logger.info("Image ready in node '%s': %s", node_id, images[0])
                        return images[0]

                raise ComfyUIError(
                    f"Job {prompt_id} finished but no output images found."
                )

            logger.debug(
                "Still generating... (%.0fs elapsed, prompt_id=%s)",
                total_elapsed, prompt_id,
            )
            time.sleep(self.poll_interval)
            total_elapsed += self.poll_interval

        raise ComfyUIError(
            f"Job {prompt_id} timed out after {self.timeout:.0f}s. "
            "Increase COMFYUI_TIMEOUT or check ComfyUI logs."
        )

    def _download_and_save(self, image_info: dict, run_id: str) -> str:
        filename  = image_info.get("filename", None)
        subfolder = image_info.get("subfolder", "")
        img_type  = image_info.get("type",      "output")

        try:
            resp = self._session.get(
                f"{self.host}/view",
                params={"filename": filename, "subfolder": subfolder, "type": img_type},
                timeout=60, stream=True,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ComfyUIError(f"Failed to download image '{filename}': {e}") from e

        local_path = self.output_dir / f"{run_id}_{filename}"
        with local_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return str(local_path.resolve())

    def generate_image(self, positive_prompt: str, run_id: str = "run") -> str:
        """
        Full pipeline: inject prompts → queue → initial wait → poll → download.

        Returns:
            Absolute path (str) of the saved image on disk.

        Raises:
            ComfyUIError on any failure.
        """
        workflow  = _inject_prompt(_load_workflow(), positive_prompt)
        prompt_id = self._queue_prompt(workflow)
        logger.info("ComfyUI job queued → prompt_id=%s", prompt_id)

        output_info = self._poll_until_done(prompt_id)
        return self._download_and_save(output_info, run_id)

    def health_check(self) -> bool:
        """Return True if ComfyUI is reachable, False otherwise."""
        try:
            return self._session.get(f"{self.host}/system_stats", timeout=5).ok
        except requests.RequestException:
            return False


# ─────────────────────────────────────────────────────────────────────────────
#  Custom exception
# ─────────────────────────────────────────────────────────────────────────────
class ComfyUIError(Exception):
    """Raised when any step of the ComfyUI generation pipeline fails."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
#  LangChain Tool
# ─────────────────────────────────────────────────────────────────────────────
@tool
def generate_food_image(positive_prompt: str, run_id: str) -> str:
    """
    Submit a prompt to ComfyUI and wait for the generated image.

    Args:
        positive_prompt:  Detailed food photography description for the diffusion model.
        run_id:           Pipeline run ID used to name the output file.

    Returns:
        The absolute local file path of the generated image (str),
        OR an error message string starting with "ERROR:" if generation failed.
    """
    comfyui_client = ComfyUIClient(run_id=run_id)
    logger.info(
        "generate_food_image called (run_id=%s). "
        "Submitting to ComfyUI — this will take ~%.0f min...",
        run_id, comfyui_client.initial_wait / 60,
    )

    if not comfyui_client.health_check():
        return (
            "ERROR: ComfyUI is not reachable. "
            f"Make sure ComfyUI is running at {comfyui_client.host} before retrying. "
            "Start it with: python main.py (inside your ComfyUI directory)."
        )

    try:
        local_path = comfyui_client.generate_image(
            positive_prompt=positive_prompt,
            run_id=run_id,
        )
        logger.info("generate_food_image: image saved to '%s'", local_path)
        return local_path

    except ComfyUIError as e:
        logger.error("generate_food_image: ComfyUI error: %s", e)
        return f"ERROR: {e}"

    except Exception as e:
        logger.exception("generate_food_image: unexpected error: %s", e)
        return f"ERROR: Unexpected failure: {e}"
