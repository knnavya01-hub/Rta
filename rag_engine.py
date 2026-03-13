"""
RAG ENGINE — Ṛta
Retrieval Augmented Generation
Searches ChromaDB for best matching wisdom
Ranks by all 7 metadata layers
Evaluates match quality before returning
"""

import os
import json
from database import search_wisdom, get_stats
from dotenv import load_dotenv

load_dotenv()


# ── RAG Ranking Weights ───────────────────────────────────────
WEIGHTS = {
    "semantic":      0.30,  # Core meaning match
    "emotion":       0.20,  # Emotion match
    "situation":     0.20,  # Situation match
    "journey_stage": 0.15,  # Journey stage match
    "archetype":     0.10,  # Archetype match
    "context":       0.10,  # Context layer match
    "not_seen":      0.05,  # Avoid repeats (applied in database.py)
}

# ── Minimum score to show a story ────────────────────────────
MIN_SCORE_THRESHOLD = 0.35


# ── Main RAG Function ─────────────────────────────────────────
def find_best_story(sensing_result: dict, seen_verses: list = []) -> dict:
    """
    Takes sensing result from sensing_engine.
    Finds best matching wisdom story.
    Evaluates match quality.
    Returns best story or None if no good match.
    """

    # Extract sensing data
    query = sensing_result.get("raw_message", "")
    emotions = [sensing_result.get("primary_emotion", "")]
    emotions += sensing_result.get("secondary_emotions", [])
    emotions = [e for e in emotions if e]  # Remove empty

    situation = sensing_result.get("situation", "")
    journey_stage = sensing_result.get("journey_stage", "")
    archetype = sensing_result.get("archetype", "")
    context = sensing_result.get("context", "")
    depth_needed = sensing_result.get("depth_needed", "moderate")

    # Search ChromaDB
    results = search_wisdom(
        query=query,
        emotions=emotions,
        situations=[situation] if situation else [],
        journey_stage=journey_stage,
        archetype=archetype,
        context=context,
        n_results=5,
        exclude_ids=seen_verses
    )

    if not results:
        return None

    # Evaluate top result
    best = results[0]
    evaluation = evaluate_rag_match(sensing_result, best)
    best["rag_evaluation"] = evaluation
    best["match_quality"] = evaluation.get("match_quality", "moderate")

    # If best score too low — return with warning
    if best["score"] < MIN_SCORE_THRESHOLD:
        best["low_confidence"] = True
        best["fallback_message"] = "Finding the right story for you..."
    else:
        best["low_confidence"] = False

    return best


# ── RAG Evaluation ────────────────────────────────────────────
def evaluate_rag_match(sensing: dict, story: dict) -> dict:
    """
    Evaluates how well the found story matches the user's need.
    This is the RAG evaluation layer.
    """

    emotion = sensing.get("primary_emotion", "")
    stage = sensing.get("journey_stage", "")
    situation = sensing.get("situation", "")
    context = sensing.get("context", "")

    story_emotions = story.get("emotions", "")
    story_stages = story.get("journey_stages", "")
    story_situations = story.get("situations", "")
    story_context = story.get("context", "")
    score = story.get("score", 0)

    # Calculate match factors
    emotion_match = emotion in story_emotions
    stage_match = stage in story_stages
    situation_match = situation in story_situations
    context_match = context in story_context

    matches = sum([emotion_match, stage_match, situation_match, context_match])

    if score > 0.7 and matches >= 3:
        match_quality = "excellent"
    elif score > 0.5 and matches >= 2:
        match_quality = "good"
    elif score > 0.35 and matches >= 1:
        match_quality = "moderate"
    else:
        match_quality = "low"

    return {
        "match_quality": match_quality,
        "score": score,
        "emotion_match": emotion_match,
        "stage_match": stage_match,
        "situation_match": situation_match,
        "context_match": context_match,
        "total_matches": matches,
        "recommendation": get_recommendation(match_quality)
    }


def get_recommendation(match_quality: str) -> str:
    recommendations = {
        "excellent": "show_story",
        "good": "show_story",
        "moderate": "show_story_with_bridge",
        "low": "try_different_approach"
    }
    return recommendations.get(match_quality, "show_story")


