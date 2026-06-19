# Deploy to Streamlit Cloud (free, public URL in 2 minutes)

## Step 1 — Push mvp/ to GitHub
Make sure your GitHub repo has the mvp/ folder committed and pushed.

## Step 2 — Go to Streamlit Cloud
1. Visit https://share.streamlit.io
2. Sign in with GitHub
3. Click **"New app"**

## Step 3 — Configure the app
Fill in these fields:
- **Repository**: `ambi2196-web/spotify-discovery-scrapper`
- **Branch**: `main`
- **Main file path**: `mvp/app.py`

Click **"Deploy"** — it will be live in ~90 seconds.

## Step 4 — Your live URL
You'll get a URL like:
`https://ambi2196-web-spotify-discovery-scrapper-mvpapp-xxxxx.streamlit.app`

Shorten it with https://bit.ly for the deck.

## Add Groq key as a secret (optional but recommended)
In Streamlit Cloud → App settings → Secrets, add:
```
GROQ_API_KEY = "gsk_your_key_here"
```
Then in app.py the key can be read from `st.secrets` instead of user input.
