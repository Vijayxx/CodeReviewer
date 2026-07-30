# Sibyl — walkthrough for tomorrow

## The one-sentence pitch

An AI code-review auditor that distinguishes real bugs from hallucinated ones:
it sends a git diff to an LLM (Gemini), has the LLM flag potential issues, then
— instead of trusting the flag — auto-generates a pytest test per issue and
actually **runs** it against the code. If the test fails, the bug is real. If
it passes, the flag was a false positive. Benchmarked against a sandbox repo
with 4 deliberately planted bugs: **100% detection, 0% false positives**.

The core idea worth saying out loud: LLMs are good at *noticing* things and
bad at being *trusted* blindly. This pipeline uses the LLM twice — once to
notice, once to write a falsifiable check — and lets code execution (pytest)
be the actual judge, not the LLM's own confidence.

## The pipeline, in order

```
git diff  →  flag_issues()  →  generate_test() per issue  →  run_test()  →  verdict  →  report
(M1)          (M2)               (M3)                          (M4)         (M5)
```
Then M6 wraps all of that in one FastAPI endpoint, and M7 runs it against the
known-answer sandbox to compute accuracy numbers.

## File by file

### `diff_reader.py` (M1)
`get_diff(repo_path)` shells out to `git diff HEAD~1 HEAD` via `subprocess.run`,
with `cwd=repo_path` so it runs *inside* the target repo instead of this one.
Returns the diff as a plain string (`capture_output=True, text=True`).

**Why it matters:** this is the only piece of the whole project that isn't an
LLM call — it's just reading real git history. `subprocess.run` blocks until
git finishes, so this is fully synchronous.

### `sandbox_repo/` — the benchmark fixture
A **separate, nested git repo** (its own `.git/`) with one file, `bugs.py`,
four small functions. Two commits: `correct baseline`, then a second commit
that plants one bug per function — off-by-one (`numbers_upto`), wrong
comparator (`is_adult`), unhandled `None` (`greet`), mutable default argument
(`add_item`). Diffing those two commits is exactly the diff M1 reads. This
gives the project a **known answer key** — we know exactly which 4 things are
real bugs, which is what makes the M7 accuracy number meaningful instead of
just a vibe.

### `gemini_client.py` — shared client + retry
```python
load_dotenv()
client = genai.Client()      # created once, at import time — reused everywhere
MODEL = "gemini-flash-latest"

def call_gemini(prompt, retries=6, delay=15):
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=MODEL, contents=prompt).text
        except errors.ServerError:
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
```
**Why this file exists:** `flagger.py` and `test_generator.py` both need to
call Gemini. Rather than duplicate client setup and retry logic in both, it's
centralized here. **Be ready to explain the retry loop** — while building
this today the model returned repeated `503 UNAVAILABLE` (server overloaded)
and eventually a `429` daily quota error on the preview model. The fix was
exponential backoff (`delay * (attempt + 1)` — 15s, 30s, 45s...) and switching
to `gemini-flash-latest`, a stable model alias rather than a pinned preview
snapshot — good real example of "what broke and how you debugged it" if asked.

**`MODEL` as an alias, not a pinned version:** `gemini-flash-latest` always
points at whatever the current default flash model is, rather than a
snapshot name that can get deprecated or run out of quota. Trade-off worth
naming: less reproducible (behavior can shift under you), more durable.

### `flagger.py` (M2)
`flag_issues(diff_text)` builds a prompt that: frames Gemini as a critical
reviewer, lists bug categories to look for (off-by-one, wrong comparators,
unhandled None, mutable defaults), and — the important part — **constrains
the output format**: respond with *only* a JSON array, two keys per object
(`location`, `description`), no markdown fences, explicit empty-array
instruction for the no-bugs case. Then `json.loads(call_gemini(prompt))`
parses that string into real Python data (a list of dicts).

