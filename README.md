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



