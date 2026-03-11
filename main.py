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
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
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