**Why the strict format matters:** `json.loads()` needs the *entire* string
to be valid JSON starting immediately — if Gemini wrapped the answer in
` ```json ` fences or added commentary, parsing would throw
`JSONDecodeError` and crash the whole pipeline before it even got to testing
anything. The prompt exists to make the LLM's output machine-readable, not
just human-readable.

**A bug worth mentioning if asked about debugging:** the JSON example inside
the prompt is embedded in an f-string. `{"location": ...}` inside an f-string
isn't literal text — `{` starts an expression — and it actually crashed with
a `ValueError` because the `:` after `"location"` got parsed as an f-string
format-spec separator. Fixed by doubling the braces (`{{`/`}}`) to escape
them into literal characters. Good example of a subtle language-level gotcha
versus a logic bug.

### `test_generator.py` (M3)
`generate_test(issue, diff_text)` — same call pattern, different prompt and
different output contract. Given one flagged issue (location + description)
plus the diff for context, it asks Gemini for **one pytest function** that:
imports the target function directly (`from bugs import <name>`, no package
prefix — works because M4 runs pytest with `sandbox_repo/` as the working
directory, so `bugs.py` is right there to import), and — the key instruction —
**must fail if the described bug is genuinely present, and pass if the code
is correct.** That's the falsifiability requirement that makes this whole
project more than "ask an LLM if there's a bug."

Returns raw text this time, not JSON — `json.loads` isn't used here because
the payload is Python source code, not structured data.

### `test_executor.py` (M4)
`run_test(test_code, repo_path, test_filename)` writes the generated test
string to an actual `.py` file inside `sandbox_repo/`, then runs
`subprocess.run(["python3", "-m", "pytest", test_filename, "-v"], cwd=repo_path, ...)`.
Returns `{"passed": returncode == 0, "output": stdout + stderr}`.

**Why write to a file instead of running the code string directly:** pytest
is a test *discovery and execution* tool — it works on files, not code
strings. This is also why `sandbox_repo/.gitignore` excludes
`test_generated*.py` — these are transient artifacts of a pipeline run, not
part of the sandbox's actual planted-bug fixture.

### `report.py` (M5)
`build_report(diff_text)` ties M2–M4 together: for each flagged issue, generate
a test, run it, and decide the verdict —
```python
verdict = "confirmed bug" if not result["passed"] else "false positive"
```
**The core logic of the whole project is this one line.** Test fails → the
described bug is real and reproducible → confirmed. Test passes → either the
LLM hallucinated an issue that isn't actually broken, or its test didn't
target it correctly → treated as a false positive either way, because we
can't currently tell those two failure modes apart (a real limitation worth
being honest about if asked — see the "if you had more time" question below).

### `main.py` (M6)
FastAPI wrapper, one endpoint:
```python
class AuditRequest(BaseModel):
    repo_path: str = "sandbox_repo"

@app.post("/audit")
def audit(request: AuditRequest):
    diff = get_diff(request.repo_path)
    return {"report": build_report(diff, repo_path=request.repo_path)}
```
`AuditRequest` is a Pydantic model — FastAPI uses it to validate the incoming
JSON body automatically and gives you a typed `request.repo_path` instead of
hand-parsing a raw dict. Verified this by actually starting the server with
`uvicorn` and `curl -X POST /audit` — got a real 200 with the full report
back, not just an import check.

### `benchmark.py` (M7)
Runs the whole pipeline against the sandbox, then compares the report against
`KNOWN_BUGS = {"numbers_upto", "is_adult", "greet", "add_item"}` — the answer
key. Computes:
- **Detection rate** — confirmed true positives ÷ known bugs
- **False positive rate** — confirmed-but-not-actually-a-known-bug ÷ all confirmed

Result on this sandbox: **100% detection (4/4), 0% false positives.**

Important caveat to say proactively if asked: this is 4 bugs in one tiny
sandbox file, not a large, adversarial, or statistically meaningful benchmark
— it demonstrates the *mechanism* works, not that it generalizes. That
honesty reads better in an interview than overclaiming.

## Likely questions and short answers

**"Walk me through what happens when a request comes in."**
POST /audit → `get_diff` shells out to git and returns the diff text →
`flag_issues` sends it to Gemini with a JSON-only prompt, parses the array →
for each flagged issue, `generate_test` asks Gemini for a pytest test that
would fail if that specific bug is real → `run_test` writes that test to disk
and runs it with pytest via subprocess → verdict is "confirmed" if the test
failed, "false positive" if it passed → all of that gets assembled into one
JSON report and returned.

**"Why generate a test instead of just asking the LLM if it's confident?"**
Confidence scores from an LLM are still just the LLM's opinion. A test that
actually executes against the real code is a falsifiable, objective check —
it either fails or it doesn't. That's the whole "distinguish real bugs from
hallucinated ones" idea.

**"What would break this?"** Three honest answers: (1) if Gemini writes a
test that doesn't actually exercise the described bug, a real bug could pass
as a false positive — the verdict logic can't distinguish "no bug" from "bad
test." (2) It only handles single-file, single-repo diffs — no multi-file
change tracking. (3) It's dependent on the LLM's output format discipline —
if it ignores the JSON-only instruction, `json.loads` throws and the whole
request fails; there's no fallback parser.

**"What was the hardest bug you hit building this?"** The f-string
brace-escaping crash in the M2 prompt (see above), and the Gemini 503/429
reliability issues today that led to the retry-with-backoff wrapper and
switching off a pinned preview model to an alias.

**"Why FastAPI?"** It was the specified stack, and the shape fits well: one
POST endpoint, a Pydantic request model for automatic validation, thin
wrapper around plain functions that are independently testable/runnable
without the web layer at all (every module has its own `__main__` block).

## Quick commands to have ready

```bash
# run the full pipeline standalone
python3 report.py

# run the benchmark
python3 benchmark.py

# run the API for real
python3 -m uvicorn main:app --reload
curl -X POST http://127.0.0.1:8000/audit -H "Content-Type: application/json" -d '{"repo_path": "sandbox_repo"}'
```
