"""
APP.PY — Ṛta Backend
The main connector. All engines meet here.
Frontend talks to these endpoints.

Engines connected:
→ sensing_engine.py   (emotion detection)
→ rag_engine.py       (find matching verse)
→ scene_engine.py     (3 painting scenes)
→ video_engine.py     (living paintings)
→ memory_engine.py    (user memory)
→ twilio_engine.py    (OTP + SOS)
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# ── Import all engines ────────────────────────────────────────────────────────
from sensing_engine import sense, detect_resonance
from rag_engine import find_best_story
from scene_engine import generate_scenes
from video_engine import animate_three_scenes
from memory_engine import (
    get_or_create_user,
    get_user_memory,
    update_user_after_session,
    save_wisdom,
    get_saved_wisdoms,
    delete_wisdom,
    get_safe_circle,
    add_safe_contact,
    remove_safe_contact,
    get_peace_scale,
    get_personalized_greeting
)
#
# TWILIO STUBBED FOR MVP
def send_otp(p): return {'success':True,'message':'demo'}
def verify_otp(p,o): return {'success':True}
def resend_otp(p): return {'success':True}
def send_sos(**k): return {'success':True}
def send_crisis_resources(p): pass
def get_ngo_list(): return [{'name':'iCall','number':'9152987821'},{'name':'Vandrevala','number':'1860-2662-345'},{'name':'Snehi','number':'044-24640050'}]


load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow frontend to talk to backend

# ── In-memory session store ───────────────────────────────────────────────────
# { session_id: { user_id, messages, sensing_data, start_time } }
active_sessions = {}


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "Ṛta is alive 🙏",
        "engines": [
            "sensing", "rag", "scene",
            "video", "memory", "twilio"
        ]
    })


# ─────────────────────────────────────────────────────────────────────────────
# AUTH — OTP LOGIN
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/auth/send-otp", methods=["POST"])
def api_send_otp():
    """
    Send OTP to phone number.
    Body: { phone: "+919876543210" }
    """
    data = request.json
    phone = data.get("phone")

    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400

    result = send_otp(phone)
    return jsonify(result)


@app.route("/api/auth/verify-otp", methods=["POST"])
def api_verify_otp():
    """
    Verify OTP + get or create user.
    Body: { phone: "+919876543210", otp: "123456" }
    """
    data = request.json
    phone = data.get("phone")
    otp   = data.get("otp")

    if not phone or not otp:
        return jsonify({"success": False, "error": "Phone and OTP required"}), 400

    # Verify OTP
    verify_result = verify_otp(phone, otp)
    if not verify_result["success"]:
        return jsonify(verify_result), 401

    # Get or create user in Supabase
    user_result = get_or_create_user(phone)
    if not user_result["success"]:
        return jsonify(user_result), 500

    return jsonify({
        "success": True,
        "user": user_result["user"],
        "is_new": user_result["is_new"]
    })


@app.route("/api/auth/resend-otp", methods=["POST"])
def api_resend_otp():
    """Resend OTP (rate limited to once per 60 seconds)."""
    data = request.json
    phone = data.get("phone")
    result = resend_otp(phone)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# HOME — GREETING + DAILY SCENE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/home", methods=["POST"])
def api_home():
    """
    Called when user opens the app.
    Returns personalized greeting + user memory summary.
    Body: { user_id: "..." }
    """
    data = request.json
    user_id = data.get("user_id")

    greeting = get_personalized_greeting(user_id)
    memory   = get_user_memory(user_id)

    return jsonify({
        "success": True,
        "greeting": greeting,
        "journey_stage": memory.get("journey_stage", "Triggered"),
        "total_sessions": memory.get("total_sessions", 0),
        "is_returning": memory.get("total_sessions", 0) > 0
    })


# ─────────────────────────────────────────────────────────────────────────────
# CORE FLOW — SENSE → STORY → SCENES → VIDEO
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/sense", methods=["POST"])
def api_sense():
    """
    Step 1: User types or speaks.
    Detects emotion, stage, archetype invisibly.
    Body: { message: "...", user_id: "...", session_history: [] }
    """
    data           = request.json
    message        = data.get("message", "")
    user_id        = data.get("user_id")
    session_history = data.get("session_history", [])

    if not message:
        return jsonify({"success": False, "error": "Message required"}), 400

    # Sense the emotion
    sensing = sense(message, session_history)

    # Crisis detected — send resources immediately
    if sensing.get("crisis_signal"):
        if user_id:
            memory = get_user_memory(user_id)
            if memory.get("user", {}).get("phone"):
                send_crisis_resources(memory["user"]["phone"])

    return jsonify({"success": True, "sensing": sensing})


@app.route("/api/story", methods=["POST"])
def api_story():
    """
    Step 2: Find matching verse + generate 3 scenes.
    Body: { sensing: {...}, user_id: "...", animate: true/false }

    animate=true  → living video paintings (slower, better)
    animate=false → static images (faster, for testing)
    """
    data    = request.json
    sensing = data.get("sensing", {})
    user_id = data.get("user_id")
    animate = data.get("animate", True)

    if not sensing:
        return jsonify({"success": False, "error": "Sensing data required"}), 400

    # Get verses already shown to this user
    verses_shown = []
    if user_id:
        memory = get_user_memory(user_id)
        verses_shown = memory.get("verses_shown", [])

    # Find best matching verse
    story = find_best_story(sensing, exclude_verses=verses_shown)
    if not story:
        return jsonify({"success": False, "error": "No matching story found"}), 404

    # Generate 3 painting scenes
    scenes = generate_scenes(story, sensing)

    # Animate scenes into living paintings
    if animate and scenes:
        scenes = animate_three_scenes(scenes)

    return jsonify({
        "success": True,
        "story": story,
        "scenes": scenes,
        "core_wisdom": story.get("core_wisdom", ""),
        "deep_question": story.get("deep_question", ""),
        "verse_id": story.get("id", "")
    })


@app.route("/api/resonance", methods=["POST"])
def api_resonance():
    """
    Step 3: User responds after seeing 3 scenes.
    Detects how much the story resonated.
    Body: { response: "...", story: {...}, user_id: "..." }
    """
    data     = request.json
    response = data.get("response", "")
    story    = data.get("story", {})

    resonance = detect_resonance(response, story)

    return jsonify({
        "success": True,
        "resonance": resonance,
        "next_action": resonance.get("next_action", "continue_story")
    })


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/memory/get", methods=["POST"])
def api_memory_get():
    """
    Load user's long-term memory.
    Body: { user_id: "..." }
    """
    data    = request.json
    user_id = data.get("user_id")

    result = get_user_memory(user_id)
    return jsonify(result)


@app.route("/api/memory/update", methods=["POST"])
def api_memory_update():
    """
    Update memory after session ends.
    Body: { user_id: "...", session_data: {...} }
    """
    data         = request.json
    user_id      = data.get("user_id")
    session_data = data.get("session_data", {})

    result = update_user_after_session(user_id, session_data)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/journal/save", methods=["POST"])
def api_journal_save():
    """
    Save a wisdom to journal.
    Body: { user_id: "...", wisdom: { verse_id, wisdom_text, scene_image, emotion, stage } }
    """
    data    = request.json
    user_id = data.get("user_id")
    wisdom  = data.get("wisdom", {})

    result = save_wisdom(user_id, wisdom)
    return jsonify(result)


@app.route("/api/journal/get", methods=["POST"])
def api_journal_get():
    """
    Get all saved wisdoms for journal screen.
    Body: { user_id: "..." }
    """
    data    = request.json
    user_id = data.get("user_id")

    result = get_saved_wisdoms(user_id)
    return jsonify(result)


@app.route("/api/journal/delete", methods=["POST"])
def api_journal_delete():
    """
    Delete a saved wisdom.
    Body: { user_id: "...", wisdom_id: "..." }
    """
    data       = request.json
    user_id    = data.get("user_id")
    wisdom_id  = data.get("wisdom_id")

    result = delete_wisdom(wisdom_id, user_id)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# PEACE SCALE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/peace-scale", methods=["POST"])
def api_peace_scale():
    """
    Auto-calculated peace scale from last 7 sessions.
    Body: { user_id: "..." }
    """
    data    = request.json
    user_id = data.get("user_id")

    result = get_peace_scale(user_id)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# SOS SAFE CIRCLE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/safe-circle/get", methods=["POST"])
def api_safe_circle_get():
    """Get user's trusted contacts + NGO list."""
    data    = request.json
    user_id = data.get("user_id")

    contacts = get_safe_circle(user_id)
    ngos     = get_ngo_list()

    return jsonify({
        "success": True,
        "contacts": contacts.get("contacts", []),
        "ngos": ngos
    })


