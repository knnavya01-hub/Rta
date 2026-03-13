"""
SENSING ENGINE — Ṛta
Detects emotion, intensity, journey stage, archetype
from user's free text or voice input.
Zero asking. Pure sensing.
Using Groq/Llama3.3 — Free, unlimited
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Setup Groq ────────────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Constants — Your Exact Metadata Tags ──────────────────────
EMOTIONS = [
    "Fear", "Guilt", "Shame", "Anger", "Confusion",
    "Grief", "Love", "Longing", "Loneliness", "Exhaustion",
    "Hopelessness", "Numbness"
]

SITUATIONS = [
    "Breakup", "Betrayal", "Career Block", "Illness",
    "Loss", "Destiny vs Free Will", "Loneliness",
    "Family Conflict", "Identity Crisis", "Financial Stress"
]

THEMES = [
    "Dharma", "Karma", "Detachment", "Surrender",
    "Faith", "Ego", "True Love", "Illusion"
]

ARCHETYPES = [
    "Seeker", "Warrior", "Healer", "Guide", "Rebel", "Creator"
]

JOURNEY_STAGES = [
    "Triggered", "Searching", "Surrendering",
    "Awakening", "Detached", "Empowered"
]

RESOLUTIONS = [
    "Acceptance", "Action", "Surrender",
    "Inquiry", "Forgiveness", "Detachment"
]

CONTEXTS = [
    "Conflict", "Decision-making", "Transformation",
    "Rebirth", "Renunciation"
]


# ── Main Sensing Function ─────────────────────────────────────
def sense(user_message: str, session_history: list = []) -> dict:
    history_text = ""
    if session_history:
        history_text = "Previous messages in this session:\n"
        for msg in session_history[-3:]:
            history_text += f"User: {msg}\n"

    prompt = f"""You are the sensing engine of Rta — a sacred wisdom app.
A person has shared something. Read between the lines deeply.

{history_text}

CURRENT MESSAGE: "{user_message}"

Return ONLY raw JSON. No markdown. No explanation. Just JSON.

{{
    "primary_emotion": "one from {EMOTIONS}",
    "secondary_emotions": ["up to 2 from {EMOTIONS}"],
    "intensity": 7,
    "situation": "one from {SITUATIONS}",
    "theme": "one from {THEMES}",
    "archetype": "one from {ARCHETYPES}",
    "journey_stage": "one from {JOURNEY_STAGES}",
    "resolution_needed": "one from {RESOLUTIONS}",
    "context": "one from {CONTEXTS}",
    "depth_needed": "moderate",
    "crisis_signal": false,
    "what_they_need_now": "comfort",
    "key_phrases": ["phrases from their message"],
    "ready_for_depth": true,
    "sensing_notes": "what you detected"
}}

intensity: 1-10. depth_needed: surface/moderate/deep. Return ONLY JSON."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        result["raw_message"] = user_message
        result["session_length"] = len(session_history)
        return result
    except Exception as e:
        return {
            "primary_emotion": "Confusion",
            "secondary_emotions": [],
            "intensity": 5,
            "situation": "Unknown",
            "theme": "Dharma",
            "archetype": "Seeker",
            "journey_stage": "Triggered",
            "resolution_needed": "Acceptance",
            "context": "Conflict",
            "depth_needed": "moderate",
            "crisis_signal": False,
            "what_they_need_now": "presence",
            "key_phrases": [],
            "ready_for_depth": True,
            "sensing_notes": f"Fallback. Error: {str(e)}",
            "raw_message": user_message,
            "session_length": len(session_history)
        }


# ── Resonance Detector ────────────────────────────────────────
def detect_resonance(user_followup: str, story_shown: dict) -> dict:
    prompt = f"""User saw a wisdom story and responded.
STORY: {story_shown.get('core_wisdom', '')}
USER RESPONSE: "{user_followup}"

Return ONLY raw JSON:
{{
    "resonance_score": 8,
    "resonance_level": "deep",
    "emotion_in_response": "recognition",
    "direction": "go_deeper",
    "next_action": "continue_story",
    "breakthrough_detected": false,
    "notes": "observation"
}}
resonance_level: none/surface/moderate/deep/breakthrough
direction: go_deeper/different_story/different_angle/close_gently
Return ONLY JSON."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        return {
            "resonance_score": 5,
            "resonance_level": "moderate",
            "emotion_in_response": "neutral",
            "direction": "go_deeper",
            "next_action": "continue_story",
            "breakthrough_detected": False,
            "notes": f"Fallback. Error: {str(e)}"
        }


# ── Journey Stage Updater ─────────────────────────────────────
def detect_journey_shift(current_stage: str, session_history: list, latest_sensing: dict) -> dict:
    if len(session_history) < 2:
        return {"stage_shifted": False, "new_stage": current_stage}

    prompt = f"""Detect if user's journey stage has shifted.
CURRENT STAGE: {current_stage}
INTENSITY: {latest_sensing.get('intensity', 5)}
EMOTION: {latest_sensing.get('primary_emotion', 'Unknown')}
Stages: Triggered → Searching → Surrendering → Awakening → Detached → Empowered

Return ONLY raw JSON:
{{
    "stage_shifted": false,
    "new_stage": "{current_stage}",
    "shift_evidence": "evidence",
    "confidence": 0.8
}}"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except:
        return {"stage_shifted": False, "new_stage": current_stage}


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🌊 Testing Rta Sensing Engine...\n")

    test_messages = [
        "I keep giving everything to people who don't value me",
        "I just got fired and my relationship ended the same week",
        "I feel like I'll never be okay again",
        "Maybe this happened for a reason, I'm starting to understand",
        "I feel nothing anymore, just completely empty",
    ]

    for msg in test_messages:
        print(f"User: {msg}")
        result = sense(msg)
        print(f"Emotion: {result['primary_emotion']} (intensity: {result['intensity']}/10)")
        print(f"Stage: {result['journey_stage']} | Archetype: {result['archetype']}")
        print(f"Needs: {result['what_they_need_now']} | Depth: {result['depth_needed']}")
        print(f"Situation: {result['situation']} | Theme: {result['theme']}")
        print(f"Context: {result.get('context', 'N/A')}")
        print(f"Crisis: {result['crisis_signal']}")
        print("─" * 50)