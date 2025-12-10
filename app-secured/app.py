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
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change_me_later"  # غيّرها لو حاب في النسخة النهائية
app.permanent_session_lifetime = timedelta(minutes=30)

# ===== Paths =====
basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, "lostfound.db")

UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ===== SQLite Helpers =====
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

# ===== Users (Secure: hashed passwords) =====
USERS = {
    "ali": {"password": generate_password_hash("stud123"), "role": "student"},
    "fatima": {"password": generate_password_hash("stud123"), "role": "student"},
    "salim": {"password": generate_password_hash("stud123"), "role": "student"},
    "office_admin": {"password": generate_password_hash("secure123"), "role": "admin"},
}


# ===== Routes =====
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
        if user and check_password_hash(user["password"], password):
            session.permanent = True
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
    role = session.get("role", "student")
    username = session.get("username")
    return render_template("dashboard.html", role=role, username=username)


@app.route("/items")
def items():
    if "username" not in session:
        return redirect(url_for("login"))

    role = session.get("role", "student")
    q = request.args.get("q", "").strip()

    conn = get_db()

    if q:
        # ✅ Secure: parameterized query (no SQL injection)
        sql = "SELECT * FROM items WHERE title LIKE ? OR description LIKE ? ORDER BY id;"
        rows = conn.execute(sql, (f"%{q}%", f"%{q}%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM items ORDER BY id;").fetchall()

    conn.close()

    return render_template("items.html", items=rows, role=role, q=q)


@app.route("/report", methods=["GET", "POST"])
def report():
    if "username" not in session:
        return redirect(url_for("login"))

    role = session.get("role", "student")
    error = None

    if request.method == "POST":
        item_type = request.form.get("item_type", "Lost")
        title = request.form.get("title", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        image_file = request.files.get("image")
        image_filename = None

        # Basic validation
        if not title or not location:
            error = "Title and location are required."
            return render_template("report.html", role=role, error=error)

        if len(title) > 100:
            error = "Title is too long (max 100 characters)."
            return render_template("report.html", role=role, error=error)

        if len(description) > 500:
            error = "Description is too long (max 500 characters)."
            return render_template("report.html", role=role, error=error)

        # ✅ Secure file upload: only images allowed
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_filename = filename
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                image_file.save(save_path)
            else:
                error = "Invalid file type. Allowed: png, jpg, jpeg, gif."
                return render_template("report.html", role=role, error=error)

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
