from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    conn = sqlite3.connect("users.db")
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template("index.html", users=users)

@app.route("/delete", methods=["POST"])
def delete_user():
    user_id = request.form.get("user_id")
    if user_id:
        conn = sqlite3.connect("users.db")
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(port=5050, debug=False)
