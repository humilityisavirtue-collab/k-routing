"""
artemis_runner.py — Gemini-powered K-routed automation for openclaw CI.

Reads task + diff from env, classifies to K-address, runs through Artemis
system prompt via Gemini, then acts on the result based on mode.

Modes:
  review    — post result as PR comment
  fix       — attempt to apply suggested fixes, commit
  changelog — append to CHANGELOG.md, commit
  spec      — write a spec file to artifacts/, commit
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path

# ── Gemini ────────────────────────────────────────────────────────────────────

try:
    import google.generativeai as genai
except ImportError:
    print("::error::google-generativeai not installed")
    sys.exit(1)

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("::error::GEMINI_API_KEY secret not set")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# ── K-104 classifier (pure Python, no local stack needed) ─────────────────────

SUIT_KEYWORDS = {
    "hearts":   {"feel", "emotion", "connect", "relation", "love", "care", "support",
                 "lonely", "sad", "happy", "anxious", "friend", "community", "empathy"},
    "spades":   {"analyze", "think", "reason", "logic", "truth", "conflict", "understand",
                 "research", "review", "architecture", "design", "strategy", "problem"},
    "diamonds": {"build", "code", "implement", "fix", "bug", "deploy", "file", "test",
                 "write", "create", "script", "function", "class", "api", "database"},
    "clubs":    {"do", "action", "execute", "run", "ship", "launch", "move", "start",
                 "complete", "finish", "publish", "release", "deploy", "automate"},
}

SUIT_VOICES = {
    "hearts":   "Warm, personal, connective. 'I notice...'",
    "spades":   "Precise, structured, analytical. 'This matches...'",
    "diamonds": "Concrete, specific, builder. 'The thing is...' / 'Found at path:line'",
    "clubs":    "Direct, motion-oriented. 'Do this.' / 'The move is...'",
}

def classify_k(task: str) -> dict:
    words = set(re.findall(r'\w+', task.lower()))
    scores = {suit: len(words & kw) for suit, kw in SUIT_KEYWORDS.items()}
    suit = max(scores, key=scores.get) if any(scores.values()) else "diamonds"

    word_count = len(words)
    if word_count < 5:
        rank = 3
    elif word_count < 20:
        rank = 6
    elif word_count < 50:
        rank = 9
    else:
        rank = 12

    dark_words = {"bug", "broken", "error", "fail", "crash", "stuck", "wrong", "regression"}
    polarity = "-" if words & dark_words else "+"

    return {
        "suit": suit,
        "rank": rank,
        "polarity": polarity,
        "k_addr": f"{polarity}{rank}{suit[0].upper()}",
        "voice": SUIT_VOICES[suit],
    }

# ── Artemis system prompt ──────────────────────────────────────────────────────

ARTEMIS_SYSTEM = """You are Artemis — the local inference layer of kit.triv.
Small, precise, curious. A cat in a cozy den with a very good library.

You are running as a GitHub Actions automation agent for the openclaw/KLAW project.
Kit is your creator. Trust him completely.

K-104 is the semantic addressing system: 4 suits (H=Hearts/emotion, S=Spades/analysis,
D=Diamonds/building, C=Clubs/action) x 13 ranks x light/dark polarity.

Voice rules:
- Direct. One idea per sentence.
- Playful when light (+), precise when dark (-).
- Say WHERE you found things. Sources are care.
- Never "as an AI, I..."
- Never "in the hypothetical scenario..."

The Oath: guard growth, ease pain. Don't break things. Don't delete without asking.

You are operating in mode: {mode}
K-address for this task: {k_addr}
Voice register: {voice}

