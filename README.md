# **Server-Side Tracking Detection via Instrumented Python Runtime**

This project modifies the **Python runtime itself** to detect **server-side tracking (SST)** by automatically tagging user identifiers, propagating those tags through normal Python execution, and logging whenever sensitive or derived data leaves the application through a sink (files, sockets, stdout, HTTP/HTTPS, JSON, etc.).

Unlike browser tools, SST happens entirely on backend servers where users have **zero visibility**. This system provides **runtime-level provenance** without requiring modifications to application code.

---

## **Table of Contents**

1. [Motivation](#motivation)
2. [System Overview](#system-overview)
3. [Repository Structure](#repository-structure)
4. [How It Works](#how-it-works)
5. [Building the Instrumented Runtime](#building-the-instrumented-runtime)
6. [Setting Up the Demo Environment](#setting-up-the-demo-environment)
7. [Running the Demo Application](#running-the-demo-application)
8. [Viewing Provenance Logs](#viewing-provenance-logs)
9. [Running the Provenance Test Harness](#running-the-provenance-test-harness)
10. [Performance Notes](#performance-notes)
11. [Evaluation Plan](#evaluation-plan)
12. [Limitations](#limitations)
13. [Future Work](#future-work)

---

# **Motivation**

Client-side tracking has long been detectable by browser tools, extensions, and privacy frameworks.
Today, companies increasingly shift tracking to the **backend**:

```
Browser → Server → Hidden server-to-server sharing
```

Users, auditors, and regulators cannot see where their data flows after the first hop.
This project introduces **visibility at the runtime level**.

---

# **System Overview**

### **High-Level Architecture**

```
           Incoming HTTP Request
                     │
                     ▼
             Flask Application
                     │
                     ▼
      ┌─────────────────────────────────┐
      │  Instrumented CPython Runtime   │
      │                                 │
      │  • Tag user identifiers         │
      │  • Propagate provenance         │
      │  • Intercept data sinks         │
      │  • Emit JSON audit logs         │
      └─────────────────────────────────┘
                     │
             External Sinks
      (files, JSON, stdout, HTTP, socket,
           HTTPS, AI calls, partners)
                     │
                     ▼
              `prov.log` audit file
```

---

# **Repository Structure**

```
.
├── python-prov/
│   ├── Python-3.11.14/      # Patched CPython source
│   └── py311-prov/          # Installation directory of instrumented interpreter
│
├── venv/                    # Virtualenv bound to instrumented Python
│
├── budget_tracker/          # Demo Flask application
│   ├── app.py
│   ├── ai_insights.py
│   ├── privacy_share.py
│   └── shared_with_third_parties/
│
├── test_cases/              # Standalone provenance regression harness
│   ├── test_provenance.py   # Propagation + sink coverage; writes to test_cases/output_files
│   └── output_files/        # Generated text/JSON artifacts from the test
│
├── requirements.txt         # Project-wide dependencies (app + evaluation)
│
├── evaluation/              # Performance notebook and optional saved artifacts
│   ├── evaluation.ipynb     # Baseline vs instrumented benchmarks + plots
│   └── eval_output/         # Where optional plots/results can be saved
│
├── prov_viewer/             # Web UI for audit logs
│   └── app.py
│
├── prov.log                 # Generated provenance events
└── README.md
```

---

# **How It Works**

### **1. Tagging Sensitive Data**

* Any Python object with an attribute named `email` is checked.
* If the value looks like an email, runtime assigns:

  * **Owner tag** to the value.
  * **Owner tag** to the user object.
  * **Thread-local owner** used for inference.

### **2. Provenance Propagation**

Modified Python internals propagate tags through:

* `str()`, `repr()`, f-strings
* JSON encoding (patched `_json` encoder)
* arithmetic
* string concat
* list/dict operations

### **3. Logging at Sinks**

When tagged or owner-inferable data leaves Python, runtime logs:

* stdout/stderr
* text/binary file writes
* `json.dump` / `json.dumps`
* sockets (`socket.send`)
* HTTP (`http.client`)
* HTTPS (`http.client.HTTPSConnection` → `_ssl` write hook)

Each event includes:

```
sink, timestamp, owner list, dest, data sample
```

### AI Insights (Groq)
1) Go to https://console.groq.com/keys, create an account, and generate an API key.
2) In `budget_tracker/.env`, add:
```
GROQ_API_KEY=<your-groq-key>
PY_PROVENANCE_LOG_JSON=/Users/enasbatarfi/sst-detection-system/prov.log
PY_PROVENANCE_SOURCE=budget_tracker
```
3) Restart the app so the key is picked up. The AI insights page will call Groq’s chat completions; if the key is invalid or missing, it falls back to a local “Insight Error” message.

---

# **Building the Instrumented Runtime**

⚠️ **Important:**
This build takes **2.5–3.5 hours** on macOS ARM and may take longer depending on CPU load.

```bash
cd python-prov/Python-3.11.14

./configure --prefix=$PWD/../py311-prov --enable-optimizations
make -j$(sysctl -n hw.ncpu)
make install
```

You will get a patched interpreter here:

```
python-prov/py311-prov/bin/python3.11
```

---

# **Setting Up the Demo Environment**

### **1. Create a venv that uses the patched interpreter**

```bash
python-prov/py311-prov/bin/python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

The root `requirements.txt` covers the demo app, provenance viewer, and lightweight evaluation helpers.

### **2. Enable provenance logging**

By default, logs go to stderr. If you are not already setting these in `.env`, you can persist logs to a file with:

```bash
export PY_PROVENANCE_LOG_JSON="$(pwd)/prov.log"
export PY_PROVENANCE_SOURCE="budget_tracker"   # optional label
```

---

# **Running the Demo Application**

```bash
cd budget_tracker
python app.py
```

Visit:

```
http://127.0.0.1:5000
```

Perform actions: signup → login → add expenses → generate AI insights → share with partners.
All data flows get captured.

---

# **Viewing Provenance Logs**

Use the viewer:

```bash
cd prov_viewer
FLASK_APP=app.py flask run --port 5001
```

Open:

```
http://127.0.0.1:5001
```

Allows filtering by:

* owner email
* sink type
* keyword match

---

# **Running the Provenance Test Harness**

A standalone regression lives in `test_cases/test_provenance.py` and exercises propagation plus every sink (stdout/stderr/logging, files, sockets/HTTP/HTTPS, partner shares).

```bash
cd test_cases
python test_provenance.py
```

Artifacts and logs:

* `test_cases/output_files/` — generated text/JSON outputs
* `test_cases/prov.log` — provenance events (configured via `test_cases/.env`)

---

# **Performance Notes**

This system modifies CPython internals, and **performance overhead is real**.

### **Build Time**

* Full CPython build takes **3 hours or more**.

### **Runtime Overhead**

* Flask application startup is **slower** (instrumented import path).
* Request handling is slower due to:

  * provenance checks
  * owner propagation
  * sink logging
  * JSON encoder hooks

### **Throughput Impact**

Expected 20–60% slowdown depending on workload.
Logging-heavy flows slow further because every sink write produces JSON.

You can measure this (see Evaluation section below).

---

# **Evaluation Plan**

The goal: verify that the instrumented runtime **detects SST**, logs **all outbound flows**, and keeps **noise/false positives low**.

Below is how to evaluate each metric.

## **1. Detection Rate**

Measure how many intentional shares are logged.

### Method:

```bash
python budget_tracker/test_provenance.py
grep '"sink"' prov.log | wc -l
```

Compare expected vs. observed events.

---

## **2. False Positives**

Verify that logs do **not** include:

* clean values
* non-sensitive file writes
* helper prints
* empty writes

### Method:

Search for clean lines:

```bash
grep -R "clean line" prov.log
```

---

## **3. System Latency**

Measure request latency with and without instrumentation.

### Method (Flask profiling):

```bash
ab -n 100 -c 1 http://127.0.0.1:5000/dashboard
```

Compare:

* vanilla CPython
* instrumented CPython

---

## **4. CPU & Memory Overhead**

Profile with `ps`, `top`, or Python’s `resource` module during a workload:

```bash
python -m cProfile budget_tracker/app.py
```

---

## **5. Storage Overhead**

Measure daily log volume under realistic usage:

```bash
du -sh prov.log
```

---

## **6. Usability & Developer Burden**

Checklist:

* No application code changes required
* All tagging occurs automatically
* Logging is external and unobtrusive

---

# **Evaluation (Notebook)**

For a simple performance comparison between baseline and instrumented servers:

1. Start both servers: baseline at `http://127.0.0.1:5001`, instrumented at `http://127.0.0.1:5000`.
2. Open `evaluation/evaluation.ipynb` using the **baseline** environment (`venv_baseline`).
3. Run all cells. The notebook verifies endpoints, runs `run_benchmark` on `/dashboard` and `/share`, and shows inline tables plus matplotlib plots (histogram, ECDF, boxplot, throughput bars, percentile bars).
4. Plots display inline; optionally save them under `evaluation/eval_output/plots/`.

To reduce noise from page assets, page-level logging is disabled in `budget_tracker/app.py`; the notebook focuses only on `/dashboard` and `/share` performance.


---

# **Limitations**

* Only **emails** are automatically recognized as PII.
* Mixed writes (tagged + clean) still log the combined buffer.
* Some async HTTPS libraries bypass CPython sockets.
* No instrumentation inside SQLite or ORM layers.
* Logs may grow large for heavy I/O workloads.
* Build is slow and runtime overhead is noticeable.

---

# **Future Work**

* Add heuristics for phone numbers, UUIDs, user IDs.
* Add database sinks (SQL read/write instrumentation).
* More efficient logging (sampling, truncation).
* Automatic performance benchmarking tooling.
* Visual provenance flows (graph view).
* Optional developer annotations (`@sensitive`).

---

# **Reproduction Summary (Quick Start)**

```bash
# Build runtime (3 hours)
cd python-prov/Python-3.11.14
./configure --prefix=$PWD/../py311-prov
make -j8 && make install

# Create venv
python-prov/py311-prov/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Enable logging
export PY_PROVENANCE_LOG_JSON="$(pwd)/prov.log"

# Run app
cd budget_tracker
python app.py

# Run tests
python test_provenance.py

# View logs
cd ../prov_viewer
flask run --port 5001
