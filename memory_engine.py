"""
MEMORY ENGINE — Ṛta
Long-term user memory using Supabase.

Two tables:
1. users         → profile, phone, journey stage, archetype
2. sessions      → every session stored forever
3. saved_wisdoms → wisdoms user saved from sessions (journal)
4. safe_circle   → trusted SOS contacts

Short-term memory = Python dict (in-memory, per session)
Long-term memory  = Supabase (persists forever)
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ── Connect to Supabase ───────────────────────────────────────────────────────
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE TABLE SETUP SQL
# Run this ONCE in your Supabase SQL editor:
# ─────────────────────────────────────────────────────────────────────────────
SETUP_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    phone               TEXT UNIQUE NOT NULL,
    journey_stage       TEXT DEFAULT 'Triggered',
    dominant_archetype  TEXT DEFAULT 'Seeker',
    emotional_patterns  JSONB DEFAULT '{}',
    verses_shown        JSONB DEFAULT '[]',
    total_sessions      INTEGER DEFAULT 0,
    breakthrough_count  INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT NOW(),
    last_session        TIMESTAMP DEFAULT NOW()
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    messages        JSONB DEFAULT '[]',
    primary_emotion TEXT,
    journey_stage   TEXT,
    resonance_score FLOAT DEFAULT 0,
    breakthrough    BOOLEAN DEFAULT FALSE,
    verse_used      TEXT,
    duration_secs   INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Saved wisdoms (journal)
CREATE TABLE IF NOT EXISTS saved_wisdoms (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    verse_id    TEXT,
    wisdom_text TEXT,
    scene_image TEXT,
    emotion     TEXT,
    stage       TEXT,
    saved_at    TIMESTAMP DEFAULT NOW()
);

-- Safe circle contacts
CREATE TABLE IF NOT EXISTS safe_circle (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);
"""


