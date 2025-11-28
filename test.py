# test_flask_provenance.py
from flask import Flask, request
import provenance

app = Flask(__name__)

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "")
    provenance.set_current_owner(email)

    welcome = f"Welcome back, {email}!"
    print(welcome)  # will emit provenance log automatically

    age = 30
    print("AGE:", age)

    return "Login success"

if __name__ == "__main__":
    app.run(port=5000, debug=False)
