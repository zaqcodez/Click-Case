# CaseLink

CaseLink turns legal case names in text into links to Justia, Oyez, or Westlaw. It can use OpenAI or OpenRouter to find case names.

## Run locally

1. Install Python 3.
2. In Terminal, change into this folder and run `python3 -m pip install -r requirements.txt`.
3. Run `python3 app.py`.
4. Open `http://127.0.0.1:8000` and enter your AI provider key in the app.

## Publish a password-protected copy on Render

The included `render.yaml` describes a small Render web service. It keeps the provider key and site password in Render's private environment settings. Visitors need the shared site username and password. AI requests use the site owner's provider key and count toward that account's usage.

1. Create a private GitHub repository and upload the files in this folder. Do not upload API keys or `.env` files.
2. In Render, create a Blueprint and connect that GitHub repository. Render reads `render.yaml` and asks for the secret values.
3. Set `AI_API_KEY` to your OpenRouter or OpenAI API key. Set `APP_PASSWORD` to a strong password you will share only with intended users. The username is `caselink`.
4. Deploy. Render will provide an `onrender.com` address. Share that URL and the username/password with your group.

The hosted version hides the API-key entry box and reads the key from the server environment. It limits AI requests to 60 per hour per running instance. The app sends text to the selected AI provider when someone clicks **Find with AI**. Add a spending limit to your provider key before sharing the site.

The Render free web service can spin down after inactivity, so the first visit after a quiet period may take longer. Review Render's current [pricing](https://render.com/pricing) and [free-service behavior](https://render.com/docs/faq) before deploying.
