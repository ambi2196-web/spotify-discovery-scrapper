"""
Spotify AI Discovery Companion — MVP
PM Fellowship Growth Case Study

Demonstrates why AI-native discovery beats traditional collaborative filtering.
Powered by Groq (Llama 3.3 70B) + real pipeline findings from 2,800+ user reviews.
"""

import streamlit as st
import os
import json
import random

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Discovery Companion · Spotify Concept",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #121212; }
    .stApp { background-color: #121212; color: #FFFFFF; }

    .hero { text-align: center; padding: 2rem 1rem 1rem; }
    .hero h1 { font-size: 2.4rem; font-weight: 800; color: #1DB954; margin-bottom: 0.3rem; }
    .hero p  { color: #B3B3B3; font-size: 1rem; }

    .card { background: #1e1e1e; border-radius: 14px; padding: 1.4rem 1.6rem; margin-bottom: 1rem; }
    .card-red  { border-left: 4px solid #ef4444; }
    .card-green{ border-left: 4px solid #1DB954; }
    .card-blue { border-left: 4px solid #3b82f6; }
    .card-gold { border-left: 4px solid #f59e0b; }

    .label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
             letter-spacing: 1.5px; margin-bottom: 0.4rem; }
    .label-red   { color: #ef4444; }
    .label-green { color: #1DB954; }
    .label-blue  { color: #3b82f6; }
    .label-gold  { color: #f59e0b; }

    .artist-chip { display: inline-block; background: #282828; border-radius: 20px;
                   padding: 4px 14px; margin: 3px; font-size: 0.85rem; }
    .quote { font-style: italic; color: #B3B3B3; border-left: 3px solid #333;
             padding-left: 1rem; margin: 0.8rem 0; font-size: 0.9rem; line-height: 1.6; }
    .stat-row { display: flex; gap: 1rem; margin: 1rem 0; }
    .stat-box { flex: 1; background: #282828; border-radius: 10px; padding: 1rem;
                text-align: center; }
    .stat-val { font-size: 1.6rem; font-weight: 800; color: #1DB954; }
    .stat-lbl { font-size: 0.7rem; color: #B3B3B3; text-transform: uppercase;
                letter-spacing: 0.5px; margin-top: 2px; }

    div[data-testid="stButton"] button {
        background-color: #1DB954; color: #000; font-weight: 700;
        border-radius: 30px; border: none; padding: 0.6rem 2rem;
        font-size: 1rem; width: 100%; cursor: pointer;
    }
    div[data-testid="stButton"] button:hover { background-color: #1ed760; }
</style>
""", unsafe_allow_html=True)

# ── Pipeline findings (from real scrapper output) ─────────────────────────────
PIPELINE_FINDINGS = {
    "reviews": 2847,
    "clusters": 59,
    "top_finding": "Relevance (Q4) dominates — users aren't trapped by lack of awareness, they're trapped in a feedback loop that amplifies existing taste instead of bridging to new music.",
    "key_quotes": [
        "I have literally seen the same 40 songs appear in my Discover Weekly for 8 months in a row.",
        "Every 'recommendation' Spotify gives me feels like an ad — I don't trust it anymore.",
        "I find more new artists on TikTok in a day than I do on Spotify in a month.",
        "I pressed 'don't play this' on the same song 20+ times. It keeps coming back.",
        "The algorithm peaked around 2019-2020 and has gotten noticeably worse each year since.",
        "I went through a 90s grunge phase and now I can't escape it. It's been 2 years.",
    ],
    "q4_themes": ["Same songs recycled across all playlists", "Taste crystallisation loop",
                  "New artists never surface", "Too safe — no musical risk-taking"],
    "q2_themes": ["Algorithm feels commercially driven", "Recs don't reflect my identity"],
    "q6_themes": ['"Don\'t play this" has no lasting effect', "No natural language taste input"],
}

TRADITIONAL_TEMPLATES = [
    "Because you listened to **{a1}**, you might like **{suggestion}** — a similar {genre} artist with comparable streams and BPM.",
    "Fans of **{a1}** also streamed **{suggestion}**.",
    "Based on your listening history, we think you'll enjoy **{suggestion}**.",
]

# ── Groq client ───────────────────────────────────────────────────────────────
@st.cache_resource
def get_groq_client(api_key: str):
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def call_groq(client, prompt: str, max_tokens: int = 900) -> str:
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.8,
    )
    return resp.choices[0].message.content.strip()


# ── Prompts ───────────────────────────────────────────────────────────────────
IDENTITY_PROMPT = """You are the Spotify AI Discovery Companion. A user has shared their music taste.

Their top artists: {artists}
Their music description: "{description}"

Write a short, vivid "Musical Identity Narrative" (3-4 sentences) that:
1. Names their core listening identity (give it a creative label like "Late-Night Texturalist" or "Melodic Escapist")
2. Identifies the emotional/sonic thread connecting their artists
3. Notes what they're READY to explore next (but haven't found yet)

Be specific, warm, and insightful. Avoid generic phrases. Max 80 words."""

BRIDGE_PROMPT = """You are the Spotify AI Discovery Companion. Based on a user's musical identity, suggest 3 artists they haven't heard yet.

User's identity: {identity}
Their current artists: {artists}

For each new artist, provide:
- Artist name (real, lesser-known artist)
- One-sentence "bridge reasoning" explaining the specific sonic/emotional link to their existing taste
- The discovery risk level: Safe | Stretch | Adventure

Format as JSON array:
[
  {{"artist": "Name", "bridge": "...", "risk": "Safe|Stretch|Adventure", "why_ai": "...one phrase explaining why only AI can make this connection..."}},
  ...
]

Be specific. Reference actual sonic qualities (tempo, timbre, lyrical themes). Avoid mainstream artists with 50M+ monthly listeners."""

CONTRAST_PROMPT = """In exactly 2 sentences, explain why the AI Discovery Companion recommendation above is fundamentally superior to Spotify's current collaborative filtering approach.

Focus on: what the AI understood that the algorithm couldn't. Be sharp and specific."""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 API Key")
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_...",
        help="Free at console.groq.com/keys",
    )
    if not groq_key:
        st.info("Enter your Groq key to activate the AI engine.")

    st.markdown("---")
    st.markdown("### 📊 Research Foundation")
    st.markdown(f"""
<div class="card card-green">
    <div class="label label-green">Pipeline Results</div>
    <div style="margin-top:0.5rem">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="color:#B3B3B3;font-size:0.85rem">Reviews analysed</span>
            <span style="font-weight:700;color:#1DB954">{PIPELINE_FINDINGS['reviews']:,}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="color:#B3B3B3;font-size:0.85rem">Themes found</span>
            <span style="font-weight:700;color:#1DB954">{PIPELINE_FINDINGS['clusters']}</span>
        </div>
        <div style="display:flex;justify-content:space-between">
            <span style="color:#B3B3B3;font-size:0.85rem">Sources</span>
            <span style="font-weight:700;color:#1DB954">3</span>
        </div>
    </div>
</div>

<div class="card card-red" style="margin-top:0.5rem">
    <div class="label label-red">Top User Pain</div>
    <p style="font-size:0.82rem;color:#B3B3B3;margin:0.4rem 0 0">{PIPELINE_FINDINGS['top_finding']}</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("**Real user quotes from pipeline:**")
    quote = st.session_state.get("current_quote", random.choice(PIPELINE_FINDINGS["key_quotes"]))
    st.session_state["current_quote"] = quote
    st.markdown(f'<div class="quote">"{quote}"</div>', unsafe_allow_html=True)
    if st.button("Next quote", key="next_quote"):
        st.session_state["current_quote"] = random.choice(PIPELINE_FINDINGS["key_quotes"])
        st.rerun()


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🎵 AI Discovery Companion</h1>
    <p>A Spotify concept MVP · Built on real user research from 2,847 reviews across App Store, Play Store & Reddit</p>
</div>
""", unsafe_allow_html=True)

# ── Problem statement banner ──────────────────────────────────────────────────
st.markdown("""
<div class="card card-red">
    <div class="label label-red">The Problem</div>
    <p style="margin:0.4rem 0 0;font-size:0.95rem">
    Spotify's algorithm is trapped in a <strong>feedback loop</strong> — it amplifies existing taste instead of bridging to new music.
    Users know discovery features exist. They just don't trust them, and can't escape their listening history.
    <strong style="color:#ef4444">This MVP demonstrates the fix.</strong>
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Input form ────────────────────────────────────────────────────────────────
st.markdown("### Step 1 — Tell us your taste")

col1, col2 = st.columns([1, 1])
with col1:
    artist1 = st.text_input("Top Artist #1", placeholder="e.g. Radiohead")
    artist2 = st.text_input("Top Artist #2", placeholder="e.g. Bon Iver")
    artist3 = st.text_input("Top Artist #3", placeholder="e.g. Four Tet")
with col2:
    description = st.text_area(
        "Describe your music taste in your own words",
        placeholder="e.g. I love music that feels cinematic and textured — stuff for late nights or long commutes. I'm drawn to melancholy but not sad, complex but not inaccessible.",
        height=145,
    )

artists_filled = [a for a in [artist1, artist2, artist3] if a.strip()]

if st.button("Generate my Discovery Companion →", key="generate"):
    if not groq_key:
        st.error("Please enter your Groq API key in the sidebar.")
        st.stop()
    if len(artists_filled) < 2:
        st.warning("Please enter at least 2 artists.")
        st.stop()
    if not description.strip():
        st.warning("Please add a short description of your taste.")
        st.stop()

    client = get_groq_client(groq_key)
    artists_str = ", ".join(artists_filled)

    st.markdown("---")
    st.markdown("### Step 2 — Traditional vs AI Recommendation")

    col_trad, col_ai = st.columns([1, 1])

    # Traditional recommendation
    with col_trad:
        genres = ["indie", "alternative", "electronic", "folk", "ambient"]
        suggestion = f"Similar {random.choice(genres)} artist"
        trad_text = random.choice(TRADITIONAL_TEMPLATES).format(
            a1=artists_filled[0],
            suggestion=suggestion,
            genre=random.choice(genres),
        )
        st.markdown(f"""
<div class="card card-red">
    <div class="label label-red">❌ Traditional Collaborative Filtering</div>
    <p style="color:#B3B3B3;font-size:0.85rem;margin:0.5rem 0">
        Based on: stream counts + co-listen patterns
    </p>
    <div style="background:#282828;border-radius:8px;padding:1rem;margin-top:0.5rem">
        <p style="font-size:0.95rem;margin:0">{trad_text}</p>
    </div>
    <div style="margin-top:1rem">
        <p style="font-size:0.78rem;color:#6b7280">What the algorithm can't do:</p>
        <p style="font-size:0.82rem;color:#B3B3B3">
        • Can't read the <em>emotional thread</em> across your artists<br>
        • Doesn't know your current discovery mood<br>
        • Trapped by your past behaviour<br>
        • No explanation for why it chose this
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

    # AI recommendation
    with col_ai:
        with st.spinner("AI is reading your musical identity…"):
            try:
                identity = call_groq(
                    client,
                    IDENTITY_PROMPT.format(artists=artists_str, description=description),
                    max_tokens=200,
                )
                st.session_state["identity"] = identity

                bridge_raw = call_groq(
                    client,
                    BRIDGE_PROMPT.format(identity=identity, artists=artists_str),
                    max_tokens=700,
                )
                # Parse JSON from response
                import re
                json_match = re.search(r'\[.*\]', bridge_raw, re.DOTALL)
                if json_match:
                    recs = json.loads(json_match.group())
                else:
                    recs = []

                contrast = call_groq(
                    client,
                    CONTRAST_PROMPT,
                    max_tokens=120,
                )

                st.markdown(f"""
<div class="card card-green">
    <div class="label label-green">✅ AI Discovery Companion</div>
    <p style="color:#B3B3B3;font-size:0.85rem;margin:0.5rem 0">
        Based on: sonic identity + emotional thread + discovery readiness
    </p>
    <div style="background:#0d1f14;border-radius:8px;padding:1rem;border:1px solid #1DB95433;margin-top:0.5rem">
        <p style="font-size:0.78rem;color:#1DB954;font-weight:700;text-transform:uppercase;letter-spacing:1px">Your Musical Identity</p>
        <p style="font-size:0.92rem;margin:0.4rem 0 0;line-height:1.6">{identity}</p>
    </div>
</div>
""", unsafe_allow_html=True)

                st.markdown("#### Your 3 Discovery Bridges")
                risk_colours = {"Safe": "#1DB954", "Stretch": "#f59e0b", "Adventure": "#8b5cf6"}

                for rec in recs[:3]:
                    risk = rec.get("risk", "Stretch")
                    colour = risk_colours.get(risk, "#f59e0b")
                    st.markdown(f"""
<div class="card" style="border-left:4px solid {colour};margin-bottom:0.7rem">
    <div style="display:flex;justify-content:space-between;align-items:center">
        <strong style="font-size:1.05rem">{rec.get('artist','')}</strong>
        <span style="background:{colour}22;color:{colour};font-size:0.7rem;font-weight:700;
              padding:3px 10px;border-radius:10px;text-transform:uppercase">{risk}</span>
    </div>
    <p style="font-size:0.85rem;color:#B3B3B3;margin:0.5rem 0 0.3rem">🔗 {rec.get('bridge','')}</p>
    <p style="font-size:0.78rem;color:#6b7280;margin:0">
        <em>Why only AI: {rec.get('why_ai','')}</em>
    </p>
</div>
""", unsafe_allow_html=True)

                st.markdown(f"""
<div class="card card-blue" style="margin-top:1rem">
    <div class="label label-blue">Why AI wins</div>
    <p style="font-size:0.88rem;margin:0.4rem 0 0;line-height:1.6">{contrast}</p>
</div>
""", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Groq API error: {e}")
                st.info("Check your API key in the sidebar and try again.")

    # How it works
    st.markdown("---")
    st.markdown("### How the AI Discovery Companion works")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
<div class="card card-green">
    <div class="label label-green">1. Identity Layer</div>
    <p style="font-size:0.85rem;color:#B3B3B3;margin:0.4rem 0 0">
    Reads the emotional and sonic thread <em>across</em> your artists — not just genre tags or BPM.
    Names your listening identity so recommendations feel personal.
    </p>
</div>
""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
<div class="card card-blue">
    <div class="label label-blue">2. Bridge Reasoning</div>
    <p style="font-size:0.85rem;color:#B3B3B3;margin:0.4rem 0 0">
    For each new artist, explains the <em>specific</em> sonic or emotional link to your taste.
    Not "fans also liked" — a genuine explanation you can evaluate.
    </p>
</div>
""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
<div class="card card-gold">
    <div class="label label-gold">3. Discovery Readiness</div>
    <p style="font-size:0.85rem;color:#B3B3B3;margin:0.4rem 0 0">
    Calibrates how far to stretch — Safe keeps you close, Adventure takes you somewhere genuinely new.
    You stay in control of the risk level.
    </p>
</div>
""", unsafe_allow_html=True)

    # Connection to Spotify's monetisation
    st.markdown("""
<div class="card" style="border:1px solid #333;margin-top:1rem">
    <div class="label" style="color:#f59e0b">Business Model Connection</div>
    <p style="font-size:0.88rem;color:#B3B3B3;margin:0.4rem 0 0;line-height:1.7">
    Bridge recommendations naturally surface <strong>emerging artists</strong> — the exact segment that pays
    for <strong>Discovery Mode</strong> (Spotify's royalty-reducing promotion tool). Better discovery =
    more artists willing to pay for Discovery Mode placement = higher margin for Spotify.
    The AI Companion aligns user value with Spotify's monetisation, rather than working against it.
    </p>
</div>
""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<p style="text-align:center;color:#6b7280;font-size:0.78rem">
    AI Discovery Companion · PM Fellowship Growth Case Study · Spotify Concept MVP<br>
    Built on findings from 2,847 real user reviews · Powered by Groq Llama 3.3 70B
</p>
""", unsafe_allow_html=True)