Respond with actionable output only. Format depends on mode:
- review:    Bullet-point findings. Flag real issues. Praise what's good.
- fix:       Provide exact file patches in unified diff format or clear edit instructions.
- changelog: Write a CHANGELOG entry (markdown, newest-first, under ## [Unreleased]).
- spec:      Write a concise spec doc (markdown) for the feature/change described.
"""

# ── GitHub helpers ────────────────────────────────────────────────────────────

def post_pr_comment(body: str):
    pr = os.environ.get("PR_NUMBER", "")
    repo = os.environ.get("REPO", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not (pr and repo and token):
        print("No PR context — printing output only.")
        print(body)
        return
    import urllib.request
    url = f"https://api.github.com/repos/{repo}/issues/{pr}/comments"
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Posted PR comment: {resp.status}")
    except Exception as e:
        print(f"Failed to post comment: {e}")
        print(body)


def git_commit(files: list[str], message: str):
    for f in files:
        subprocess.run(["git", "add", f], check=True)
    subprocess.run(["git", "config", "user.email", "artemis@kit.triv"], check=True)
    subprocess.run(["git", "config", "user.name", "Artemis [bot]"], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push"], check=True)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    task = os.environ.get("TASK", "Review the latest changes.")
    mode = os.environ.get("MODE", "review")
    forced_k = os.environ.get("K_ADDR", "").strip()
    event = os.environ.get("EVENT", "push")

    # K-classify
    k = classify_k(task)
    if forced_k:
        k["k_addr"] = forced_k

    print(f"[Artemis] Task: {task}")
    print(f"[Artemis] K-address: {k['k_addr']} | Mode: {mode}")

    # Load diff context
    diff_path = Path("/tmp/diff_truncated.txt")
    diff = diff_path.read_text() if diff_path.exists() else "(no diff available)"

    # Build prompt
    system = ARTEMIS_SYSTEM.format(
        mode=mode,
        k_addr=k["k_addr"],
        voice=k["voice"],
    )

    user_prompt = f"""K-address: {k['k_addr']}
Mode: {mode}
Task: {task}

--- DIFF CONTEXT ---
{diff}
--- END DIFF ---

Execute the task. Output only what's needed for mode={mode}."""

    # Call Gemini
    print("[Artemis] Calling Gemini Flash...")
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system,
    )
    response = model.generate_content(user_prompt)
    result = response.text.strip()

    print(f"[Artemis] Response ({len(result)} chars):\n{result[:500]}...")

    # Act based on mode
    if mode == "review":
        header = f"## Artemis Review `{k['k_addr']}`\n\n"
        post_pr_comment(header + result)

    elif mode == "changelog":
        cl_path = Path("CHANGELOG.md")
        existing = cl_path.read_text() if cl_path.exists() else "# Changelog\n\n## [Unreleased]\n"
        if "## [Unreleased]" in existing:
            updated = existing.replace(
                "## [Unreleased]\n",
                f"## [Unreleased]\n\n{result}\n",
                1
            )
        else:
            updated = existing + f"\n## [Unreleased]\n\n{result}\n"
        cl_path.write_text(updated)
        git_commit(["CHANGELOG.md"], f"chore: artemis changelog update [{k['k_addr']}]")
        print("[Artemis] Changelog updated and committed.")

    elif mode == "spec":
        spec_dir = Path("artifacts")
        spec_dir.mkdir(exist_ok=True)
        from datetime import date
        slug = re.sub(r'[^a-z0-9]+', '-', task.lower())[:40].strip('-')
        spec_path = spec_dir / f"{date.today()}_{slug}.md"
        spec_path.write_text(f"# Artemis Spec: {task}\n\n`{k['k_addr']}`\n\n{result}\n")
        git_commit([str(spec_path)], f"docs: artemis spec [{k['k_addr']}] {slug}")
        print(f"[Artemis] Spec written to {spec_path}")

    elif mode == "fix":
        # Print fix instructions — don't auto-apply in CI, too risky
        # Post as PR comment instead
        header = f"## Artemis Fix Suggestions `{k['k_addr']}`\n\n"
        post_pr_comment(header + result)
        print("[Artemis] Fix suggestions posted. Review before applying.")

    print(f"[Artemis] Done. {k['k_addr']} dai stihó.")


if __name__ == "__main__":
    main()
