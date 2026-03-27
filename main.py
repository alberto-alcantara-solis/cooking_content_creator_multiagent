import uuid
import logging
from graph.builder import build_graph
from graph.state import ContentState

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to INFO for less verbose, DEBUG for detailed state logs
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("main")

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

    logger.info(f"🚀 Starting run: {thread_id}")
    logger.info("=" * 50)

    # First invoke — runs until interrupt_before=["human_review"]
    result = graph.invoke(initial_state, config)

    logger.info("\n⏸️  Graph paused for human review.")
    logger.info(f"Thread ID saved: {thread_id}")
    logger.info("Open the Streamlit UI to review and approve.")
    logger.info(f"\n👉 Run: streamlit run ui/human_approval_app.py -- --thread_id {thread_id}")

if __name__ == "__main__":
    run()