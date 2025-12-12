from pathlib import Path
from dotenv import load_dotenv

# --- Paths and env setup ---
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_files"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


load_dotenv(BASE_DIR.parent /"test_cases" / ".env")  

with open(f"{OUTPUT_DIR}/clean_only.txt", "w") as f:
    f.write("hello world\n")
    f.write("no emails here\n")
    f.write("just some text 123\n")

Path(f"{OUTPUT_DIR}/clean_only2.txt").write_text("another clean file\n")
print("This is a clean print, no emails, no user ids.")