# ─────────────────────────────────────────────────────────────────────────────
# USER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_user(phone: str) -> dict:
    """
    Gets existing user or creates new one.
    Called after OTP verification.
    Returns user dict.
    """
    try:
        supabase = get_client()

        # Try to get existing user
        result = supabase.table("users").select("*").eq("phone", phone).execute()

        if result.data:
            user = result.data[0]
            # Update last seen
            supabase.table("users").update({
                "last_session": datetime.now().isoformat()
            }).eq("phone", phone).execute()
            return {"success": True, "user": user, "is_new": False}

        # Create new user
        new_user = {
            "phone": phone,
            "journey_stage": "Triggered",
            "dominant_archetype": "Seeker",
            "emotional_patterns": {},
            "verses_shown": [],
            "total_sessions": 0,
            "breakthrough_count": 0
        }

        result = supabase.table("users").insert(new_user).execute()
        return {"success": True, "user": result.data[0], "is_new": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_user_memory(user_id: str) -> dict:
    """
    Loads full long-term memory for a user.
    Called at start of every session.
    """
    try:
        supabase = get_client()

        # Get user profile
        user_result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_result.data:
            return {"success": False, "error": "User not found"}

        user = user_result.data[0]

        # Get last 5 sessions
        sessions_result = (
            supabase.table("sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )

        # Get saved wisdoms count
        wisdoms_result = (
            supabase.table("saved_wisdoms")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )

        return {
            "success": True,
            "user": user,
            "recent_sessions": sessions_result.data,
            "total_wisdoms_saved": wisdoms_result.count or 0,
            "verses_shown": user.get("verses_shown", []),
            "journey_stage": user.get("journey_stage", "Triggered"),
            "dominant_archetype": user.get("dominant_archetype", "Seeker"),
            "emotional_patterns": user.get("emotional_patterns", {}),
            "total_sessions": user.get("total_sessions", 0)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def update_user_after_session(user_id: str, session_data: dict) -> dict:
    """
    Updates user memory after a session ends.
    Called automatically — user never knows.

    session_data = {
        primary_emotion, journey_stage, archetype,
        verse_id, resonance_score, breakthrough,
        messages, duration_secs
    }
    """
    try:
        supabase = get_client()

        # Get current user data
        user_result = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_result.data:
            return {"success": False, "error": "User not found"}

        user = user_result.data[0]

        # Update emotional patterns
        patterns = user.get("emotional_patterns", {})
        emotion = session_data.get("primary_emotion", "Unknown")
        patterns[emotion] = patterns.get(emotion, 0) + 1

        # Update verses shown (avoid repeats)
        verses_shown = user.get("verses_shown", [])
        verse_id = session_data.get("verse_id")
        if verse_id and verse_id not in verses_shown:
            verses_shown.append(verse_id)

        # Update journey stage if shifted
        new_stage = session_data.get("journey_stage", user["journey_stage"])

        # Update breakthrough count
        breakthrough_count = user.get("breakthrough_count", 0)
        if session_data.get("breakthrough"):
            breakthrough_count += 1

        # Update user profile
        supabase.table("users").update({
            "journey_stage": new_stage,
            "dominant_archetype": session_data.get("archetype", user["dominant_archetype"]),
            "emotional_patterns": patterns,
            "verses_shown": verses_shown,
            "total_sessions": user.get("total_sessions", 0) + 1,
            "breakthrough_count": breakthrough_count,
            "last_session": datetime.now().isoformat()
        }).eq("id", user_id).execute()

        # Save session to history
        supabase.table("sessions").insert({
            "user_id": user_id,
            "messages": session_data.get("messages", []),
            "primary_emotion": emotion,
            "journey_stage": new_stage,
            "resonance_score": session_data.get("resonance_score", 0),
            "breakthrough": session_data.get("breakthrough", False),
            "verse_used": verse_id,
            "duration_secs": session_data.get("duration_secs", 0)
        }).execute()

        return {"success": True, "stage": new_stage}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL — SAVED WISDOMS
# ─────────────────────────────────────────────────────────────────────────────

def save_wisdom(user_id: str, wisdom: dict) -> dict:
    """
    Saves a wisdom to the user's journal.

    wisdom = {
        verse_id, wisdom_text, scene_image,
        emotion, stage
    }
    """
    try:
        supabase = get_client()

        result = supabase.table("saved_wisdoms").insert({
            "user_id": user_id,
            "verse_id": wisdom.get("verse_id"),
            "wisdom_text": wisdom.get("wisdom_text"),
            "scene_image": wisdom.get("scene_image"),
            "emotion": wisdom.get("emotion"),
            "stage": wisdom.get("stage")
        }).execute()

        return {"success": True, "saved": result.data[0]}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_saved_wisdoms(user_id: str) -> dict:
    """Gets all saved wisdoms for journal display."""
    try:
        supabase = get_client()

        result = (
            supabase.table("saved_wisdoms")
            .select("*")
            .eq("user_id", user_id)
            .order("saved_at", desc=True)
            .execute()
        )

        return {"success": True, "wisdoms": result.data}

    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_wisdom(wisdom_id: str, user_id: str) -> dict:
    """Removes a saved wisdom from journal."""
    try:
        supabase = get_client()

        supabase.table("saved_wisdoms").delete().eq(
            "id", wisdom_id
        ).eq("user_id", user_id).execute()

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SAFE CIRCLE CONTACTS
# ─────────────────────────────────────────────────────────────────────────────

def get_safe_circle(user_id: str) -> dict:
    """Gets user's trusted SOS contacts."""
    try:
        supabase = get_client()

        result = (
            supabase.table("safe_circle")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        return {"success": True, "contacts": result.data}

    except Exception as e:
        return {"success": False, "error": str(e)}


def add_safe_contact(user_id: str, name: str, phone: str) -> dict:
    """Adds a trusted contact to safe circle. Max 3."""
    try:
        supabase = get_client()

        # Check count
        existing = supabase.table("safe_circle").select(
            "id", count="exact"
        ).eq("user_id", user_id).execute()

        if (existing.count or 0) >= 3:
            return {
                "success": False,
                "error": "Maximum 3 contacts allowed in Safe Circle."
            }

        result = supabase.table("safe_circle").insert({
            "user_id": user_id,
            "name": name,
            "phone": phone
        }).execute()

        return {"success": True, "contact": result.data[0]}

    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_safe_contact(contact_id: str, user_id: str) -> dict:
    """Removes a contact from safe circle."""
    try:
        supabase = get_client()

        supabase.table("safe_circle").delete().eq(
            "id", contact_id
        ).eq("user_id", user_id).execute()

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# PEACE SCALE — Auto calculated from sessions
# ─────────────────────────────────────────────────────────────────────────────

def get_peace_scale(user_id: str) -> dict:
    """
    Auto-calculates the user's peace scale from last 7 days.
    Never shown as a number — only as a gentle visual graph.
    User never feels measured.
    """
    try:
        supabase = get_client()

        # Get last 7 sessions
        result = (
            supabase.table("sessions")
            .select("resonance_score, journey_stage, breakthrough, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(7)
            .execute()
        )

        sessions = result.data
        if not sessions:
            return {"success": True, "scale": [], "trend": "neutral"}

        # Build 7-day journey graph
        scale = []
        for session in reversed(sessions):
            stage_scores = {
                "Triggered": 2,
                "Searching": 4,
                "Surrendering": 5,
                "Awakening": 7,
                "Detached": 8,
                "Empowered": 9
            }
            stage_score = stage_scores.get(session.get("journey_stage", "Triggered"), 3)
            resonance = session.get("resonance_score", 0)
            breakthrough_bonus = 2 if session.get("breakthrough") else 0

            # Combined peace score (0-10)
            peace = min(10, (stage_score * 0.6) + (resonance * 0.3) + breakthrough_bonus)

            scale.append({
                "date": session["created_at"][:10],
                "peace": round(peace, 1),
                "stage": session.get("journey_stage", "Triggered")
            })

        # Trend
        if len(scale) >= 2:
            trend = "rising" if scale[-1]["peace"] > scale[0]["peace"] else \
                    "falling" if scale[-1]["peace"] < scale[0]["peace"] else "stable"
        else:
            trend = "neutral"

        return {
            "success": True,
            "scale": scale,
            "trend": trend,
            "latest_peace": scale[-1]["peace"] if scale else 5
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY-BASED GREETING
# ─────────────────────────────────────────────────────────────────────────────

def get_personalized_greeting(user_id: str) -> str:
    """
    Returns a warm, memory-based greeting for the home screen.
    Changes based on time of day + past sessions.
    Never generic. Always personal.
    """
    try:
        memory = get_user_memory(user_id)
        if not memory["success"]:
            return get_default_greeting()

        user = memory["user"]
        total_sessions = user.get("total_sessions", 0)
        stage = user.get("journey_stage", "Triggered")
        patterns = user.get("emotional_patterns", {})

        hour = datetime.now().hour

        # Time of day
        if hour < 6:
            time_greeting = "You're up late"
        elif hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        elif hour < 21:
            time_greeting = "Good evening"
        else:
            time_greeting = "Late night"

        # First time
        if total_sessions == 0:
            return f"{time_greeting}. Ṛta is here with you."

        # Returning user
        if total_sessions == 1:
            return f"{time_greeting}. Welcome back. 🙏"

        # Based on stage
        stage_greetings = {
            "Triggered":    f"{time_greeting}. Ṛta is here. Take your time.",
            "Searching":    f"{time_greeting}. Something is stirring in you.",
            "Surrendering": f"{time_greeting}. The quiet is speaking.",
            "Awakening":    f"{time_greeting}. Something is shifting. 🙏",
            "Detached":     f"{time_greeting}. Peace is your natural state.",
            "Empowered":    f"{time_greeting}. You know the way now. 🙏"
        }

        return stage_greetings.get(stage, f"{time_greeting}. Ṛta is here. 🙏")

    except Exception:
        return get_default_greeting()


def get_default_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning. Ṛta is here. 🙏"
    elif hour < 17:
        return "Good afternoon. Ṛta is here. 🙏"
    elif hour < 21:
        return "Good evening. Ṛta is here. 🙏"
    else:
        return "Ṛta is here with you. 🙏"


# ── Test ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🧠 Testing Ṛta Memory Engine...\n")
    print("Note: Needs Supabase keys in .env to run")
    print("Tables to create — run SETUP_SQL in Supabase SQL editor")
    print("\nSetup SQL:")
    print(SETUP_SQL[:200] + "...")