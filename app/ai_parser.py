"""
ai_parser.py — AI-powered bank email parser.
Extracts structured transaction details from raw bank alert email text.
Supports Google Gemini and Groq (Llama) models based on .env configuration.
"""

import json
import os
import sys
import re
from dotenv import load_dotenv

# Fix Windows emoji encoding issue
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))
from categories import CATEGORIES, classify_merchant, validate_category

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Provider & Client Initialization ──────────────────────────────────────────
_provider = None
_client = None


def _get_provider_and_client():
    """
    Determine which provider to use:
    - Reads AI_PROVIDER from .env ('gemini' or 'groq').
    - If AI_PROVIDER is not explicitly set, auto-detects based on available keys.
    """
    global _provider, _client
    if _client is not None:
        return _provider, _client

    provider_choice = os.getenv("AI_PROVIDER", "").strip().lower()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    # Determine provider
    if provider_choice:
        if provider_choice not in ("gemini", "groq"):
            raise ValueError(f"❌ Unknown AI_PROVIDER '{provider_choice}'. Allowed values: 'gemini' or 'groq'.")
        target_provider = provider_choice
    else:
        # Auto-detect if AI_PROVIDER is not set
        if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
            target_provider = "gemini"
        elif groq_api_key and groq_api_key != "your_groq_api_key_here":
            target_provider = "groq"
        else:
            target_provider = "gemini"

    # Initialize the selected provider
    if target_provider == "gemini":
        if not gemini_api_key or gemini_api_key == "your_gemini_api_key_here":
            raise ValueError(
                "❌ AI_PROVIDER is set to 'gemini', but GEMINI_API_KEY is missing or invalid in .env.\n"
                "Get a free API key at: https://aistudio.google.com/apikey"
            )
        from google import genai
        _provider = "gemini"
        _client = genai.Client(api_key=gemini_api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        print(f"🤖 AI Parser using Gemini (Model: {model})")
        return _provider, _client

    else:  # groq
        if not groq_api_key or groq_api_key == "your_groq_api_key_here":
            raise ValueError(
                "❌ AI_PROVIDER is set to 'groq', but GROQ_API_KEY is missing or invalid in .env.\n"
                "Get a free API key at: https://console.groq.com/keys"
            )
        from groq import Groq
        _provider = "groq"
        _client = Groq(api_key=groq_api_key)
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        print(f"🤖 AI Parser using Groq (Model: {model})")
        return _provider, _client


# ── System prompt for Transaction Parsing ─────────────────────────────────────
SYSTEM_PROMPT = f"""You are a precise bank transaction email parser for Indian banks.

Extract the following details from the bank alert email and respond ONLY with valid JSON.
Do not include any explanation or markdown — just the raw JSON object.

JSON schema:
{{
  "is_transaction": true/false,        // false if this email is NOT a transaction alert
  "type": "debit" or "credit",
  "amount": <number in INR, no currency symbol>,
  "date": "YYYY-MM-DD",
  "time": "HH:MM" or null,
  "merchant": "<merchant/payee name, clean title case>",
  "category": "<one of the valid categories below>",
  "balance": <available balance as number, or null if not mentioned>,
  "description": "<brief 1-line description of the transaction>"
}}

Valid categories: {", ".join(CATEGORIES)}

Rules:
- If the email is a promotional mail, OTP, login alert, or not a transaction, set is_transaction=false and return only that field.
- Amount must be a plain number (e.g. 1250.50), never a string.
- For merchant, extract the business name cleanly (e.g. "Swiggy", "Amazon", "HDFC ATM").
- For UPI transfers, merchant = recipient name or UPI ID (shortened).
- Date format must be YYYY-MM-DD.
- Choose the most fitting category from the list above.
"""


def _parse_with_groq(client, email_body: str) -> str:
    """Call Groq API using Llama model."""
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this bank email:\n\n{email_body}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return completion.choices[0].message.content.strip()


def _parse_with_gemini(client, email_body: str) -> str:
    """Call Gemini API."""
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    interaction = client.interactions.create(
        model=model,
        system_instruction=SYSTEM_PROMPT,
        input=f"Parse this bank email:\n\n{email_body}",
        store=False,
    )
    return interaction.output_text.strip()


def parse_email_with_ai(email_body: str) -> dict | None:
    """
    Use Google Gemini or Groq (Llama) to parse a bank alert email based on .env.
    Returns a dict with transaction details, or None if not a transaction.
    """
    provider, client = _get_provider_and_client()
    raw = ""

    try:
        if provider == "groq":
            raw = _parse_with_groq(client, email_body)
        else:
            raw = _parse_with_gemini(client, email_body)

        # Strip markdown code fences if wrapped with ```json ... ```
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)

        if not data.get("is_transaction", True):
            return None  # not a transaction email

        # Validate and fix category with fallback
        category = validate_category(data.get("category", ""))
        if category == "Other":
            category = classify_merchant(
                data.get("merchant", ""),
                data.get("description", ""),
            )
        data["category"] = category

        # Ensure amount is a float
        data["amount"] = float(data.get("amount", 0))

        return data

    except json.JSONDecodeError as e:
        print(f"⚠️  AI returned invalid JSON: {e}\nRaw output: {raw[:300]}")
        return None
    except Exception as e:
        print(f"⚠️  AI parsing error ({provider}): {e}")
        return None


if __name__ == "__main__":
    # Quick test with a sample email
    sample = """
    Dear Customer,

    INR 450.00 has been debited from your account ending 1234
    for a transaction at SWIGGY on 24-Oct-2026 at 13:10.
    Available Balance: INR 24,500.00.

    If not done by you, call 1800-XXX-XXXX.
    """
    result = parse_email_with_ai(sample)
    print("Parsed result:", json.dumps(result, indent=2))
