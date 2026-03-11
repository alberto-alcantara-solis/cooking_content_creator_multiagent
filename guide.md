# 🍳 Cooking Content Studio — Full Architecture

## Work Directory Structure

```
cooking-content-studio/
│
├── .env                          # API keys (Buffer, OpenAI/Anthropic, etc.)
├── .env.example                  # Template to commit to git (no secrets)
├── requirements.txt
├── README.md
│
├── main.py                       # Entry point — triggers the graph
│
├── graph/
│   ├── __init__.py
│   ├── builder.py                # Where the graph is assembled (nodes + edges)
│   ├── state.py                  # ContentState definition (the single source of truth)
│   └── checkpointer.py           # Persistence config for human-in-the-loop
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py           # Supervisor: decides what to create and routes
│   ├── trend_agent.py            # Searches trending recipes/topics
│   ├── recipe_agent.py           # Generates recipe, ingredients, steps
│   ├── content_agent.py          # Writes captions + hashtags per platform
│   ├── image_agent.py            # Builds ComfyUI prompt + triggers generation
│   └── publisher_agent.py        # Sends everything to Buffer API
│
├── tools/
│   ├── __init__.py
│   ├── search_tools.py           # Web search for trends (Tavily or SerpAPI)
│   ├── comfyui_tools.py          # ComfyUI REST API integration
│   └── buffer_tools.py           # Buffer API integration
│
├── prompts/
│   ├── orchestrator.py
│   ├── trend.py
│   ├── recipe.py
│   ├── content.py
│   └── image.py
│
├── ui/
│   └── review_app.py             # Streamlit app for human-in-the-loop approval
│
├── workflows/
│   └── comfyui_workflow.json     # Your exported ComfyUI workflow template
│
└── tests/
    ├── test_state.py
    ├── test_tools.py
    └── test_graph.py
```

---

## State Schema — `graph/state.py`

This is the most important file in the whole project.
Every agent reads from and writes to this shared object.

```python
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
    cuisine: str


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
    twitter_content: Optional[PlatformContent]

    # --- Image ---
    image: Optional[ImageData]

    # --- Human review ---
    human_review: HumanReview

    # --- Publishing ---
    buffer_ig_post_id: Optional[str]
    buffer_twitter_post_id: Optional[str]
    published: bool

    # --- Error handling ---
    errors: list[str]
```

---

## Graph Definition — `graph/builder.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from graph.state import ContentState
from agents.orchestrator import orchestrator_node
from agents.trend_agent import trend_node
from agents.recipe_agent import recipe_node
from agents.content_agent import content_node
from agents.image_agent import image_node
from agents.publisher_agent import publisher_node
from graph.checkpointer import get_checkpointer


def human_review_node(state: ContentState) -> ContentState:
    """
    This node does nothing by itself.
    LangGraph will interrupt HERE and wait for external input.
    The graph resumes when you call graph.invoke() again
    with updated state containing human_review.status = "approved"
    """
    return state


def route_after_review(state: ContentState) -> str:
    """Conditional edge after human review."""
    status = state["human_review"]["status"]
    if status == "approved":
        return "publisher"
    elif status == "rejected":
        return END
    elif status == "edit_requested":
        return "content_agent"   # Re-generate content with feedback
    return END


def build_graph():
    graph = StateGraph(ContentState)

    # --- Add nodes ---
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("trend_agent", trend_node)
    graph.add_node("recipe_agent", recipe_node)
    graph.add_node("content_agent", content_node)
    graph.add_node("image_agent", image_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("publisher", publisher_node)

    # --- Entry point ---
    graph.set_entry_point("orchestrator")

    # --- Edges ---
    graph.add_edge("orchestrator", "trend_agent")

    # Parallel execution: after trends, run recipe AND content prep simultaneously
    # (content_agent will refine once recipe is ready, but we can start both)
    graph.add_edge("trend_agent", "recipe_agent")
    graph.add_edge("recipe_agent", "content_agent")
    graph.add_edge("content_agent", "image_agent")
    graph.add_edge("image_agent", "human_review")

    # Conditional edge after human reviews
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "publisher": "publisher",
            "content_agent": "content_agent",   # edit loop
            END: END
        }
    )

    graph.add_edge("publisher", END)

    # Checkpointer enables interrupt + persistence
    checkpointer = get_checkpointer()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]   # <-- THIS is the magic line
    )
```

---

## Checkpointer — `graph/checkpointer.py`

```python
from langgraph.checkpoint.sqlite import SqliteSaver

def get_checkpointer():
    """
    SQLite checkpointer: saves full graph state to a local DB file.
    This is what makes interrupt() work — state survives between runs.
    For production you'd swap this for PostgresSaver.
    """
    return SqliteSaver.from_conn_string("checkpoints.db")
```

---

## Entry Point — `main.py`

```python
import uuid
from graph.builder import build_graph
from graph.state import ContentState

def run():
    graph = build_graph()

    # Each run needs a unique thread_id so the checkpointer
    # knows which conversation/state to load
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: ContentState = {
        "run_id": thread_id,
        "current_step": "start",
        "trending_topics": [],
        "selected_topic": "",
        "recipe": None,
        "instagram_content": None,
        "twitter_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "buffer_twitter_post_id": None,
        "published": False,
        "errors": []
    }

    print(f"🚀 Starting run: {thread_id}")
    print("=" * 50)

    # First invoke — runs until interrupt_before=["human_review"]
    result = graph.invoke(initial_state, config)

    print("\n⏸️  Graph paused for human review.")
    print(f"Thread ID saved: {thread_id}")
    print("Open the Streamlit UI to review and approve.")
    print(f"\n👉 Run: streamlit run ui/review_app.py -- --thread_id {thread_id}")

