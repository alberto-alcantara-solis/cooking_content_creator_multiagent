from typing import TypedDict, Optional, Literal
from langgraph.graph import MessagesState


class PlatformContent(TypedDict):
    caption: str
    hashtags: list[str]
    character_count: int


class RecipeData(TypedDict):
    title: str
    description: str          # Short hook, 1-2 sentences
    ingredients: list[str]
    steps: list[str]
    prep_time: str
    difficulty: Literal["Easy", "Medium", "Hard"]


class ImageData(TypedDict):
    comfyui_prompt: str       # The text prompt sent to ComfyUI
    local_path: str           # Where the image was saved locally
    status: Literal["pending", "generating", "ready", "failed"]


class HumanReview(TypedDict):
    status: Literal["pending", "approved", "rejected", "edit_requested"]
    feedback: Optional[str]   # If user requests edits


class ContentState(TypedDict):
    # --- Orchestration ---
    run_id: str
    current_step: str

    # --- Trend Research ---
    trending_topics: list[str]
    selected_topic: str

    # --- Recipe ---
    recipe: Optional[RecipeData]

    # --- Content per platform ---
    instagram_content: Optional[PlatformContent]

    # --- Image ---
    image: Optional[ImageData]

    # --- Human review ---
    human_review: HumanReview

    # --- Publishing ---
    buffer_ig_post_id: Optional[str]
    published: bool

    # --- Error handling ---
    errors: list[str]