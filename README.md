# cooking_content_creator_multiagent
A cooking related content creator multiagent

## Done:
- ✅Define ContentState
- ✅Build graph structure
- ✅Verify interrupt_before
- ✅Build Trend Agent
- ✅Test Trend Agent
- ✅Build Recipe node
- ✅Test Recipe node
- ✅Build Content node
- ✅Test Content node
- ✅Build Image Agent
- ✅Test Image Agent

## In process:
- ⌨️Build Publisher Agent
- ⌨️Test Publisher Agent

## Next steps:
- 🔜Build Orchestrator Agent
- 🔜Test Orchestrator Agent
- 🔜Test full workflow (with working human review)
- 🔜Polish + final touches
- 🔜Clean README of the hole project

## Future improvements:
- ✨Error Agent


### How to make it work (Windows)
```
python3.11 -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
```

Load .env variables (In powershell):
```
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}
```

## How the Workflow Works

Dive into the heart of our cooking content creation multiagent system! This workflow automates the entire process of discovering trends, crafting recipes, generating engaging content, and producing stunning visuals—all with human oversight for quality control. 

**Note:** The following explanation is based on a specific test execution (run ID: 7ffb07e9-bdcd-492d-92f8-5e7d004e66c3) to demonstrate how the current system operates. Actual runs may vary based on trending topics and AI responses.

### 📊 **Workflow Diagram**

![Human Approval App Screenshot](images/Workflow_Diagram.png)

### 🚀 **Step 1: Trend Discovery**
The **Trend Agent** kicks things off by researching the latest food trends. It leverages:
- **Gemini AI** for intelligent analysis of current culinary buzz
- **Tavily Search** to scour the web for trending topics across food blogs, TikTok, Instagram, and news sources

From a curated list of 5 trending topics (e.g., "Lemony Asparagus One-Pot Pasta", "Viral Doner Kebabs", etc.), it selects the most promising one based on factors like seasonal relevance, home-cook friendliness, and visual appeal. In our example run, it chose **"Lemony Asparagus One-Pot Pasta"** with a high trend score of 8.8.

### 👩‍🍳 **Step 2: Recipe Creation**
The **Recipe Node** takes the selected trend and generates a complete, detailed recipe. Using Gemini AI, it creates:
- A catchy title and engaging description
- Full ingredient list with measurements
- Step-by-step cooking instructions
- Prep time and difficulty level

The system includes retry logic to handle JSON parsing issues or content quality checks. In our run, it produced **"Zesty Spring Asparagus One-Pot Pasta"** – an easy, 25-minute recipe featuring fresh asparagus, lemon, and Parmesan in a creamy one-pot wonder.

### ⚡ **Step 3: Parallel Content Generation**
Once the recipe is ready, two agents work simultaneously to create the final content:

#### 📱 **Content Node (Instagram Caption)**
- Crafts an engaging Instagram caption that tells the recipe story
- Includes the full ingredient list and instructions
- Adds relevant hashtags (#food, #recipe, #onepotpasta, etc.)
- Ensures the caption stays under Instagram's 2,200 character limit
- Handles retries for length violations or formatting issues

#### 📸 **Image Agent (Visual Creation)**
- Generates a detailed prompt for AI image generation
- Submits the prompt to **ComfyUI** (a local AI image generation server running on port 8188)
- Waits for image generation (typically 15-30 seconds)
- Uses **Gemini Vision** to critique the generated image on criteria like appetizing appearance, lighting, composition, sharpness, plating, and social media fit
- Provides scores and feedback for potential improvements

In our example, the image achieved a solid 8.4/10 score, with excellent lighting and composition but a note about asparagus vibrancy.

### 👀 **Step 4: Human Review & Approval**
This is where human creativity meets AI efficiency! The workflow **pauses automatically** and launches a **Streamlit web app** for review.

The review interface displays:
- **Recipe details** (title, description)
- **Instagram caption** with character count and hashtags
- **Generated image** preview
- **Feedback fields** for content and image suggestions

**Action options:**
- ✅ **Approve & Publish**: Send to the publisher agent (coming soon!)
- ✏️ **Edit Content**: Regenerate caption with specific feedback
- 🖼️ **Regenerate Image**: Create a new image with improvement notes
- 🔄 **Regenerate Both**: Update both content and image in parallel
- ❌ **Reject**: End the workflow

This human-in-the-loop approach ensures every piece of content meets your standards before going live.

#### 📸 **Human Approval App Screenshot**
Here's how the review interface looked during our test execution:

![Human Approval App Screenshot](images/Content%20Studio%20—%20Review.jpg)

### 📤 **Step 5: Publishing (In Development)**
Once approved, the **Publisher Agent** will handle:
- Posting to Instagram via Buffer API
- Scheduling optimal posting times
- Tracking engagement metrics

### 🔄 **Error Handling & Retries**
Throughout the process, the system includes robust error handling:
- API rate limit management (with automatic retries)
- JSON parsing validation with fallbacks
- Content quality checks (character limits, formatting)
- Image critique and regeneration loops

### 🛠️ **Technical Architecture**
- Built with **LangGraph** for orchestrating the multiagent workflow
- Uses **SQLite checkpointer** for persistence and resumability
- **Interrupt-before** mechanism for human review pauses
- Parallel execution for content and image generation
- Modular node design for easy extension

### 📊 **Example Run Summary**
In our test execution:
- **Runtime**: ~2 minutes from start to human review
- **Selected Topic**: Lemony Asparagus One-Pot Pasta
- **Recipe**: Zesty Spring Asparagus One-Pot Pasta (Easy, 25 min)
- **Caption**: 1,844 characters with 5 hashtags
- **Image**: Generated in ~18 seconds, scored 8.4/10
- **Status**: Paused for human approval

The workflow demonstrates how AI can handle the heavy lifting of research, creation, and generation while keeping the human touch for final quality control and creative direction.

Ready to cook up some viral content? Run `python main.py` and watch the magic happen! 🍳✨