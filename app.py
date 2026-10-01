import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.path.join(os.path.dirname(__file__), "food.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('donor', 'ngo')),
    area TEXT,
    phone TEXT
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL REFERENCES users(id),
    food_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    servings INTEGER NOT NULL,
    expiry TEXT NOT NULL,
    address TEXT NOT NULL,
    area TEXT NOT NULL,
    contact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Available',
    claimed_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);
"""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


def now_str():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


# ---------- auth helpers ----------
def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You don't have access to that page.", "danger")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------- public pages ----------
@app.route("/")
def index():
    db = get_db()
    stats = db.execute(
        """SELECT COALESCE(SUM(servings), 0) AS meals,
                  COALESCE(SUM(quantity_kg), 0) AS kg,
                  COUNT(*) AS n
           FROM listings WHERE status = 'Picked up'"""
    ).fetchone()
    active = db.execute(
        "SELECT COUNT(*) FROM listings WHERE status = 'Available' AND expiry > ?",
        (now_str(),),
    ).fetchone()[0]
    return render_template("index.html", stats=stats, active=active)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        if not all(f.get(k, "").strip() for k in ("name", "email", "password", "role", "area")):
            flash("Please fill in all required fields.", "danger")
            return render_template("register.html")
        if f["role"] not in ("donor", "ngo"):
            flash("Invalid role.", "danger")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash, role, area, phone) VALUES (?,?,?,?,?,?)",
                (f["name"].strip(), f["email"].strip().lower(),
                 generate_password_hash(f["password"]), f["role"],
                 f["area"].strip(), f.get("phone", "").strip()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "danger")
            return render_template("register.html")
        flash("Registered! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("donor_dashboard" if user["role"] == "donor" else "ngo_dashboard"))
        flash("Wrong email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- donor ----------
@app.route("/donor", methods=["GET", "POST"])
@login_required("donor")
def donor_dashboard():
    db = get_db()
    if request.method == "POST":
        f = request.form
        try:
            qty = float(f["quantity_kg"])
            servings = int(f["servings"])
            if qty <= 0 or servings <= 0:
                raise ValueError
            if f["expiry"] <= now_str():
                flash("Expiry time must be in the future.", "danger")
                return redirect(url_for("donor_dashboard"))
            db.execute(
                """INSERT INTO listings
                   (donor_id, food_type, quantity_kg, servings, expiry, address, area, contact, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (session["user_id"], f["food_type"].strip(), qty, servings, f["expiry"],
                 f["address"].strip(), f["area"].strip(), f["contact"].strip(), now_str()),
            )
            db.commit()
            flash("Food listing posted!", "success")
        except (ValueError, KeyError):
            flash("Please enter valid quantity, servings and expiry.", "danger")
        return redirect(url_for("donor_dashboard"))

    rows = db.execute(
        """SELECT l.*, u.name AS ngo_name, u.phone AS ngo_phone
           FROM listings l LEFT JOIN users u ON u.id = l.claimed_by
           WHERE l.donor_id = ? ORDER BY l.id DESC""",
        (session["user_id"],),
    ).fetchall()
    return render_template("donor_dashboard.html", listings=rows, now=now_str())


# ---------- NGO ----------
@app.route("/ngo")
@login_required("ngo")
def ngo_dashboard():
    db = get_db()
    area = request.args.get("area", "").strip()
    query = """SELECT l.*, u.name AS donor_name FROM listings l
               JOIN users u ON u.id = l.donor_id
               WHERE l.status = 'Available' AND l.expiry > ?"""
    params = [now_str()]
    if area:
        query += " AND LOWER(l.area) LIKE ?"
        params.append(f"%{area.lower()}%")
    available = db.execute(query + " ORDER BY l.expiry ASC", params).fetchall()
    mine = db.execute(
        """SELECT l.*, u.name AS donor_name FROM listings l
           JOIN users u ON u.id = l.donor_id
           WHERE l.claimed_by = ? ORDER BY l.id DESC""",
        (session["user_id"],),
    ).fetchall()
    return render_template("ngo_dashboard.html", available=available, mine=mine, area=area)


@app.route("/claim/<int:listing_id>", methods=["POST"])
@login_required("ngo")
def claim(listing_id):
    db = get_db()
    # single atomic UPDATE so two NGOs can't claim the same listing
    cur = db.execute(
        """UPDATE listings SET status = 'Claimed', claimed_by = ?
           WHERE id = ? AND status = 'Available' AND expiry > ?""",
        (session["user_id"], listing_id, now_str()),
    )
    db.commit()
    flash("Claimed! Contact the donor for pickup." if cur.rowcount
          else "Sorry, this listing is no longer available.",
          "success" if cur.rowcount else "danger")
    return redirect(url_for("ngo_dashboard"))


@app.route("/pickup/<int:listing_id>", methods=["POST"])
@login_required("ngo")
def pickup(listing_id):
    db = get_db()
    cur = db.execute(
        "UPDATE listings SET status = 'Picked up' WHERE id = ? AND claimed_by = ? AND status = 'Claimed'",
        (listing_id, session["user_id"]),
    )
    db.commit()
    flash("Marked as picked up. Thank you!" if cur.rowcount else "Could not update.",
          "success" if cur.rowcount else "danger")
    return redirect(url_for("ngo_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
