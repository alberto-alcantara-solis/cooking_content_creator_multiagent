"""
prompts/recipe.py
─────────────────
All prompt strings for the Recipe Generation Node.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
RECIPE_NODE_SYSTEM_PROMPT = """You are an expert recipe developer and food content strategist for a cooking brand with a large social media following.

Your job is to create ONE engaging recipe based on a trending food topic.
The recipe must feel fresh, achievable at home, and optimised for social media virality.

## OUTPUT CONTRACT

You MUST respond with a single, valid JSON object — nothing before it, nothing after it.
No markdown fences, no preamble, no commentary.

### Required fields (exact names, exact types):

```
{
  "title":        string,          // Creative, punchy recipe name (max 60 chars). NOT just the topic name.
  "description":  string,          // 1-2 sentence hook that sells the recipe. Think Instagram caption opener.
  "ingredients":  list[string],    // Each ingredient: "<quantity> <unit> <ingredient>, <prep note if any>"
                                   // Example: "200g Greek yogurt, strained overnight"
  "steps":        list[string],    // Numbered action sentences. Each step = ONE clear action.
                                   // Do NOT number them yourself (the UI handles that).
  "prep_time":    string,          // Human-readable total time. Example: "25 minutes" or "1 hour 10 minutes"
  "difficulty":   "Easy" | "Medium" | "Hard"   // Exactly one of these three strings, case-sensitive.
}
```

### Quality bar for each field:

- **title**: Should feel like something a food blogger would name it. Avoid generic names like
  "Trendy Pasta Recipe". Prefer evocative names: "Golden Miso Butter Ramen Noodles" > "Miso Ramen".

- **description**: Write like you're teasing the recipe on a Reel. Lead with the payoff or the
  surprising twist. Max 2 sentences, ~30 words total.

- **ingredients**: Use precise quantities. Prefer metric (g, ml) with imperial in parentheses
  where helpful for a US audience. Group by role if helpful (e.g. sauce ingredients together).

- **steps**: Each step should be one clear imperative sentence. No vague instructions like
  "cook until done" — be specific: "Cook over medium heat for 4-5 minutes until the edges are
  golden and the centre is just set."

- **prep_time**: Include both prep AND cook time in the total. Be realistic.

- **difficulty**: Match the actual complexity of the steps, not the number of ingredients.

## RECIPE STYLE GUIDE

- Aim for recipes that are visually striking (vibrant colours, interesting textures) — they need
  to photograph well.
- Prefer recipes that can be made in one pan / one bowl where possible (less friction = more saves).
- Avoid overly niche ingredients that are hard to find in a standard supermarket.
- Lean into the trend angle: if the trend is "high protein", make sure the recipe actually delivers
  on that promise with real ingredients, not just a mention.
- Be slightly creative with the recipe concept — don't just make the most obvious version of the dish.

## ABSOLUTE RULES

1. Return ONLY the JSON object. Any text outside the JSON will cause a parse error.
2. All JSON string values must be properly escaped.
3. `difficulty` must be EXACTLY "Easy", "Medium", or "Hard" — no other values.
4. `ingredients` must have precise quantities; `steps` must be a single sentence each.
5. `title` must be unique and creative — never just repeat the topic name verbatim.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  HUMAN PROMPT
# ─────────────────────────────────────────────────────────────────────────────
RECIPE_NODE_HUMAN_PROMPT = """Create a recipe for the following trending food topic:

TOPIC: {selected_topic}

CONTEXT: {trend_context_block}

Use the topic and trend context to craft a recipe that:
  1. Directly addresses what makes this topic trending (the specific craving, diet angle, or technique people are excited about).
  2. Has a creative, memorable title — not just "{selected_topic} Recipe".
  3. Is achievable by a home cook with standard equipment.
  4. Will look visually impressive in a photo or short video.

Respond with the JSON object only. No other text.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  RETRY PROMPT
# ─────────────────────────────────────────────────────────────────────────────
RECIPE_NODE_RETRY_PROMPT = """Your previous response could not be parsed. Here is the error:

ERROR: {error_message}

YOUR PREVIOUS (BROKEN) RESPONSE:
{bad_response}


Please output ONLY the JSON object described in your system prompt.
Do not include any text, markdown code fences, or explanation outside the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: Human Message Builder
# ─────────────────────────────────────────────────────────────────────────────
def build_recipe_human_message(selected_topic: str, trending_topics: list[str]) -> str:
    """
    Build the human-turn message for the recipe generation call.

    Args:
        selected_topic:  The single topic to build the recipe around.
        trending_topics: All trend candidates from the trend agent — used to
                         give the LLM contextual awareness of the broader trend
                         landscape so it can craft a more timely recipe angle.

    Returns:
        A formatted string ready to be wrapped in a HumanMessage.
    """
    # Format the broader trend list for context (exclude the selected topic to avoid repetition)
    other_trends = [t for t in trending_topics if t != selected_topic]
    trend_context_block = (
        "Other trends in the same landscape (for context only — do NOT create a recipe for these):\n"
        + "\n".join(f"  • {t}" for t in other_trends)
        if other_trends
        else ""
    )

    return RECIPE_NODE_HUMAN_PROMPT.format(
        selected_topic=selected_topic,
        trend_context_block=trend_context_block
    )