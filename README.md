# GrokAi — Render-ready version

Changes:
- Telegram webhook instead of polling
- Render binds to 0.0.0.0:$PORT
- admin uses Telegram ID + password, no Gmail
- PostgreSQL uses external DATABASE_URL
- xAI Grok 4.5 / web search / image / STT / TTS

Required Render environment variables:
TELEGRAM_BOT_TOKEN
XAI_API_KEY
DATABASE_URL
ADMIN_TELEGRAM_ID
ADMIN_PASSWORD
WEBHOOK_SECRET

Render supplies PORT and RENDER_EXTERNAL_URL automatically.
Never commit real secrets to GitHub.
