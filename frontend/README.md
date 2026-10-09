# Kaavalal Frontend

React and Vite frontend for the Kaavalal Kerala disaster-management dashboard.

## Requirements

* Node.js
* npm
* Kaavalal FastAPI backend

## Setup

From the project root, run:

```powershell
cd frontend
npm install
npm run dev
```

The frontend connects to the FastAPI backend at `http://127.0.0.1:8000`.

Make sure the backend is running before testing API-connected features.

## Production Build

```powershell
npm run build
```

## Data Note

Some dashboard values are sample/demo data. They should not be treated as official live measurements or validated disaster-risk predictions.