@app.route("/api/safe-circle/add", methods=["POST"])
def api_safe_circle_add():
    """
    Add trusted contact.
    Body: { user_id: "...", name: "...", phone: "+91..." }
    """
    data    = request.json
    user_id = data.get("user_id")
    name    = data.get("name")
    phone   = data.get("phone")

    result = add_safe_contact(user_id, name, phone)
    return jsonify(result)


@app.route("/api/safe-circle/remove", methods=["POST"])
def api_safe_circle_remove():
    """
    Remove trusted contact.
    Body: { user_id: "...", contact_id: "..." }
    """
    data       = request.json
    user_id    = data.get("user_id")
    contact_id = data.get("contact_id")

    result = remove_safe_contact(contact_id, user_id)
    return jsonify(result)


@app.route("/api/sos/trigger", methods=["POST"])
def api_sos_trigger():
    """
    Trigger SOS — sends message to all trusted contacts.
    Body: { user_id: "...", trigger: "manual" or "crisis" }
    """
    data    = request.json
    user_id = data.get("user_id")
    trigger = data.get("trigger", "manual")

    # Get user info
    memory   = get_user_memory(user_id)
    user     = memory.get("user", {})
    user_name = "Your person"  # Anonymous by default

    # Get trusted contacts
    circle = get_safe_circle(user_id)
    contacts = circle.get("contacts", [])

    if not contacts:
        return jsonify({
            "success": False,
            "error": "No contacts in Safe Circle yet."
        })

    result = send_sos(
        user_name=user_name,
        trusted_contacts=contacts,
        trigger=trigger,
        include_ngos=True
    )

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🌿 Ṛta Backend Starting...\n")
    print("Endpoints ready:")
    print("  /api/health")
    print("  /api/auth/send-otp")
    print("  /api/auth/verify-otp")
    print("  /api/home")
    print("  /api/sense")
    print("  /api/story")
    print("  /api/resonance")
    print("  /api/memory/get + update")
    print("  /api/journal/save + get + delete")
    print("  /api/peace-scale")
    print("  /api/safe-circle/get + add + remove")
    print("  /api/sos/trigger")
    print("\n🙏 Running on http://localhost:5000\n")

    app.run(debug=True, port=5000)