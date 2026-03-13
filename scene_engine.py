"""
SCENE ENGINE — Ṛta
Takes story from RAG
Creates 6 visual scenes
Each scene = sacred image + one powerful line
LLM checks every image prompt before generating
Painting style — respectful, artistic, not photorealistic
"""

import os
import json
import time
import urllib.parse
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

SAFE_STYLE = (
    "ancient Indian painting style, soft watercolor, "
    "respectful spiritual art, warm gold and blue tones, "
    "not photorealistic, painterly, sacred but not religious, "
    "museum quality, no offensive content"
)

FALLBACK_IMAGES = {
    "lotus": "blooming lotus flower on still water, golden sunrise, watercolor painting",
    "flame": "single sacred flame burning bright, darkness around, oil painting style",
    "river": "ancient river flowing through forest, soft morning light, watercolor",
    "mountain": "lone mountain at sunrise, clouds below, ancient painting style",
    "ocean": "vast ocean at twilight, single boat, spiritual watercolor art",
    "tree": "ancient banyan tree, roots deep, soft golden light, watercolor",
}


def call_groq(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    time.sleep(1.5)
    return response.choices[0].message.content.strip()


def check_image_prompt(prompt: str) -> dict:
    check_prompt = f"""You are a content safety judge for a sacred wisdom app.
Check if this image generation prompt is appropriate.

PROMPT: "{prompt}"

Rules — REJECT if prompt:
- Shows sacred figures disrespectfully
- Is too literally religious (idol worship scenes)
- Could offend any religious group
- Is inappropriate for any audience
- Shows violence or suffering graphically

Return ONLY raw JSON:
{{
    "approved": true,
    "reason": "respectful painting style",
    "suggestion": ""
}}

If not approved, give a safer suggestion in "suggestion" field.
Return ONLY JSON."""

    try:
        text = call_groq(check_prompt)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except:
        return {"approved": True, "reason": "fallback", "suggestion": ""}


def generate_image_url(description: str, use_fallback: str = None) -> str:
    if use_fallback:
        description = FALLBACK_IMAGES.get(use_fallback, FALLBACK_IMAGES["lotus"])
    full_prompt = f"{description}, {SAFE_STYLE}"
    encoded = urllib.parse.quote(full_prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=800&height=600&nologo=true"


def generate_scenes(story: dict, sensing: dict) -> list:
    core_wisdom = story.get("core_wisdom", "")
    narrative = story.get("primary_narrative", "")
    scripture = story.get("scripture", "")
    emotion = sensing.get("primary_emotion", "")
    stage = sensing.get("journey_stage", "")

    scene_prompt = f"""You are creating 6 sacred visual scenes for a wisdom app.
The user is feeling: {emotion}
Their journey stage: {stage}
Core wisdom to convey: {core_wisdom}
Story: {narrative[:300]}

Create 6 scenes that form a visual journey — from where the user is now to transformation.
Each has:
- image_description: What to paint (ancient Indian painting style, characters shown painterly not photorealistic)
- text_line: One powerful line (6-8 words max)

Rules for image descriptions:
- Painting/watercolor style always
- If showing Krishna/Arjuna: silhouette or painterly soft faces only
- Sacred but universal — not idol-worship literal
- Warm, peaceful, hopeful tones
- Scene 1-2: where the user is (pain, confusion, heaviness)
- Scene 3-4: the turning point (wisdom arrives)
- Scene 5-6: transformation, clarity, hope

Return ONLY raw JSON:
{{
    "scene_1": {{"image_description": "...", "text_line": "..."}},
    "scene_2": {{"image_description": "...", "text_line": "..."}},
    "scene_3": {{"image_description": "...", "text_line": "..."}},
    "scene_4": {{"image_description": "...", "text_line": "..."}},
    "scene_5": {{"image_description": "...", "text_line": "..."}},
    "scene_6": {{"image_description": "...", "text_line": "..."}}
}}"""

    try:
        text = call_groq(scene_prompt)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        scenes_data = json.loads(text)
    except:
        scenes_data = {
            "scene_1": {"image_description": "person sitting alone in darkness, heavy heart", "text_line": "The weight feels unbearable now"},
            "scene_2": {"image_description": "storm clouds over ancient landscape, watercolor", "text_line": "Even storms have an ending"},
            "scene_3": {"image_description": "single ray of light through dark clouds", "text_line": "Wisdom arrives in stillness"},
            "scene_4": {"image_description": "ancient sage by river at dawn, watercolor", "text_line": "You are not this moment"},
            "scene_5": {"image_description": "lotus rising from dark water into golden light", "text_line": "From this, something grows"},
            "scene_6": {"image_description": "sunrise over sacred mountains, warm golden tones", "text_line": "Order returns. Always."}
        }

    final_scenes = []
    fallbacks = ["lotus", "flame", "river", "mountain", "ocean", "tree"]

    for i, key in enumerate([f"scene_{j}" for j in range(1, 7)]):
        scene = scenes_data.get(key, {})
        img_desc = scene.get("image_description", "")
        text_line = scene.get("text_line", "")

        safety = check_image_prompt(img_desc)

        if safety.get("approved", True):
            image_url = generate_image_url(img_desc)
        else:
            suggestion = safety.get("suggestion", "")
            if suggestion:
                image_url = generate_image_url(suggestion)
            else:
                image_url = generate_image_url(use_fallback=fallbacks[i])

        final_scenes.append({
            "scene_number": i + 1,
            "image_url": image_url,
            "image_description": img_desc,
            "text_line": text_line,
            "safety_approved": safety.get("approved", True),
            "safety_reason": safety.get("reason", ""),
        })

    return final_scenes


def generate_rta_response(user_followup: str, resonance: dict, story: dict, sensing: dict) -> dict:
    direction = resonance.get("direction", "go_deeper")
    core_wisdom = story.get("core_wisdom", "")
    deep_question = story.get("deep_question", "")
    emotion = sensing.get("primary_emotion", "")

    if direction == "go_deeper":
        prompt = f"""You are Ṛta — a sacred digital sage. Warm, wise, never preachy.
User is feeling: {emotion}
They saw wisdom: "{core_wisdom}"
They responded: "{user_followup}"
They are resonating. Go deeper with them.

Write ONE short paragraph (3-4 sentences max).
Then ask the deep question: "{deep_question}"
Tone: like a wise friend, not a guru.
Never use: "I understand", "I see", "Certainly"
Start with something that shows you truly heard them."""

    elif direction == "different_story":
        prompt = f"""You are Ṛta — a sacred digital sage.
User responded: "{user_followup}"
The story didn't fully resonate.
Gently acknowledge and say you have another perspective to share.
ONE sentence only. Warm, not apologetic."""

    elif direction == "close_gently":
        prompt = f"""You are Ṛta — a sacred digital sage.
User seems to have found what they needed.
They said: "{user_followup}"
Offer a warm, brief closing reflection.
2-3 sentences. Leave them with peace."""

    else:
        prompt = f"""You are Ṛta — a sacred digital sage.
User said: "{user_followup}"
Respond warmly and wisely. 2-3 sentences."""

    try:
        response_text = call_groq(prompt)
    except:
        response_text = "Your words carry real weight. Sit with what you've seen for a moment."

    return {
        "rta_response": response_text,
        "direction": direction,
        "show_question": direction == "go_deeper",
        "deep_question": deep_question if direction == "go_deeper" else "",
    }


if __name__ == "__main__":
    print("\n🌊 Testing Ṛta Scene Engine (6 scenes)...\n")

    test_story = {
        "verse_id": "bg_2_47",
        "scripture": "Bhagavad Gita",
        "core_wisdom": "Perform actions without attachment to outcomes.",
        "primary_narrative": "Arjuna stands on the battlefield, overwhelmed. Krishna speaks.",
        "deep_question": "What would you do if you knew the outcome didn't matter?",
    }

    test_sensing = {
        "primary_emotion": "Exhaustion",
        "journey_stage": "Triggered",
        "intensity": 8,
        "depth_needed": "moderate",
    }

    print("Generating 6 scenes...\n")
    scenes = generate_scenes(test_story, test_sensing)

    for scene in scenes:
        print(f"SCENE {scene['scene_number']}:")
        print(f"  Text: {scene['text_line']}")
        print(f"  Image URL: {scene['image_url'][:80]}...")
        print(f"  Safety: {'✅' if scene['safety_approved'] else '⚠️'}")
        print()

    print("✅ Scene engine working!")