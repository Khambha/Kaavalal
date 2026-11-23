# Thunai chatbot operations

## Readiness and diagnosis

Open `GET /api/chat/status` on the Kaavalal API. It reports database connectivity, provider name/model and whether a credential is configured, whether the `kaavalal_kb` vector collection has embeddings, and the row counts for KSDMA reference tables. Credential presence does not verify the key, quota, model name, or provider network access.

If a chat reply says the AI service is unavailable, inspect the backend log for `Thunai agent failed (provider=...)`. Do not paste API keys or `.env` contents into reports. Browser network errors usually mean the configured API URL is unreachable or CORS does not allow the site origin.

## Setup

- Install the packages in `backend/requirements-chatbot.txt` in the same Python environment that runs Kaavalal.
- Set `CHATBOT_PROVIDER`, its matching provider credential, and `CHATBOT_MODEL` in the backend environment. Restart the API after changing them.
- Set frontend `VITE_API_URL` to the deployed FastAPI base URL. In local development, `http://127.0.0.1:8000` is the default.
- Keep `CHATBOT_KSDMA_DATA_READY=false` until reference records have been imported into Kaavalal's database and the status endpoint reports nonzero rows for the relevant tables. A success report alone is not proof that the running database contains those rows.

## Safety knowledge index

The source documents live in `backend/app/chatbot/knowledge`. After editing them, rebuild the local Chroma index from the backend directory:

```powershell
cd backend
python -m app.chatbot.ingest
```

The embedding model must be installed/downloadable in the API environment. Deploy the rebuilt `chatbot_vectorstore` with the backend, or run ingestion as a deployment step that writes to the configured persistent volume. The status endpoint must report the knowledge index as `ready`.

## Data semantics

- Risk answers call the current weather/risk engine. An experimental 0–100 index is not a calibrated disaster probability; the assistant must label it as an index and give its update time and confidence meaning.
- Verified historical disaster events are not currently connected to the chatbot. Training or synthetic rows must not be described as confirmed events.
- KSDMA camp, hospital, kiosk, and taluk records are reference data. A listed camp is not confirmation that it is open, and the hospital survey may be old.
- Thunai is informational. Official warnings and emergency responders take precedence; call 112 for immediate danger.
