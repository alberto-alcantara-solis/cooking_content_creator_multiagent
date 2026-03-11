"""
Simple end-to-end test to run the whole cooking content creator process.
This test validates the graph structure and flow without external dependencies.
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.builder import build_graph
from graph.state import ContentState


def mock_orchestrator_node(state: ContentState) -> ContentState:
    """Mock orchestrator node."""
    state["current_step"] = "orchestrator"
    return state


def mock_trend_node(state: ContentState) -> ContentState:
    """Mock trend agent that returns sample trending topics."""
    state["current_step"] = "trend_agent"
    state["trending_topics"] = ["Vegan Desserts", "Quick Weeknight Meals"]
    state["selected_topic"] = "Vegan Desserts"
    return state


def mock_recipe_node(state: ContentState) -> ContentState:
    """Mock recipe agent that returns a sample recipe."""
    state["current_step"] = "recipe_agent"
    state["recipe"] = {
        "title": "Chocolate Avocado Mousse",
        "description": "A creamy, rich vegan chocolate dessert that's ready in 10 minutes.",
        "ingredients": ["1 avocado", "1/2 cup cocoa powder", "1/2 cup almond milk", "2 tbsp maple syrup"],
        "steps": [
            "Blend avocado with cocoa powder",
            "Add almond milk and maple syrup",
            "Blend until smooth",
            "Serve chilled"
        ],
        "prep_time": "10 minutes",
        "difficulty": "Easy"
    }
    return state


def mock_content_node(state: ContentState) -> ContentState:
    """Mock content agent that returns Instagram content."""
    state["current_step"] = "content_agent"
    state["instagram_content"] = {
        "caption": "Try this amazing vegan chocolate mousse! 🍫✨ Ready in just 10 minutes. Perfect for dessert lovers.",
        "hashtags": ["#VeganDesserts", "#HealthyRecipes", "#QuickRecipes", "#VeganBaking"],
        "character_count": 120
    }
    return state


def mock_image_node(state: ContentState) -> ContentState:
    """Mock image agent that generates image prompt."""
    state["current_step"] = "image_agent"
    state["image"] = {
        "comfyui_prompt": "A delicious vegan chocolate mousse with fresh berries, professional food photography, warm lighting",
        "local_path": "",
        "status": "pending"
    }
    return state


def mock_publisher_node(state: ContentState) -> ContentState:
    """Mock publisher node that publishes the content."""
    state["current_step"] = "publisher"
    state["buffer_ig_post_id"] = f"post_{uuid.uuid4().hex[:8]}"
    state["published"] = True
    return state


def approve_human_review(state: ContentState) -> ContentState:
    """Auto-approve content for testing."""
    state["human_review"]["status"] = "approved"
    state["human_review"]["feedback"] = "Auto-approved for testing"
    return state


def test_end_to_end_process():
    """Test the complete content creation process from start to finish."""
    
    print("\n" + "="*60)
    print("🚀 STARTING END-TO-END TEST")
    print("="*60)
    
    # Mock the agent nodes
    with patch('graph.builder.orchestrator_node', side_effect=mock_orchestrator_node), \
         patch('graph.builder.trend_node', side_effect=mock_trend_node), \
         patch('graph.builder.recipe_node', side_effect=mock_recipe_node), \
         patch('graph.builder.content_node', side_effect=mock_content_node), \
         patch('graph.builder.image_node', side_effect=mock_image_node), \
         patch('graph.builder.publisher_node', side_effect=mock_publisher_node):
        
        # Build the graph with mocked nodes
        graph = build_graph()
        
        # Create unique thread ID
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # Initialize state
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
        
        print(f"\n✅ Graph built successfully")
        print(f"📋 Thread ID: {thread_id}")
        print(f"📝 Initial state: current_step = {initial_state['current_step']}")
        
        # First invoke — runs until human_review interrupt
        try:
            print(f"\n⏳ Running graph until human review...")
            result = graph.invoke(initial_state, config)
            print(f"✅ Graph executed successfully")
            print(f"   Current step: {result['current_step']}")
            print(f"   Selected topic: {result['selected_topic']}")
            print(f"   Recipe: {result['recipe']['title'] if result['recipe'] else 'None'}")
            print(f"   Instagram content: {bool(result['instagram_content'])}")
            print(f"   Image prompt generated: {bool(result['image']['comfyui_prompt'])}")
            
            # Verify human_review status is pending (graph should pause here)
            assert result['human_review']['status'] == 'pending', \
                "Graph should pause at human_review with pending status"
            print(f"   Human review status: {result['human_review']['status']}")
            
        except Exception as e:
            print(f"❌ Error running graph: {e}")
            raise
        
        # Now simulate human approval and continue
        print(f"\n⏳ Simulating human approval and continuing...")
        result['human_review'] = approve_human_review(result['human_review'])
        
        try:
            final_result = graph.invoke(result, config)
            print(f"✅ Graph completed after human approval")
            print(f"   Current step: {final_result['current_step']}")
            print(f"   Published: {final_result['published']}")
            print(f"   Post ID: {final_result['buffer_ig_post_id']}")
            
            # Verify final state
            assert final_result['published'] == True, "Content should be published"
            assert final_result['buffer_ig_post_id'] is not None, "Should have post ID"
            print(f"\n✅ All assertions passed!")
            
        except Exception as e:
            print(f"❌ Error continuing graph after approval: {e}")
            raise
    
    print(f"\n" + "="*60)
    print("✅ END-TO-END TEST PASSED!")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_end_to_end_process()
    print("🎉 Test completed successfully!")
