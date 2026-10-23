# Kaavalal Admin Site

This is a separate private React/Vite frontend. It does not provide public signup and uses separate administrator accounts managed by the platform API.

## Local development

1. Configure `backend/.env` with `DATABASE_URL`, `JWT_SECRET_KEY`, `ADMIN_JWT_SECRET_KEY`, and `ADMIN_APP_ORIGIN=http://localhost:5175`.
2. From `backend`, create the first administrator using `python -m app.create_admin`.
3. Start the existing FastAPI application from `backend` using `python -m uvicorn app.main:app --reload`.
4. From `admin-frontend`, copy `.env.example` to `.env`, install dependencies with `npm install`, then run `npm run dev`.
5. Open `http://localhost:5175` and sign in with the administrator account.

For deployment, host this frontend behind private access controls (such as an organization VPN or access gateway), set `VITE_PLATFORM_API_URL` to the platform API, and set `ADMIN_APP_ORIGIN` to the deployed admin site origin. Keep the admin JWT secret separate from the platform JWT secret.
