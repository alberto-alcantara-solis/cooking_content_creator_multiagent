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