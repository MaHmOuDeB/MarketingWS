# ===== app.py =====

import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from typing import Optional, Dict, Any, List

# ─── Configuration ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable")

client = OpenAI(api_key=API_KEY)
app = Flask(__name__)
CORS(app)

# ─── Campaign templates and platform limits ────────────────────────────────────
templates: Dict[str, str] = {
    "social_media": (
        "Create a {tone} social media post for {platform} about {topic}. "
        "Start with a thought-provoking question or statistic (1 sentence), "
        "highlight the main benefit (1 sentence), add a clear call to action, "
        "and finish with 2-3 relevant hashtags."
    ),
    "email_marketing": (
        "Write a {tone} email promoting {topic} to {audience}. "
        "Use a compelling subject line (under 60 characters), open with a personalized greeting, "
        "highlight two key benefits in separate paragraphs, close with a strong call to action and professional sign-off, "
        "and include a P.S. reminding the reader to click the link."
    ),
    "ppc_ads": (
        "Produce a {tone} PPC ad for {platform} about {topic} (max 90 characters). "
        "Write a persuasive headline (under 30 characters), include a one-line value proposition, "
        "and end with a direct call to action—do not wrap the copy in extra quotes."
    ),
    "content_marketing": (
        "Draft a {tone} blog introduction for {topic}, aimed at {audience}. "
        "Begin with an engaging statistic or question, outline three key points as a bulleted list, "
        "and end with a transition sentence into the main article."
    ),
    "customer_retention": (
        "Create a {tone} customer re-engagement message about {topic} for {audience}. "
        "Start by acknowledging their past engagement, mention an exclusive incentive (e.g. 20% off), "
        "close with a friendly reminder of how they can take the next step, and use one consistent emoji (e.g. 🌟)."
    ),
    "seasonal_campaigns": (
        "Write a {tone} seasonal marketing campaign post for {platform} about {topic}. "
        "Open with a festive greeting, tie the message to the season's themes, "
        "highlight one special offer or feature, and include one season-themed hashtag."
    ),
    "product_launch": (
        "Draft a {tone} product launch announcement for {platform} about {topic}. "
        "Lead with a powerful headline, describe three standout features (one per sentence), "
        "and finish with a clear invitation using the placeholder <registration_link>."
    ),
    "crisis_management": (
        "Compose a {tone} crisis response message for {platform} about {topic}. "
        "In two sentences: acknowledge the issue, express genuine empathy, outline corrective steps, "
        "and reassure the audience of your commitment."
    ),
}

PLATFORM_LIMITS: Dict[str, int] = {
    "linkedin": 1300,
    "twitter": 280,
    "facebook": 63206,
}

# ─── Helper Functions ──────────────────────────────────────────────────────────

def build_system_message(language: str, user_prompt: Optional[str]) -> Dict[str, str]:
    default = (
        f"All outputs must be in {language}. "
        "You are a world-class marketing copywriter. "
        "Produce concise, on-topic, well-structured marketing copy."
        "Make sure to take into consideration what works best on chosen campaign type, platforms, and audience whenever they are provided."
        "You don't have to follow the marketing campaigns template examples given to the letter, you can inovate and make the best out of your marketing knowledge & expertise."
        "Follow the details and instructions the user is putting in the following lines to the letter(if any) along with what is mentioned above . Otherwise execute what is given above."
    )
    if user_prompt:
        content = f"{default}\n\nAdditional instructions: {user_prompt}"
    else:
        content = default
    return {"role": "system", "content": content}

def build_user_message(template: str, params: Dict[str, str], language: str,
                       feedback: Optional[str]) -> Dict[str, str]:
    base = template.format(**params)
    content = f"{base} Please write this in {language}."
    if feedback:
        content += f" Feedback: '{feedback}'. Revise accordingly."
    return {"role": "user", "content": content}

def call_openai(messages: List[Dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.6,
        max_tokens=180,
        top_p=0.9,
        frequency_penalty=0.2,
        presence_penalty=0.1
    )
    return response.choices[0].message.content.strip().strip('"').strip("'")

# ─── Main Logic ────────────────────────────────────────────────────────────────

def generate_content(data: Dict[str, Any]) -> str:
    ct = data["campaign_type"]
    params = {
        "tone": data.get("tone", ""),
        "platform": data.get("platform", ""),
        "topic": data.get("topic", ""),
        "audience": data.get("audience", ""),
    }
    language = data.get("language", "English")
    feedback = data.get("feedback")
    user_sys = data.get("system_prompt")

    template = templates.get(ct)
    if not template:
        raise ValueError(f"Unsupported campaign_type: {ct}")

    sys_msg = build_system_message(language, user_sys)
    user_msg = build_user_message(template, params, language, feedback)
    messages = [sys_msg, user_msg]

    content = call_openai(messages)
    limit = PLATFORM_LIMITS.get(params["platform"].lower())
    if limit:
        content = content[:limit]
    return content

# ─── Flask Routes ─────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        payload = request.json or {}
        result = generate_content(payload)
        return jsonify({"generated_content": result})
    except Exception as e:
        logging.exception("Generation error")
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    # bind to 0.0.0.0 so Docker can route incoming traffic
    app.run(host='0.0.0.0', debug=False, port=5000)