# ── Get Alternative Stories ───────────────────────────────────
def get_alternatives(sensing_result: dict, seen_verses: list = [], n: int = 3) -> list:
    """
    Returns multiple story options.
    Used when first story didn't resonate.
    """
    query = sensing_result.get("raw_message", "")
    emotions = [sensing_result.get("primary_emotion", "")]
    situation = sensing_result.get("situation", "")
    journey_stage = sensing_result.get("journey_stage", "")
    archetype = sensing_result.get("archetype", "")
    context = sensing_result.get("context", "")

    results = search_wisdom(
        query=query,
        emotions=emotions,
        situations=[situation] if situation else [],
        journey_stage=journey_stage,
        archetype=archetype,
        context=context,
        n_results=n + len(seen_verses),
        exclude_ids=seen_verses
    )

    return results[:n]


# ── Format Story for Output ───────────────────────────────────
def format_story_for_output(story: dict, sensing: dict) -> dict:
    """
    Takes raw story from DB.
    Formats it for scene_engine to use.
    Selects ancient or modern parallel based on depth needed.
    """
    depth = sensing.get("depth_needed", "moderate")
    intensity = sensing.get("intensity", 5)

    # High intensity → start with gentler modern parallel
    # Low intensity → can go straight to ancient
    if intensity >= 7:
        primary_narrative = story.get("modern_parallel", "")
        secondary_narrative = story.get("ancient_narrative", "")
    else:
        primary_narrative = story.get("ancient_narrative", "")
        secondary_narrative = story.get("modern_parallel", "")

    return {
        "verse_id": story.get("id", ""),
        "scripture": story.get("scripture", ""),
        "core_wisdom": story.get("core_wisdom", ""),
        "primary_narrative": primary_narrative,
        "secondary_narrative": secondary_narrative,
        "scene_1": story.get("scene_1", ""),
        "scene_2": story.get("scene_2", ""),
        "scene_3": story.get("scene_3", ""),
        "deep_question": story.get("deep_question", ""),
        "sanskrit": story.get("sanskrit", ""),
        "match_quality": story.get("match_quality", "moderate"),
        "score": story.get("score", 0),
    }


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🌊 Testing Ṛta RAG Engine...\n")

    # Simulate sensing results
    test_cases = [
        {
            "raw_message": "I worked so hard but nothing is working out",
            "primary_emotion": "Exhaustion",
            "secondary_emotions": ["Hopelessness"],
            "intensity": 8,
            "situation": "Career Block",
            "theme": "Karma",
            "archetype": "Warrior",
            "journey_stage": "Triggered",
            "resolution_needed": "Acceptance",
            "context": "Conflict",
            "depth_needed": "moderate",
        },
        {
            "raw_message": "I feel like I don't know who I am anymore",
            "primary_emotion": "Confusion",
            "secondary_emotions": ["Loneliness"],
            "intensity": 7,
            "situation": "Identity Crisis",
            "theme": "Ego",
            "archetype": "Seeker",
            "journey_stage": "Searching",
            "resolution_needed": "Inquiry",
            "context": "Transformation",
            "depth_needed": "deep",
        },
        {
            "raw_message": "My best friend betrayed me completely",
            "primary_emotion": "Grief",
            "secondary_emotions": ["Anger"],
            "intensity": 9,
            "situation": "Betrayal",
            "theme": "Karma",
            "archetype": "Warrior",
            "journey_stage": "Triggered",
            "resolution_needed": "Forgiveness",
            "context": "Conflict",
            "depth_needed": "deep",
        }
    ]

    for i, sensing in enumerate(test_cases):
        print(f"Test {i+1}: '{sensing['raw_message']}'")
        story = find_best_story(sensing, seen_verses=[])

        if story:
            formatted = format_story_for_output(story, sensing)
            print(f"  Match: {story['id']} (score: {story['score']:.2f})")
            print(f"  Quality: {story.get('match_quality', 'N/A')}")
            print(f"  Wisdom: {formatted['core_wisdom']}")
            print(f"  Scene 1: {formatted['scene_1']}")
            print(f"  Question: {formatted['deep_question']}")
        else:
            print("  No match found")
        print("─" * 50)

    print(f"\n📊 Database: {get_stats()} verses")