if __name__ == "__main__":
    run()
```

---

## Human Review UI — `ui/review_app.py`

```python
import streamlit as st
import sys
from graph.builder import build_graph

def main():
    thread_id = sys.argv[-1]  # passed from terminal
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_graph()

    # Load current state from checkpointer
    state = graph.get_state(config).values

    st.title("🍳 Content Studio — Review")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📸 Generated Image")
        if state["image"]["local_path"]:
            st.image(state["image"]["local_path"])

        st.subheader("🍽️ Recipe")
        recipe = state["recipe"]
        st.write(f"**{recipe['title']}**")
        st.write(recipe["description"])

    with col2:
        st.subheader("📱 Instagram")
        st.text_area("Caption", state["instagram_content"]["caption"], height=150)
        st.write("Hashtags:", " ".join(state["instagram_content"]["hashtags"]))

        st.subheader("🐦 Twitter")
        st.text_area("Tweet", state["twitter_content"]["caption"], height=100)

    st.divider()

    feedback = st.text_area("Feedback (optional — for edit requests)")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("✅ Approve & Publish", type="primary"):
            graph.update_state(
                config,
                {"human_review": {"status": "approved", "feedback": None}}
            )
            graph.invoke(None, config)  # Resume graph
            st.success("Published! 🎉")

    with col_b:
        if st.button("✏️ Request Edits"):
            graph.update_state(
                config,
                {"human_review": {"status": "edit_requested", "feedback": feedback}}
            )
            graph.invoke(None, config)
            st.info("Regenerating content...")

    with col_c:
        if st.button("❌ Reject"):
            graph.update_state(
                config,
                {"human_review": {"status": "rejected", "feedback": None}}
            )
            st.warning("Run rejected.")

if __name__ == "__main__":
    main()
```

---

## Step-by-Step Execution Flow (Full Run)

```
Terminal 1:                           Your screen:
──────────────────────────────────────────────────────────────
$ python main.py
                                      🚀 Starting run: abc-123
                                      [orchestrator] Deciding topic...
                                      [trend_agent] Searching trends...
                                      [recipe_agent] Generating recipe...
                                      [content_agent] Writing captions...
                                      [image_agent] Calling ComfyUI...
                                      ✅ Image ready: outputs/abc-123.png
                                      ⏸️  Graph paused for human review.
                                      👉 Run: streamlit run ui/review_app.py -- --thread_id abc-123

Terminal 2:
──────────────────────────────────────────────────────────────
$ streamlit run ui/review_app.py -- --thread_id abc-123
                                      [Browser opens with review UI]
                                      You see: image + captions + recipe
                                      You click: ✅ Approve & Publish

                                      [Graph resumes]
                                      [publisher_agent] Sending to Buffer...
                                      ✅ Published to Instagram + Twitter!
```

---

## Build Order (Phase by Phase)

### Phase 1 — Get the skeleton running (Week 1-2)
- [ ] Set up repo, venv, install `langgraph`, `langchain`, `python-dotenv`
- [ ] Define `ContentState` in `state.py`
- [ ] Build a minimal graph: orchestrator → recipe_agent → END (hardcoded outputs, no real LLM yet)
- [ ] Confirm state flows correctly between nodes
- [ ] Add SQLite checkpointer + `interrupt_before` — verify the graph actually pauses

### Phase 2 — Real LLM agents (Week 3-4)
- [ ] Wire in OpenAI/Anthropic API
- [ ] Build `trend_agent` with Tavily search tool
- [ ] Build `recipe_agent` with structured output (force JSON with Pydantic)
- [ ] Build `content_agent` with platform-specific prompts
- [ ] Write prompts in `prompts/` folder

### Phase 3 — ComfyUI integration (Week 5)
- [ ] Export your best food workflow from ComfyUI as JSON
- [ ] Build `comfyui_tools.py`: POST workflow → poll → download image
- [ ] Wire into `image_agent`
- [ ] Test end-to-end: text in → image file out

### Phase 4 — Human review UI (Week 6)
- [ ] Build Streamlit review app
- [ ] Test `graph.update_state()` + resume flow
- [ ] Test the edit loop (request edits → content_agent regenerates → back to review)

### Phase 5 — Buffer publishing (Week 7)
- [ ] Create Buffer account, connect IG + Twitter
- [ ] Build `buffer_tools.py`
- [ ] Test with a real post
- [ ] Add error handling + retry logic

### Phase 6 — Polish (Week 8-12)
- [ ] Add a scheduler (APScheduler or cron) to auto-trigger daily
- [ ] Add logging throughout
- [ ] Write README with architecture diagram
- [ ] Record a demo video for your portfolio

---

## Key Dependencies

```txt
# requirements.txt
langgraph>=0.2.0
langchain>=0.2.0
langchain-openai>=0.1.0       # or langchain-anthropic
langchain-community>=0.2.0
tavily-python                  # web search for trends
requests                       # ComfyUI + Buffer API calls
streamlit                      # review UI
python-dotenv
pydantic>=2.0
```
