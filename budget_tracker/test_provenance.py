# Provenance test covering ALL sinks and propagation cases

import json
import socket
import logging
from pathlib import Path
import io
import sys
import http.client


class User:
    def __init__(self, email, age, nationality, income):
        self.email = email
        self.age = age
        self.nationality = nationality
        self.income = income


# --- Setup two users ---
u = User("alice@example.com", 30, "USA", 600.5)
u2 = User("bob@example.com", 25, "Canada", 600.0)


def helper(email):
    email = email + "  --- "
    print("Helper email:", email)


# --- Direct attribute reads ---
print("Alice email:", u.email)
print("Alice age:", u.age)
print("Alice nationality:", u.nationality)
helper(u.email)


# --- Derived from sensitive data ---
derived = u.email + " -- verified"
print("Alice email modified:", derived)


# --- Clean data ---
num = 70
print("This variable is clean shouldn't be tainted:", num)


# --- Modify attribute to clean value ---
u.age = 999
print("Alice age modified:", u.age)


# --- Multiple owner propagation ---
alice = u.age
bob = u2.age

combined = alice + bob
print("Alice and Bob ages combined:", combined)

print("Bob age:", u2.age)


# --- String concat propagation ---
u2.nationality = "Canada" + " - North America"
print("Bob nationality:", u2.nationality)


# --- Arithmetic propagation ---
income_diff = u2.income - u.income
print("Income difference:", income_diff)

bob_income_sum = u2.income + 1000
print("Bob income plus 1000:", bob_income_sum)

bob_income_like_alice = u2.income + 0.5
print("Bob income plus 0.5:", bob_income_like_alice)

x = u2.age + 5
print("Bob age modified:", x)

combined2 = combined + 5
print("Combined modified ages:", combined2)


# ==========================================================
# 1. Text file write (text sink)
# ==========================================================
with open("test_text.txt", "w") as f:
    f.write(str(u.age))      # should log
    f.write("\nclean line")           # ignored
print("Text file write done")


# ==========================================================
# 2. Binary file write (binary sink)
# ==========================================================
with open("test_bin.bin", "wb") as f:
    f.write(str(u.age).encode())    # should log
    f.write(b"\x00\x01\x02")          # ignored
print("Binary write done")


# ==========================================================
# 3. JSON dump + write
# ==========================================================
record = {"email": u.email, "age": u.age}
with open("test_json.json", "w") as f:
    json.dump(u.age, f)              # uses file.write internally
print("JSON dump done")


# ==========================================================
# 4. json.dumps + file.write
# ==========================================================
with open("test_json2.json", "w") as f:
    f.write(str(u.age))               # should log
print("JSON string write done")


# ==========================================================
# 5. sys.stdout.write
# ==========================================================
sys.stdout.write("stdout test: " + str(u.age) + "\n")


# ==========================================================
# 6. sys.stderr.write
# ==========================================================
sys.stderr.write("stderr test: " + str(u.age) + "\n")


# ==========================================================
# 7. logging module (writes to stderr)
# ==========================================================
logging.basicConfig(level=logging.WARNING)
logging.warning("log test: " + str(u.age))


# ==========================================================
# 8. Path.write_text
# ==========================================================
Path("test_path.txt").write_text("from_path: " + str(u2.age))
print("Path write done")


# ==========================================================
# 9. io.TextIOWrapper write
# ==========================================================
buf = io.StringIO()
buf.write("stringio: " + str(u.age))
print("StringIO done")


# ==========================================================
# 10. socket.send
# ==========================================================
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    # no connection needed to trigger provenance
    s.send(b"email: " + str(u.age).encode())
except Exception:
    pass
s.close()
print("Socket send done")


# ==========================================================
# 11. HTTP request (built on socket)
# ==========================================================
try:
    conn = http.client.HTTPConnection("example.com", 80, timeout=1)
    conn.request("GET", "/?q=" + str(u.age))
except Exception:
    pass
print("HTTP send done")


print("DONE")
