"""CaseLink web app. Use AI_API_KEY and APP_PASSWORD when hosted."""

from __future__ import annotations

import hmac
import json
import os
import time
from collections import deque
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, Response, jsonify, request, send_from_directory


ROOT = Path(__file__).resolve().parent
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.environ.get("AI_API_KEY", "").strip()
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
APP_USERNAME = os.environ.get("APP_USERNAME", "caselink")
IS_HOSTED = bool(os.environ.get("RENDER"))
if IS_HOSTED and (not APP_PASSWORD or not API_KEY):
    raise RuntimeError("Set APP_PASSWORD and AI_API_KEY in the hosting dashboard before starting CaseLink.")

app = Flask(__name__)
recent_ai_requests: deque[float] = deque()
MAX_AI_REQUESTS_PER_HOUR = 60


@app.before_request
def require_password():
    if not APP_PASSWORD:
        return None
    credentials = request.authorization
    if (
        credentials
        and hmac.compare_digest(credentials.username or "", APP_USERNAME)
        and hmac.compare_digest(credentials.password or "", APP_PASSWORD)
    ):
        return None
    return Response(
        "Sign in to use CaseLink.",
        401,
        {"WWW-Authenticate": 'Basic realm="CaseLink", charset="UTF-8"'},
    )


@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/api/status")
def status():
    return jsonify(
        key_configured=bool(API_KEY),
        key_entry_allowed=not IS_HOSTED and not API_KEY,
    )


@app.post("/api/configure-key")
def configure_key():
    global API_KEY
    if IS_HOSTED:
        return jsonify(error="The AI key is managed by the site administrator."), 403
    payload = request.get_json(silent=True) or {}
    key = payload.get("api_key", "")
    if not isinstance(key, str) or len(key.strip()) < 20:
        return jsonify(error="Paste the complete secret API key."), 400
    API_KEY = key.strip()
    return jsonify(ok=True)


@app.post("/api/extract-cases")
def extract_cases():
    global recent_ai_requests
    if not API_KEY:
        return jsonify(error="The site administrator has not configured the AI key."), 503

    now = time.time()
    while recent_ai_requests and now - recent_ai_requests[0] > 3600:
        recent_ai_requests.popleft()
    if len(recent_ai_requests) >= MAX_AI_REQUESTS_PER_HOUR:
        return jsonify(error="This app has reached its hourly AI request limit. Try again later."), 429

    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify(error="Please provide text to analyze."), 400
    if len(text) > 30_000:
        return jsonify(error="Please keep the text under 30,000 characters."), 413

    instructions = (
        "Extract legal court case captions explicitly mentioned in the supplied text. "
        "Return only a JSON object with a case_names array of strings. Preserve the "
        "caption spelling; include names in Party v. Party, In re, or Ex parte form "
        "only when clearly used as a case name. Do not invent or infer cases."
    )
    use_openrouter = API_KEY.startswith("sk-or-v1-")
    if use_openrouter:
        url = OPENROUTER_URL
        body = {
            "model": "openai/gpt-4.1-mini",
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1200,
        }
    else:
        url = OPENAI_URL
        body = {
            "model": "gpt-4.1-mini",
            "instructions": instructions,
            "input": text,
            "text": {"format": {"type": "json_object"}},
            "max_output_tokens": 1200,
        }

    try:
        upstream_request = Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(upstream_request, timeout=60) as response:
            result = json.loads(response.read())
        if use_openrouter:
            output = result["choices"][0]["message"]["content"]
        else:
            output = "".join(
                part.get("text", "")
                for item in result.get("output", [])
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
        parsed = json.loads(output)
        names = parsed.get("case_names", [])
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError("The model returned an unexpected result.")
        recent_ai_requests.append(now)
        return jsonify(case_names=names[:50])
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace"))
            message = detail.get("error", {}).get("message", "The AI provider rejected the request.")
        except (json.JSONDecodeError, AttributeError):
            message = "The AI provider rejected the request."
        return jsonify(error=f"AI provider error: {message[:400]}"), exc.code
    except (URLError, TimeoutError):
        return jsonify(error="Could not reach the AI provider. Please try again."), 502
    except (json.JSONDecodeError, ValueError, KeyError, IndexError, TypeError):
        return jsonify(error="Could not read the AI response. Please try again."), 502


if __name__ == "__main__":
    if IS_HOSTED and (not APP_PASSWORD or not API_KEY):
        raise SystemExit("Set APP_PASSWORD and AI_API_KEY in the hosting dashboard before deploying.")
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
        threaded=True,
    )
