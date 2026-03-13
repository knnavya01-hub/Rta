"""
TWILIO ENGINE — Ṛta
Two jobs:

1. OTP LOGIN
   Send 6-digit OTP to phone number
   Verify OTP → user is authenticated

2. SOS SAFE CIRCLE
   User adds up to 3 trusted contacts
   Crisis detected OR user taps SOS button
   Gentle SMS sent to all contacts + NGOs
"""

import os
import random
import time
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")   # your Twilio number

# In-memory OTP store — { phone: { otp, expires_at } }
# For production: move to Redis or Supabase
otp_store = {}

# ── NGO numbers built in ──────────────────────────────────────────────────────
NGO_CONTACTS = [
    {
        "name": "iCall",
        "number": "+919152987821",
        "description": "Psychosocial helpline — Mon-Sat 8am-10pm"
    },
    {
        "name": "Vandrevala Foundation",
        "number": "+18602662345",
        "description": "24/7 mental health helpline"
    },
    {
        "name": "Snehi",
        "number": "+914424640050",
        "description": "Emotional support helpline"
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# PART 1: OTP LOGIN
# ─────────────────────────────────────────────────────────────────────────────

def send_otp(phone_number: str) -> dict:
    """
    Sends a 6-digit OTP to the user's phone via SMS.
    OTP expires in 10 minutes.

    phone_number: E.164 format e.g. +919876543210
    """

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    expires_at = time.time() + 600   # 10 minutes

    # Store OTP
    otp_store[phone_number] = {
        "otp": otp,
        "expires_at": expires_at,
        "attempts": 0
    }

    message_body = (
        f"Your Ṛta verification code is: {otp}\n"
        f"Valid for 10 minutes.\n"
        f"Do not share this code."
    )

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )

        return {
            "success": True,
            "message_sid": message.sid,
            "phone": phone_number,
            "expires_in": 600
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "phone": phone_number
        }


def verify_otp(phone_number: str, entered_otp: str) -> dict:
    """
    Verifies the OTP entered by the user.
    Returns success/failure + reason.
    """

    stored = otp_store.get(phone_number)

    # No OTP found
    if not stored:
        return {
            "success": False,
            "reason": "no_otp",
            "message": "No OTP found. Please request a new one."
        }

    # Too many attempts (max 3)
    if stored["attempts"] >= 3:
        del otp_store[phone_number]
        return {
            "success": False,
            "reason": "too_many_attempts",
            "message": "Too many attempts. Please request a new OTP."
        }

    # Expired
    if time.time() > stored["expires_at"]:
        del otp_store[phone_number]
        return {
            "success": False,
            "reason": "expired",
            "message": "OTP expired. Please request a new one."
        }

    # Increment attempt count
    otp_store[phone_number]["attempts"] += 1

    # Wrong OTP
    if entered_otp != stored["otp"]:
        remaining = 3 - otp_store[phone_number]["attempts"]
        return {
            "success": False,
            "reason": "wrong_otp",
            "message": f"Incorrect code. {remaining} attempt(s) remaining."
        }

    # ✅ Correct OTP
    del otp_store[phone_number]   # Clean up
    return {
        "success": True,
        "phone": phone_number,
        "message": "Verified successfully."
    }


def resend_otp(phone_number: str) -> dict:
    """
    Clears old OTP and sends a new one.
    Rate limited — max once per 60 seconds.
    """

    existing = otp_store.get(phone_number)

    if existing:
        time_since_last = time.time() - (existing["expires_at"] - 600)
        if time_since_last < 60:
            wait = int(60 - time_since_last)
            return {
                "success": False,
                "reason": "rate_limited",
                "message": f"Please wait {wait} seconds before requesting a new OTP."
            }

        del otp_store[phone_number]

    return send_otp(phone_number)


# ─────────────────────────────────────────────────────────────────────────────
# PART 2: SOS SAFE CIRCLE
# ─────────────────────────────────────────────────────────────────────────────

def send_sos(
    user_name: str,
    trusted_contacts: list,
    trigger: str = "manual",
    include_ngos: bool = True
) -> dict:
    """
    Sends gentle SOS messages to trusted contacts + NGOs.

    user_name        : first name or "your person" if anonymous
    trusted_contacts : list of { name, phone } dicts (max 3)
    trigger          : "manual" (user tapped SOS) or "crisis" (auto-detected)
    include_ngos     : also send NGO numbers as reference

    Message is warm, not alarming.
    """

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    results = []

    # Message for trusted contacts
    if trigger == "crisis":
        contact_message = (
            f"This is a gentle message from Ṛta.\n\n"
            f"{user_name} may need your presence right now. "
            f"They are safe, but reaching out through Ṛta to let you know "
            f"they could use some support.\n\n"
            f"A simple message or call from you could mean everything. 🙏"
        )
    else:
        # Manual SOS tap
        contact_message = (
            f"This is a message from Ṛta.\n\n"
            f"{user_name} has reached out through their Safe Circle "
            f"to let you know they need support right now.\n\n"
            f"Please reach out to them when you can. 🙏"
        )

    # Send to each trusted contact
    for contact in trusted_contacts[:3]:   # Max 3
        try:
            message = client.messages.create(
                body=contact_message,
                from_=TWILIO_PHONE_NUMBER,
                to=contact["phone"]
            )
            results.append({
                "name": contact["name"],
                "phone": contact["phone"],
                "success": True,
                "sid": message.sid
            })
        except Exception as e:
            results.append({
                "name": contact["name"],
                "phone": contact["phone"],
                "success": False,
                "error": str(e)
            })

    # Send NGO info to user themselves
    if include_ngos:
        ngo_message = (
            f"Ṛta Safe Circle — Support Resources:\n\n"
            f"iCall: {NGO_CONTACTS[0]['number']}\n"
            f"Mon-Sat 8am-10pm\n\n"
            f"Vandrevala Foundation: {NGO_CONTACTS[1]['number']}\n"
            f"24/7 support\n\n"
            f"You are not alone. 🙏"
        )

        # We'd need the user's own number here
        # Passed via user profile from Supabase

    sent_count = sum(1 for r in results if r["success"])

    return {
        "success": sent_count > 0,
        "sent_to": sent_count,
        "total_contacts": len(trusted_contacts[:3]),
        "results": results,
        "ngos_available": NGO_CONTACTS if include_ngos else []
    }


def get_ngo_list() -> list:
    """Returns all built-in NGO contacts for the Safe Circle screen."""
    return NGO_CONTACTS


def send_crisis_resources(user_phone: str) -> dict:
    """
    Sends NGO + helpline numbers directly to the user
    when crisis is detected in sensing engine.
    """

    message = (
        f"Ṛta is with you right now. 🙏\n\n"
        f"If you need to speak to someone:\n\n"
        f"iCall: {NGO_CONTACTS[0]['number']}\n"
        f"(Mon-Sat, 8am-10pm)\n\n"
        f"Vandrevala Foundation: {NGO_CONTACTS[1]['number']}\n"
        f"(Available 24/7)\n\n"
        f"You are not alone. This moment will pass."
    )

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=user_phone
        )
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Test ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n📱 Testing Ṛta Twilio Engine...\n")

    # Test OTP flow
    test_phone = "+919999999999"   # Replace with real number to test

    print(f"Sending OTP to {test_phone}...")
    result = send_otp(test_phone)
    print(f"Send result: {result}")

    # Test verify (won't work without real SMS)
    verify_result = verify_otp(test_phone, "123456")
    print(f"Verify result: {verify_result}")

    # Test NGO list
    print("\nBuilt-in NGOs:")
    for ngo in get_ngo_list():
        print(f"  {ngo['name']}: {ngo['number']}")