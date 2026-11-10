import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-development-secret")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "Missing Supabase settings. Add SUPABASE_URL and SUPABASE_SECRET_KEY to your .env file."
    )

# This server-side key must never be placed in frontend JavaScript or committed to Git.
supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

CATEGORIES = [
    "Food", "Travel", "Shopping", "Education",
    "Bills", "Health", "Entertainment", "Other"
]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def get_user_expenses(user_id, start_date=None, end_date=None):
    query = (
        supabase.table("expenses")
        .select("id, title, amount, category, expense_date")
        .eq("user_id", user_id)
    )
    if start_date:
        query = query.gte("expense_date", start_date)
    if end_date:
        query = query.lte("expense_date", end_date)
    return query.order("expense_date", desc=True).order("id", desc=True).execute().data or []


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and use a password with at least 8 characters.", "error")
            return render_template("register.html")

        try:
            existing = (
                supabase.table("users")
                .select("id")
                .eq("email", email)
                .limit(1)
                .execute()
                .data
            )
            if existing:
                flash("That email is already registered. Try signing in.", "error")
                return render_template("register.html")

            result = supabase.table("users").insert({
                "name": name,
                "email": email,
                "password_hash": generate_password_hash(password)
            }).execute()

            if not result.data:
                raise RuntimeError("Supabase did not return the created user.")

            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))
        except Exception:
            app.logger.exception("Supabase registration failed")
            flash("Could not create your account. Check your Supabase connection and database setup.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            result = (
                supabase.table("users")
                .select("id, name, email, password_hash")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            user = result.data[0] if result.data else None

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(url_for("dashboard"))
        except Exception:
            app.logger.exception("Supabase login failed")
            flash("Unable to connect to the database. Check your Supabase settings.", "error")
            return render_template("login.html")

        flash("Incorrect email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    month = today.strftime("%Y-%m")
    month_start = today.replace(day=1).isoformat()
    next_month_start = (
        (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    ).isoformat()
    month_end = (date.fromisoformat(next_month_start) - timedelta(days=1)).isoformat()
    user_id = session["user_id"]

    try:
        monthly_expenses = get_user_expenses(user_id, month_start, month_end)
        recent_expenses = get_user_expenses(user_id)[:10]

        spent = sum((Decimal(str(row["amount"])) for row in monthly_expenses), Decimal("0"))

        budget_result = (
            supabase.table("budgets")
            .select("amount")
            .eq("user_id", user_id)
            .eq("month", month)
            .limit(1)
            .execute()
        )
        budget_row = budget_result.data[0] if budget_result.data else None
        budget = Decimal(str(budget_row["amount"])) if budget_row else Decimal("0")

        category_totals = {}
        for row in monthly_expenses:
            category = row["category"]
            category_totals[category] = category_totals.get(category, Decimal("0")) + Decimal(str(row["amount"]))
        category_rows = [
            {"category": category, "total": float(total)}
            for category, total in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        ]

        expenses = [
            {**row, "amount": float(Decimal(str(row["amount"])))}
            for row in recent_expenses
        ]
        remaining = budget - spent
        percent = min(100, round(float(spent / budget * 100), 1)) if budget > 0 else 0

        return render_template(
            "dashboard.html",
            expenses=expenses,
            spent=float(spent),
            budget=float(budget),
            remaining=float(remaining),
            percent=percent,
            categories=category_rows,
            today=today.isoformat(),
            month=month
        )
    except Exception:
        app.logger.exception("Supabase dashboard query failed")
        flash("Could not load your dashboard. Check your Supabase tables and connection.", "error")
        return render_template(
            "dashboard.html", expenses=[], spent=0, budget=0, remaining=0,
            percent=0, categories=[], today=today.isoformat(), month=month
        )


@app.route("/expense/add", methods=["POST"])
@login_required
def add_expense():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Other")
    expense_date = request.form.get("expense_date", "")

    try:
        amount = Decimal(request.form.get("amount", "0"))
        if amount <= 0 or not amount.is_finite():
            raise InvalidOperation
        parsed_date = date.fromisoformat(expense_date)
    except (InvalidOperation, ValueError):
        flash("Enter a valid positive amount and date.", "error")
        return redirect(url_for("dashboard"))

    if not title or category not in CATEGORIES:
        flash("Enter a title and choose a valid category.", "error")
        return redirect(url_for("dashboard"))

    try:
        supabase.table("expenses").insert({
            "user_id": session["user_id"],
            "title": title,
            "amount": str(amount),
            "category": category,
            "expense_date": parsed_date.isoformat()
        }).execute()
        flash("Expense added successfully.", "success")
    except Exception:
        app.logger.exception("Supabase expense insert failed")
        flash("Could not save the expense. Please check your database setup.", "error")

    return redirect(url_for("dashboard"))


@app.route("/expense/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    try:
        (
            supabase.table("expenses")
            .delete()
            .eq("id", expense_id)
            .eq("user_id", session["user_id"])
            .execute()
        )
        flash("Expense deleted.", "success")
    except Exception:
        app.logger.exception("Supabase expense delete failed")
        flash("Could not delete the expense.", "error")
    return redirect(url_for("dashboard"))


@app.route("/budget", methods=["POST"])
@login_required
def set_budget():
    month = date.today().strftime("%Y-%m")
    try:
        amount = Decimal(request.form.get("amount", "0"))
        if amount <= 0 or not amount.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        flash("Enter a valid budget greater than zero.", "error")
        return redirect(url_for("dashboard"))

    try:
        supabase.table("budgets").upsert({
            "user_id": session["user_id"],
            "month": month,
            "amount": str(amount)
        }, on_conflict="user_id,month").execute()
        flash("Monthly budget saved.", "success")
    except Exception:
        app.logger.exception("Supabase budget save failed")
        flash("Could not save the budget. Please check your database setup.", "error")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
