import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient, errors
from bson.objectid import ObjectId
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev-secret"

# ---------- MongoDB Setup ----------
MONGO_URI = os.getenv("MONGO_URI") or "mongodb://localhost:27017/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)  # 5s timeout
    client.server_info()  # triggers exception if cannot connect
    print("MongoDB connected successfully!")
except errors.ServerSelectionTimeoutError as err:
    print("MongoDB connection failed:", err)
    exit(1)  # stop app if cannot connect

db = client["todo_app"]
users_col = db["users"]
tasks_col = db["tasks"]

# ---------- Helper ----------
def current_user_email():
    return session["user"]["email"] if "user" in session else None

# ---------- ROUTES ----------
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        if not all([name, email, password, confirm]):
            flash("All fields are required!", "warning")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("signup"))

        if users_col.find_one({"email": email}):
            flash("Email already exists!", "danger")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)
        users_col.insert_one({"name": name, "email": email, "password": password_hash})
        flash("Signup successful! Please login.", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Email and password required!", "warning")
        return redirect(url_for("index"))

    user = users_col.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
        session["user"] = {"email": user["email"], "name": user["name"]}
        flash(f"Welcome {user['name']}!", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Invalid email or password", "danger")
        return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("index"))

    email = current_user_email()
    user_tasks = list(tasks_col.find({"email": email}).sort("_id", -1))
    return render_template("dashboard.html", tasks=user_tasks, user=session["user"])

@app.route("/add", methods=["POST"])
def add_task():
    if "user" not in session:
        return redirect(url_for("index"))

    task_text = request.form.get("task", "").strip()
    if task_text:
        tasks_col.insert_one({
            "email": current_user_email(),
            "task": task_text,
            "done": False
        })
        flash("Task added successfully!", "success")
    else:
        flash("Task cannot be empty!", "warning")
    return redirect(url_for("dashboard"))

@app.route("/done/<task_id>", methods=["POST"])
def mark_done(task_id):
    if "user" not in session:
        return redirect(url_for("index"))

    tasks_col.update_one(
        {"_id": ObjectId(task_id), "email": current_user_email()},
        {"$set": {"done": True}}
    )
    flash("Task marked as done!", "success")
    return redirect(url_for("dashboard"))

@app.route("/pending/<task_id>", methods=["POST"])
def mark_pending(task_id):
    if "user" not in session:
        return redirect(url_for("index"))

    tasks_col.update_one(
        {"_id": ObjectId(task_id), "email": current_user_email()},
        {"$set": {"done": False}}
    )
    flash("Task marked as pending!", "info")
    return redirect(url_for("dashboard"))

@app.route("/delete/<task_id>", methods=["POST"])
def delete_task(task_id):
    if "user" not in session:
        return redirect(url_for("index"))

    tasks_col.delete_one({"_id": ObjectId(task_id), "email": current_user_email()})
    flash("Task deleted successfully!", "danger")
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("index"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
