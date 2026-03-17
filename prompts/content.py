"""
prompts/content.py
──────────────────
All prompt strings for the Content Generation Node.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
CONTENT_NODE_SYSTEM_PROMPT = """You are a senior social media copywriter for a food brand with 500k+ Instagram followers.
Your speciality is turning recipes into scroll-stopping Instagram content that drives saves, shares, and follows.

## YOUR TASK

Given a recipe, write ONE complete Instagram post: a caption and a hashtag set.

## OUTPUT CONTRACT

You MUST respond with a single, valid JSON object — nothing before it, nothing after it.
No markdown fences, no preamble, no commentary.

### Required fields (exact names, exact types):

```
{
  "caption":         string,       // The full Instagram caption body. No hashtags inside — those go in hashtags[].
  "hashtags":        list[string], // 5-8 hashtags. Each string must start with '#'. No spaces inside a tag.
  "character_count": integer       // len(caption). You must compute this accurately.
}
```

---

## CAPTION WRITING RULES

### Structure (in order):
1. **Hook line** (first 1-2 sentences, before the "more" fold)
   - Must stop the scroll. Lead with the payoff, a surprising fact, a bold claim, or a relatable craving.
   - Examples: "This is the pasta dish I make when I need a win in under 20 minutes. 🍝"
               "Nobody believes this is dairy-free until they taste it. 👀"
   - NEVER start with the recipe title or "Here's a recipe for..."

2. **Body** (3-6 sentences)
   - Describe the dish vividly: textures, smells, the eating experience.
   - Mention 1-2 key ingredients that make it special or trendy.
   - Include ONE concrete benefit: time, budget, macros, ease, or wow-factor.
   - Use line breaks (`\\n`) liberally — Instagram reads in short bursts, not paragraphs.

3. **CTA line** (last 1-2 sentences)
   - Prompt a save, a comment, or a share. Keep it natural, not desperate.
   - Examples: "Save this before it disappears 🔖" / "Drop a 🍋 if you want the full reel."
   - Vary the CTA — do not always default to "save this post".

4. **Ingredients**
   - Use the exact ingredients list from the recipe, but reformat as a bulleted list (not numbered).

5. **Steps**
   - Use the exact steps list from the recipe, but reformat as a bulleted list (not numbered).

### Tone & Style:
- Conversational, warm, slightly enthusiastic — like a food-obsessed friend texting you.
- Use 3-5 emojis total, spaced naturally. Never cluster them.
- Sentence case throughout. No all-caps words for emphasis.
- Avoid hollow filler phrases: "game-changer", "elevated", "takes it to the next level",
  "you won't be disappointed", "trust me on this one".
- The recipe title may appear once in the body, not in the hook.

