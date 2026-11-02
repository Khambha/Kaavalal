# Shared role testing deployment

Kaavalal has two browser apps and one API. Deploy the citizen/responder app and the admin app as separate Vercel projects, and run the FastAPI backend on a persistent Python host connected to a managed MySQL database. Both Vercel projects must point to the same backend URL and the backend must point to the same database. This gives both testers shared accounts, incidents, shelter requests, alerts, and resource changes.

## 1. Deploy the API and database

Use a Python host that supports a long-running FastAPI service and persistent environment variables (for example Render). Use a managed MySQL instance with public network access restricted to the backend host when supported. Do not use a serverless function with the current backend: it runs schema changes during import and writes uploaded incident images to local disk.

Create the backend service from this repository with:

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set these backend environment variables in the host dashboard:

- `DATABASE_URL`: hosted MySQL URL, using the `mysql+pymysql://` scheme
- `JWT_SECRET_KEY`: a long random secret, distinct from the admin secret
- `ADMIN_JWT_SECRET_KEY`: a separate long random secret
- `FRONTEND_ORIGINS`: the comma-separated production origins of the citizen/responder and admin Vercel sites, without trailing slashes
- `FRONTEND_BASE_URL`: the citizen/responder Vercel URL, used in password reset links
- `CHATBOT_VECTOR_DIR`: `/tmp/kaavalal-chatbot-vectorstore` (or another writable temporary path)

Set optional integrations only if needed: `OPENWEATHER_API_KEY`, `GOOGLE_API_KEY`, and the `SMTP_*` variables. Never use values from a local `.env` file as production secrets without rotating them first. Visit `https://<api-host>/health` after deployment; it should return `{"status":"healthy"}`.

The current incident-photo endpoint reads and writes `backend/uploads/help_requests`. A local folder is not durable across service restarts and is not shared across instances. Before relying on photo attachments, change this storage to an object store such as S3 or Cloudinary and set its credentials in the backend. Core role workflows can be exercised without attachments.

## 2. Deploy the citizen and responder app to Vercel

Create a Vercel project from the repository and set its Root Directory to `frontend`. Vercel will use `frontend/vercel.json`. Add the build-time environment variable:

- `VITE_API_URL=https://<api-host>` (no trailing slash)

Deploy and confirm the root page loads. Citizen, responder, and incident views are all served by this app; sign in with separate user accounts on the two laptops to play different roles.

## 3. Deploy the admin app to Vercel

Create a second Vercel project from the same repository and set its Root Directory to `admin-frontend`. Add:

- `VITE_PLATFORM_API_URL=https://<api-host>` (no trailing slash)

Deploy and sign in with an admin account. Create or reset the admin account from the backend host's shell using the project's `python -m app.create_admin` command, then follow its prompts. Do not share the admin login if one tester is meant to act only as a citizen or responder.

## 4. Shared testing checklist

Open the citizen/responder Vercel URL on one laptop and the admin Vercel URL on the other. Register two separate citizen/responder users as needed; use a separate admin account for the admin console. Create a test incident or shelter request and confirm it appears in the appropriate admin/responder view. Both sites use the same API and database, so their data is shared. Changes generally appear on refresh; this setup does not add live push updates.

Vercel environment variables are embedded in the frontend at build time. Redeploy each site after changing its API URL. Never put database URLs, JWT secrets, email credentials, or third-party API secrets in either Vercel frontend project.
