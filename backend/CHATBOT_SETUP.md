# Thunai chatbot setup

Thunai is available in the Citizen Portal and the Responder Feed. Its API is mounted at `/api/chat` and uses Kaavalal's existing MySQL database, SQLAlchemy session, and JWT tokens.

## First run

1. From `backend/`, install the backend dependencies:

   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   The chatbot dependencies include a multilingual embedding model and can take longer to install than the existing API requirements.

2. Add these settings to `backend/.env` and set a Google AI Studio key:

   ```dotenv
   CHATBOT_PROVIDER=gemini
   CHATBOT_MODEL=gemini-2.5-flash
   GOOGLE_API_KEY=your-key
   CHATBOT_KB_DIR=./app/chatbot/knowledge
   CHATBOT_VECTOR_DIR=./chatbot_vectorstore
   CHATBOT_RATE_LIMIT=20/minute
   CHATBOT_KSDMA_DATA_READY=false
   ```

   Keep the key private. Chat messages are sent to the configured model provider when an AI response is needed. Emergency rules and the emergency contact list are handled locally.

3. From `backend/`, build the safety-guide search index once:

   ```powershell
   python -m app.chatbot.ingest
   ```

   This downloads the multilingual embedding model and creates `chatbot_vectorstore/`.

4. Start the API as usual:

   ```powershell
   uvicorn app.main:app --reload
   ```

The database tables for chat history and feedback are created by the existing `Base.metadata.create_all` startup path. Thunai is read-only and cannot submit SOS requests or change responder assignments.

## KSDMA reference data

The linked chatbot repository does not contain the source datasets needed for camp, water-kiosk, hospital, and taluk-contact imports. These lookups are intentionally marked unavailable until the datasets are imported; the assistant will not interpret empty tables as proof that no services exist. After placing the source files in a folder, import them with `python -m app.chatbot.import_ksdma --src <folder-with-source-files>`, set `CHATBOT_KSDMA_DATA_READY=true` in `backend/.env`, and restart the API.