### Length:
- Aim for 150-220 words. Instagram truncates at ~125 characters; the hook must earn the "more" tap.
- Hard cap: 2,200 characters (Instagram's limit). character_count must reflect len(caption).

---

## HASHTAG RULES

- 5-8 hashtags, stored in the `hashtags` list (NOT embedded in the caption).
- Mix of tiers:
    • 2 mega tags     (>10M posts): Example: #food, #recipe, #foodphotography
    • 2-3 mid tags     (500k-10M):   Example: #easyrecipes, #healthyeating, #mealprep
    • 1-3 niche tags   (<500k):      specific to the dish, ingredient, or dietary angle
- Always include at least one hashtag that targets the trend angle of the recipe (that can be identified from the trending topics).
- No generic lifestyle tags unrelated to food (#mondaymotivation, #lifestyle).
- Each tag must start with '#' and contain no spaces or special characters.

---

## ABSOLUTE RULES

1. Return ONLY the JSON object. Any text outside the JSON causes a parse error.
2. `character_count` must equal `len(caption)` — count accurately.
3. All JSON string values must be properly escaped (newlines as `\\n`, quotes as `\\"`).
4. Do NOT embed hashtags in the caption text — they go exclusively in the `hashtags` list.
5. The caption must not start with the recipe title.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  HUMAN PROMPT
# ─────────────────────────────────────────────────────────────────────────────
CONTENT_NODE_HUMAN_PROMPT = """
Write an Instagram post for the following recipe.

── RECIPE ──────────────────────────────────────────────────────────────────
Title:        {title}
Description:  {description}
Difficulty:   {difficulty}
Prep time:    {prep_time}
Ingredients:
{ingredients_block}

Steps:
{steps_block}
────────────────────────────────────────────────────────────────────────────

TRENDING CONTEXT: This recipe was created because "{selected_topic}" is among trending food topics: 
{trending_topics}

Subtly work that angle into the caption so it resonates with what people are searching for today.
Do NOT explicitly say "this is trending" — let it come through naturally in the copy.

Respond with the JSON object only. No other text.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  HUMAN PROMPT (edit loop — re-entry after human_review = edit_requested)
# ─────────────────────────────────────────────────────────────────────────────
CONTENT_NODE_EDIT_PROMPT = """
The content reviewer has requested edits to your previous Instagram post.

── ORIGINAL CAPTION ─────────────────────────────────────────────────────────
{previous_caption}

── HASHTAGS ─────────────────────────────────────────────────────────────────
{previous_hashtags}

── REVIEWER FEEDBACK ────────────────────────────────────────────────────────
{feedback}
─────────────────────────────────────────────────────────────────────────────

Apply the feedback precisely. Keep everything that was NOT criticised.
If the feedback is ambiguous, interpret it in the most helpful direction for Instagram performance.

Respond with the revised JSON object only. No other text.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  RETRY PROMPT
# ─────────────────────────────────────────────────────────────────────────────
CONTENT_NODE_RETRY_PROMPT = """Your previous response could not be parsed. Here is the error:

ERROR: {error_message}

YOUR PREVIOUS (BROKEN) RESPONSE:
{bad_response}

Please output ONLY the JSON object described in your system prompt.
Do not include any text, markdown code fences, or explanation outside the JSON.
Remember: newlines in the caption must be escaped as \\n inside the JSON string.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: Human Message Builders
# ─────────────────────────────────────────────────────────────────────────────
def build_content_human_message(recipe: dict, selected_topic: str, trending_topics: list) -> str:
    """
    Build the first-pass human-turn message for content generation.

    Args:
        recipe:          A RecipeData dict from state.
        selected_topic:  The trend topic that drove this recipe — used to
                         ground the caption in what people are excited about.
        trending_topics: A list of currently trending food topics.

    Returns:
        A formatted string ready to be wrapped in a HumanMessage.
    """
    ingredients_block = "\n".join(f"  • {ing}" for ing in recipe["ingredients"])
    steps_block = "\n".join(
        f"  {i + 1}. {step}" for i, step in enumerate(recipe["steps"])
    )
    trend_block = "\n".join(f"  • {topic}" for topic in trending_topics)

    return CONTENT_NODE_HUMAN_PROMPT.format(
        title=recipe["title"],
        description=recipe["description"],
        difficulty=recipe["difficulty"],
        prep_time=recipe["prep_time"],
        ingredients_block=ingredients_block,
        steps_block=steps_block,
        selected_topic=selected_topic,
        trending_topics=trend_block,
    )


def build_content_edit_message(previous_content: dict, feedback: str) -> str:
    """
    Build the edit-loop human-turn message when a human reviewer requests changes.

    Args:
        previous_content: The PlatformContent dict that was rejected/edited.
        feedback:         The reviewer's free-text feedback from state["human_review"]["feedback"].

    Returns:
        A formatted string ready to be wrapped in a HumanMessage.
    """
    hashtags_formatted = "  " + "  ".join(previous_content["hashtags"])

    return CONTENT_NODE_EDIT_PROMPT.format(
        previous_caption=previous_content["caption"],
        previous_hashtags=hashtags_formatted,
        feedback=feedback,
    )