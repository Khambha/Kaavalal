\# Kaavalal Backend Setup



\## Prerequisites



\- Python 3.11

\- MySQL Server

\- Git



\## 1. Open the backend directory



```powershell

cd backend

```



Run this from the repository root. If you are already inside the backend directory, skip this command.



\## 2. Create a virtual environment



```powershell

py -3.11 -m venv venv

```



\## 3. Activate the virtual environment



```powershell

.\\venv\\Scripts\\Activate.ps1

```



If PowerShell blocks activation, use the virtual environment's Python executable directly in the following commands.



\## 4. Install dependencies



```powershell

python -m pip install --upgrade pip

python -m pip install -r requirements.txt

```



\## 5. Configure environment variables



Create a local `.env` file by copying the example:



```powershell

Copy-Item .env.example .env

```



Edit `.env` and provide your own MySQL connection details and a securely generated `JWT\_SECRET\_KEY`.



Do not commit `.env` or share its secret values.



\## 6. Prepare the database



Ensure MySQL is running and the database configured in `.env` exists. Apply any database migrations or project-specific initialization steps required by the application.



\## 7. Start the backend



```powershell

python -m uvicorn app.main:app --reload

```



The API should be available at:



\- API: http://127.0.0.1:8000

\- Swagger documentation: http://127.0.0.1:8000/docs



\## Troubleshooting



\- If a Python module is missing, verify that the virtual environment is active and reinstall dependencies using `python -m pip install -r requirements.txt`.

\- If database connection fails, verify MySQL is running, the database exists, and `DATABASE\_URL` is correct.

\- If authentication configuration fails, verify that `JWT\_SECRET\_KEY` is set in `.env`.




## Password reset email (optional)

Citizen and rescuer accounts use the same password reset flow. To enable email delivery, set these values in `backend/.env` and restart the backend:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-Google-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=10
FRONTEND_BASE_URL=http://127.0.0.1:5173
```

For Gmail, create an app password for the sender account after enabling 2-Step Verification. Store it only in the ignored local `backend/.env`; do not put it in source control or chat. If SMTP is not configured, password reset requests tell everyone to contact the system administrator.

When SMTP is active, the request page always gives the same generic acknowledgment. An unknown email address receives no email and gets no reset token or usable reset form, so the endpoint does not reveal whether an account exists. Real accounts receive a single-use reset link that expires after 30 minutes.

## Live dashboard weather

The dashboard requests current conditions from OpenWeather for the selected district or LAC coordinates. Add `OPENWEATHER_API_KEY` to the ignored `backend/.env` file and restart the API. The key stays on the backend; the frontend does not call OpenWeather directly. When a LAC is selected, dashboard risk, hazard, and exposure values are loaded for that LAC record when available. Missing LAC-specific values are shown as unavailable instead of being filled from district defaults.
