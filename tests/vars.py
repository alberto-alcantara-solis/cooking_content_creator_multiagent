TEST_STATE_1_TREND = {
    "run_id":"trend_agent_test_run_XXX",
    "current_step": "orchestration_finished",
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


TEST_STATE_1_RECIPE = {
    "run_id": "recipe_node_test_run_XXX",
    "current_step": "trend_research_complete",
    "trending_topics": ["Charli's Zero-Sugar Cheesecake", "Spring Pea Crostini", "Rhubarb Desserts", "Miso Butter Cabbage", "Nostalgic Sparkling Water", "Spring Pea Crostini with Ricotta"],
    "selected_topic": "Spring Pea Crostini with Ricotta",
    "recipe": None,
    "instagram_content": None,
    "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
    "human_review": {"status": "pending", "feedback": None},
    "buffer_ig_post_id": None,
    "published": False,
    "errors": [],
}

TEST_STATE_1_PARALLEL = {
        "run_id": "PARALLEL_test_run_XXX",
        "current_step": "recipe_generation_complete",
        "trending_topics": ["Charli's Zero-Sugar Cheesecake", "Spring Pea Crostini", "Rhubarb Desserts", "Miso Butter Cabbage", "Nostalgic Sparkling Water", "Spring Pea Crostini with Ricotta"],
        "selected_topic": "Spring Pea Crostini with Ricotta",
        "recipe": {
            "title": "Emerald Pea & Lemon Ricotta Crostini",
            "description": "Bright, creamy, and bursting with spring flavor! These vibrant crostini are an effortless appetizer perfect for entertaining or a light, fresh snack.",
            "ingredients": [
                "1 baguette (approx. 300g), sliced into 1.5 cm (½ inch) rounds",
                "60ml (¼ cup) extra virgin olive oil, plus more for drizzling",
                "1 large clove garlic, peeled, halved",
                "250g (1 cup) whole milk ricotta cheese",
                "1 lemon, zested and juiced",
                "300g (2 cups) fresh or frozen peas, defrosted if frozen",
                "30g (¼ cup) fresh mint leaves, finely chopped, plus extra for garnish",
                "½ teaspoon flaky sea salt, plus more to taste",
                "¼ teaspoon freshly ground black pepper, plus more to taste",
                "¼ teaspoon red pepper flakes, optional, for garnish"
            ],
            "steps": [
                "Preheat your oven to 190°C (375°F) and arrange the baguette slices in a single layer on a baking sheet.",
                "Brush both sides of the baguette slices generously with 30ml (2 tablespoons) of the olive oil.",
                "Toast the baguette slices in the preheated oven for 8-10 minutes, or until lightly golden and crisp.",
                "While the crostini are still warm, gently rub one side of each toasted slice with the cut side of the garlic clove.",
                "In a small bowl, combine the ricotta cheese with half of the lemon zest, 1 tablespoon of lemon juice, a pinch of salt, and a pinch of black pepper, then stir until smooth and creamy.",
                "Bring a small pot of salted water to a boil, add the peas, and cook for 1-2 minutes until bright green and tender-crisp.",
                "Drain the peas immediately and transfer them to a medium bowl.",
                "Add the remaining 30ml (2 tablespoons) of olive oil, the remaining lemon zest, 1 tablespoon of lemon juice, chopped mint, ½ teaspoon flaky sea salt, and ¼ teaspoon black pepper to the peas.",
                "Using a fork or potato masher, coarsely mash the peas until they are mostly broken down but still have some texture.",
                "To assemble, spread a generous layer of the lemon ricotta mixture onto each garlic-rubbed crostini.",
                "Spoon a dollop of the mashed pea mixture over the ricotta on each crostini.",
                "Arrange the crostini on a serving platter, drizzle with a little extra virgin olive oil, and garnish with fresh mint leaves and red pepper flakes, if desired."
            ],
            "prep_time": "25 minutes",
            "difficulty": "Easy"
        },
        "instagram_content": None,
        "image": {"status": "pending", "comfyui_prompt": "", "local_path": ""},
        "human_review": {"status": "pending", "feedback": None},
        "buffer_ig_post_id": None,
        "published": False,
        "errors": [],
    }