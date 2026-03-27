from typing import TypedDict, Optional, Literal, Annotated


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
    status: Literal[
        "pending",
        "approved",
        "rejected",
        "edit_requested",       # Re-generate content only
        "regenerate_image",     # Re-generate image only
        "regenerate_both",      # Re-generate content AND image
    ]
    feedback: Optional[str]         # Content revision feedback
    image_feedback: Optional[str]   # Image revision feedback


class ContentState(TypedDict):
    # --- Orchestration ---
    run_id: str
    current_step: Annotated[str, lambda a, b: b]

    # --- Trend Research ---
    trending_topics: list[str]
    selected_topic: str
    avoid_topics: Optional[list[str]]
    topic_override: Optional[str]

    # --- Recipe ---
    recipe: Optional[RecipeData]

    # --- Content per platform ---
    instagram_content: Optional[PlatformContent]

    # --- Image ---
    image: Optional[ImageData]

    # --- Human review ---
    human_review: Annotated[HumanReview, lambda a, b: {**a, **b}]

    # --- Publishing ---
    buffer_ig_post_id: Optional[str]
    published: bool

    # --- Error handling ---
    errors: Annotated[list[str], lambda a, b: a + b]