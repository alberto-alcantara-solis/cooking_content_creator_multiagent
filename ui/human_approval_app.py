import os
import sys
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from graph.builder import build_graph


def main():
    thread_id = sys.argv[-1]  # passed from terminal
    config    = {"configurable": {"thread_id": thread_id}}
    graph     = build_graph()

    # Load current state from checkpointer
    state = graph.get_state(config).values

    st.set_page_config(page_title="Content Studio — Review", layout="wide")
    st.title("🍳 Content Studio — Review")

    # ── Preview row ──────────────────────────────────────────────────────────
    st.header("🍽️ Recipe")
    recipe = state.get("recipe", {})
    if recipe:
        st.write(f"**{recipe['title']}**")
        st.write(recipe["description"])
    st.divider()

    col1, col2 = st.columns(2)
    with col1:

        st.subheader("📱 Instagram Caption")
        ig = state.get("instagram_content")
        st.text_area(
            "Caption",
            value=ig["caption"] if ig else "No caption found. Recomend action: regenerating content.",
            height=220,
            disabled=True,
        )
        if ig:
            st.write("**Hashtags:** " + " ".join(ig["hashtags"]))

    with col2:
        st.subheader("📸 Generated Image")
        image = state.get("image", {})
        if image and image.get("local_path"):
            st.image(image["local_path"])
        else:
            st.info("No image found. Recomended action: regenerating image.")

    st.divider()

    # ── Feedback fields ──────────────────────────────────────────────────────
    st.subheader("💬 Feedback")

    fb_col1, fb_col2 = st.columns(2)

    with fb_col1:
        content_feedback = st.text_area(
            "✏️ Content feedback",
            placeholder="e.g. Make the hook punchier, reduce hashtag count…",
            height=110,
        )

    with fb_col2:
        image_feedback = st.text_area(
            "🖼️ Image feedback",
            placeholder="e.g. Too dark, switch to overhead angle, add fresh herbs…",
            height=110,
        )

    st.divider()

    # ── Action buttons ───────────────────────────────────────────────────────
    st.subheader("🚦 Actions")
    btn_cols = st.columns(5)

    # Helper — update state and resume graph
    def _update_and_resume(review_patch: dict):
        graph.update_state(config, {"human_review": review_patch})
        graph.invoke(None, config)

    with btn_cols[0]:
        if st.button("✅ Approve & Publish", type="primary", use_container_width=True):
            _update_and_resume({"status": "approved", "feedback": None, "image_feedback": None})
            st.success("Published! 🎉")

    with btn_cols[1]:
        if st.button("✏️ Edit Content", use_container_width=True):
            if not content_feedback.strip():
                st.warning("Please enter content feedback before requesting an edit.")
            else:
                _update_and_resume({
                    "status":         "edit_requested",
                    "feedback":       content_feedback.strip(),
                    "image_feedback": None,
                })
                st.info("Regenerating caption…")

    with btn_cols[2]:
        if st.button("🖼️ Regenerate Image", use_container_width=True):
            if not image_feedback.strip():
                st.warning("Please enter image feedback before requesting a regeneration.")
            else:
                _update_and_resume({
                    "status":         "regenerate_image",
                    "feedback":       None,
                    "image_feedback": image_feedback.strip(),
                })
                st.info("Regenerating image…")

    with btn_cols[3]:
        if st.button("🔄 Regenerate Both", use_container_width=True):
            if not content_feedback.strip() and not image_feedback.strip():
                st.warning("Please enter at least one feedback field.")
            else:
                _update_and_resume({
                    "status":         "regenerate_both",
                    "feedback":       content_feedback.strip() or None,
                    "image_feedback": image_feedback.strip() or None,
                })
                st.info("Regenerating content and image in parallel…")

    with btn_cols[4]:
        if st.button("❌ Reject", use_container_width=True):
            graph.update_state(
                config,
                {"human_review": {"status": "rejected", "feedback": None, "image_feedback": None}}
            )
            st.warning("Run rejected.")


if __name__ == "__main__":
    main()