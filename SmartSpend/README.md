# SmartSpend — Supabase version

SmartSpend is a personal expense and monthly budget tracker built with Flask,
HTML, CSS, JavaScript, and Supabase PostgreSQL.

## Features
- User registration and login (passwords are hashed by Werkzeug)
- Add and delete personal expenses
- Expense categories
- Monthly budget management
- Dashboard with monthly spending, remaining budget, and category totals
- Supabase cloud PostgreSQL database

## 1. Create a Supabase project
1. Open https://supabase.com/dashboard and create a project.
2. Choose a database password and save it securely.
3. Wait until the project is ready.
4. In Project Settings -> API (or the Connect panel), copy the Project URL.
5. Copy the server-side Secret key (starts with `sb_secret_`) from the API keys area.
   If your project only shows legacy keys, use the `service_role` key as the server-side
   key. Never use the `anon`/publishable key for this custom Flask-session setup.
6. Never put the secret/service-role key in HTML, JavaScript, or a public repository.

## 2. Create the database tables
1. In Supabase, open SQL Editor.
2. Choose New query.
3. Open `database/db.sql` from this project and copy its complete contents.
4. Paste it into SQL Editor and click Run.
5. Confirm that `users`, `expenses`, and `budgets` appear under Table Editor.

## 3. Configure the Flask app on Windows
Open the SmartSpend folder in VS Code. In its terminal run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, run this and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Open `.env` and replace the sample values:

```env
SECRET_KEY=use-a-long-random-value
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=sb_secret_your_server_side_secret_key
```

Use the actual Project URL and server-side Secret key from your Supabase project.
Do not add quotes around the values. Do not share the `.env` file.

## 4. Run SmartSpend

```powershell
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Important security note
This starter version keeps the existing custom Flask login/session system and
uses the Supabase server-side secret key only inside Flask. That key bypasses
Row Level Security, so the Flask server must enforce user ownership on every
database operation (the app filters expense and budget operations by the logged-in
user ID). Do not expose this key to the browser or deploy Flask with debug mode
enabled. For a production public app, move authentication to Supabase Auth and
use per-user Row Level Security policies.

## Existing SQLite data
This version starts with empty Supabase tables. Your old local SQLite file is
not automatically copied. Export/migrate the old `users`, `expenses`, and
`budgets` data separately if you need to preserve existing records.

