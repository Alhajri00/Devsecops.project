import os
import sqlite3
from datetime import timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change_me_later"
app.permanent_session_lifetime = timedelta(minutes=30)

# Paths
basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, "lostfound.db")

UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# موجود لكن ما نستخدمه هنا كحماية (نذكره في النسخة الآمنة)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL,
            description TEXT,
            image TEXT
        );
        """
    )

    cur = conn.execute("SELECT COUNT(*) AS c FROM items;")
    count = cur.fetchone()["c"]
    if count == 0:
        conn.executemany(
            "INSERT INTO items (type, title, location, status, description, image) VALUES (?, ?, ?, ?, ?, ?);",
            [
                ("Lost", "Student ID Card", "Building A", "Pending", "Blue ID card with photo", None),
                ("Found", "AirPods Case", "Cafeteria", "Pending", "White case with small scratch", None),
            ],
        )
    conn.commit()
    conn.close()


init_db()

# Weak auth: hardcoded, plaintext, simple passwords
USERS = {
    "fatima": {"password": "stud123", "role": "student"},
    "ali": {"password": "stud123", "role": "student"},
    "salim": {"password": "stud123", "role": "student"},
    "office_admin": {"password": "secure123", "role": "admin"},
}


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    username = session.get("username")
    return render_template("dashboard.html", role=role, username=username)


@app.route("/items")
def items():
    if "username" not in session:
        return redirect(url_for("login"))

    role = session.get("role")
    q = request.args.get("q", "").strip()

    conn = get_db()

    if q:
        # ❌ Insecure SQL: SQL Injection via string concatenation
        sql = (
            "SELECT * FROM items "
            "WHERE title LIKE '%" + q + "%' "
            "OR description LIKE '%" + q + "%' "
            "ORDER BY id;"
        )
        rows = conn.execute(sql).fetchall()
    else:
        rows = conn.execute("SELECT * FROM items ORDER BY id;").fetchall()

    conn.close()

    return render_template("items.html", items=rows, role=role, q=q)


@app.route("/report", methods=["GET", "POST"])
def report():
    if "username" not in session:
        return redirect(url_for("login"))

    role = session.get("role")
    error = None

    if request.method == "POST":
        item_type = request.form.get("item_type", "Lost")
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        image_file = request.files.get("image")
        image_filename = None

        if not title or not location:
            error = "Title and location are required."
        else:
            # ❌ Insecure File Upload: no validation on file type
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                image_filename = filename
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                image_file.save(save_path)

            # إضافة العنصر في SQLite
            conn = get_db()
            conn.execute(
                "INSERT INTO items (type, title, location, status, description, image) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                (item_type, title, location, "Pending", description, image_filename),
            )
            conn.commit()
            conn.close()

            return redirect(url_for("items"))

    return render_template("report.html", role=role, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
