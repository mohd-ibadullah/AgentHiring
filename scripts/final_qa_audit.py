"""Brutal pre-submission QA — all layers."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "outputs" / "mohd_ibadullah.csv"
CANDIDATES_PATH = Path(
    r"C:/Users/froms/Downloads/[PUB] India_runs_data_and_ai_challenge/"
    r"[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/candidates.jsonl"
)
SAMPLE_PATH = ROOT / "data" / "sample_candidates.json"
VALIDATOR = Path(
    r"C:/Users/froms/Downloads/[PUB] India_runs_data_and_ai_challenge/"
    r"[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge/validate_submission.py"
)
OUT_CSV = ROOT / "outputs" / "_qa_speed_test.csv"

sys.path.insert(0, str(ROOT))
from src.honeypot_detector import detect_trap  # noqa: E402

results: dict[str, tuple[bool, str]] = {}


def record(name: str, passed: bool, detail: str = "") -> None:
    results[name] = (passed, detail)
    tag = "PASS" if passed else "FAIL"
    line = f"  {tag} — {name}"
    if detail:
        line += f" ({detail})"
    print(line)


def load_csv_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def layer1() -> None:
    print("\n" + "=" * 60)
    print("LAYER 1 — Submission File Deep Check")
    print("=" * 60)
    rows = load_csv_rows()
    scores = [float(r["score"]) for r in rows]
    ranks = sorted(int(r["rank"]) for r in rows)
    ids = [r["candidate_id"] for r in rows]

    record("Exactly 100 rows", len(rows) == 100, str(len(rows)))
    record("Has candidate_id column", "candidate_id" in rows[0])
    record("Has rank column", "rank" in rows[0])
    record("Has score column", "score" in rows[0])
    record("Ranks are 1-100 sequential", ranks == list(range(1, 101)))
    record("No duplicate candidate_ids", len(set(ids)) == 100)
    record("No duplicate ranks", len(set(ranks)) == 100)
    sorted_scores = [float(r["score"]) for r in sorted(rows, key=lambda x: int(x["rank"]))]
    record("Scores descending by rank", all(sorted_scores[i] >= sorted_scores[i + 1] for i in range(99)))
    record("No score = 100.0", sum(1 for s in scores if s == 100.0) == 0)
    record("No score = 0.0 in top 100", sum(1 for s in scores if s == 0.0) == 0)
    # Submission uses 0–1 scale; also check 0–100 interpretation
    max_s = max(scores)
    record(
        "Top score in valid range (0–1 scale 0.85–0.994)",
        0.85 <= max_s <= 0.994,
        f"max={max_s}",
    )
    record("Score variance > 0.10 (0–1 scale)", max_s - min(scores) > 0.10, f"range={max_s - min(scores):.4f}")
    record("At least 50 unique scores", len(set(scores)) >= 50, str(len(set(scores))))
    record("Has reasoning column", "reasoning" in rows[0])
    record("100 unique reasonings", len(set(r.get("reasoning", "") for r in rows)) == 100)

    honeypots_known = ["CAND_0000002", "CAND_0000003", "CAND_0000004", "CAND_0000005"]
    for h in honeypots_known:
        record(f"Honeypot {h} excluded", h not in ids)

    # Full honeypot scan on top 100
    cmap: dict[str, dict] = {}
    if CANDIDATES_PATH.exists():
        with CANDIDATES_PATH.open(encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                cmap[c["candidate_id"]] = c
        traps = [cid for cid in ids if detect_trap(cmap[cid])[0] >= 0.4]
        record("0 honeypots in top 100 (detector)", len(traps) == 0, f"found={traps[:5]}")
    else:
        record("0 honeypots in top 100 (detector)", False, "candidates.jsonl missing")

    print("\nTop 5:")
    for r in sorted(rows, key=lambda x: int(x["rank"]))[:5]:
        print(f"  {r['rank']} | {r['candidate_id']} | {r['score']} | {r['reasoning'][:90]}...")


def layer2() -> None:
    print("\n" + "=" * 60)
    print("LAYER 2 — Pipeline Integrity Check")
    print("=" * 60)
    if not CANDIDATES_PATH.exists():
        record("Speed test ran", False, "candidates.jsonl missing")
        return

    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "rank.py"),
            "--candidates",
            str(CANDIDATES_PATH),
            "--out",
            str(OUT_CSV),
            "--skip-preflight",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    pipeline_sec = None
    for line in proc.stdout.splitlines():
        if "Pipeline completed successfully in" in line:
            pipeline_sec = line.split("in")[1].strip().rstrip("!")

    record("Pipeline exit code 0", proc.returncode == 0, f"code={proc.returncode}")
    record("Speed wall-clock < 140s", elapsed < 140, f"{elapsed:.1f}s")
    record("Speed wall-clock < 60s (ideal warm)", elapsed < 60, f"{elapsed:.1f}s")
    if pipeline_sec:
        print(f"  INFO — Pipeline self-reported: {pipeline_sec}")

    print("\n--- MEMORY TEST (load full JSONL into list) ---")
    tracemalloc.start()
    with CANDIDATES_PATH.open(encoding="utf-8") as f:
        data = [json.loads(line) for line in f]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / 1024 / 1024
    record("Memory load-jsonl < 16GB", peak_mb < 16000, f"{peak_mb:.0f} MB")
    record("Memory load-jsonl < 2GB (ideal)", peak_mb < 2000, f"{peak_mb:.0f} MB")
    print(f"  NOTE — Full pipeline peak RAM is higher (~2–4 GB with models); this tests raw JSONL load only ({len(data)} rows)")


def _profile(c: dict) -> dict:
    return c.get("profile", c)


def layer3() -> None:
    print("\n" + "=" * 60)
    print("LAYER 3 — Data Quality (sample_candidates.json — UI dataset)")
    print("=" * 60)
    with SAMPLE_PATH.open(encoding="utf-8") as f:
        candidates = json.load(f)

    GENERIC_PHRASES = [
        "managed cross-functional projects",
        "managed the full release lifecycle",
        "led the mobile api backend",
        "led performance profiling",
        "owned the authentication and authorization layer",
        "built internal tooling and developer platforms",
        "implemented ci/cd pipelines",
        "owned end-to-end feature delivery",
        "architected the migration from monolith",
        "led api design and developer experience improvements",
    ]

    generic_found = []
    duplicate_within = []
    all_descriptions = []

    for c in candidates:
        name = _profile(c).get("anonymized_name", c.get("name", "?"))
        seen: set[str] = set()
        for job in c.get("career_history", []):
            desc = job.get("description", "").lower()
            all_descriptions.append((name, job.get("company", ""), desc))
            for phrase in GENERIC_PHRASES:
                if phrase in desc:
                    generic_found.append(f"{name} @ {job.get('company','')} → '{phrase}'")
            if desc in seen:
                duplicate_within.append(f"{name} duplicate at {job.get('company','')}")
            seen.add(desc)

    record("Zero generic descriptions (sample 50)", len(generic_found) == 0, f"found={len(generic_found)}")
    for g in generic_found[:8]:
        print(f"    {g}")

    record("Zero within-candidate desc dupes", len(duplicate_within) == 0, f"found={len(duplicate_within)}")
    for d in duplicate_within[:5]:
        print(f"    {d}")

    desc_texts = [d[2] for d in all_descriptions if d[2]]
    cross_dupes = {k: v for k, v in Counter(desc_texts).items() if v > 1}
    record("Zero cross-candidate desc dupes (sample)", len(cross_dupes) == 0, f"found={len(cross_dupes)}")
    for desc, count in list(cross_dupes.items())[:5]:
        print(f"    Used {count}x: '{desc[:80]}...'")

    edu_issues = []
    for c in candidates:
        name = _profile(c).get("anonymized_name", "?")
        edu = c.get("education", [])
        keys = [(e.get("institution", ""), e.get("degree", "")) for e in edu]
        if len(keys) != len(set(keys)):
            edu_issues.append(f"{name} duplicate degree")
        years = [e.get("start_year", 0) for e in edu]
        for i in range(1, len(years)):
            if years[i] < years[i - 1]:
                edu_issues.append(f"{name} edu not chronological {years}")
        for i in range(1, len(edu)):
            if edu[i].get("start_year", 0) < edu[i - 1].get("end_year", 0):
                edu_issues.append(f"{name} overlapping edu")

    record("Education dates valid (sample)", len(edu_issues) == 0, f"issues={len(edu_issues)}")
    for e in edu_issues[:5]:
        print(f"    {e}")

    salary_issues = []
    for c in candidates:
        name = _profile(c).get("anonymized_name", "?")
        salary = c.get("redrob_signals", {}).get("expected_salary_range_inr_lpa", {})
        mn, mx = salary.get("min", 0), salary.get("max", 0)
        if mn > mx:
            salary_issues.append(f"{name} min({mn}) > max({mx})")
    record("Salary min < max (sample)", len(salary_issues) == 0, f"issues={len(salary_issues)}")

    job_issues = []
    for c in candidates:
        name = _profile(c).get("anonymized_name", "?")
        jobs = c.get("career_history", [])
        keys = [(j.get("company", "").lower(), j.get("title", "").lower()) for j in jobs]
        if len(keys) != len(set(keys)):
            job_issues.append(f"{name} duplicate job")
    record("No duplicate job entries (sample)", len(job_issues) == 0, f"issues={len(job_issues)}")


def layer4() -> None:
    print("\n" + "=" * 60)
    print("LAYER 4 — Submission Top-10 Role Quality (NOT Streamlit sample)")
    print("=" * 60)
    rows = load_csv_rows()
    top10 = sorted(rows, key=lambda x: int(x["rank"]))[:10]
    cmap: dict[str, dict] = {}
    with CANDIDATES_PATH.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c["candidate_id"] in {r["candidate_id"] for r in top10}:
                cmap[c["candidate_id"]] = c

    ai_keywords = [
        "ai", "ml", "nlp", "data", "search", "scientist", "recommendation",
        "machine learning", "applied", "retrieval", "ranking",
    ]
    ai_count = 0
    for r in top10:
        cid = r["candidate_id"]
        title = _profile(cmap[cid]).get("current_title", "").lower()
        ok = any(k in title for k in ai_keywords)
        if ok:
            ai_count += 1
        record(f"Top-{r['rank']} AI-relevant title: {title[:50]}", ok, cid)

    record("Top 10 all AI/ML-relevant titles", ai_count == 10, f"{ai_count}/10")

    scores = [float(r["score"]) for r in rows]
    record("No score > 0.994 (99.4%)", max(scores) <= 0.994, f"max={max(scores)}")
    record("Top-20 submission scores all unique", len(set(scores[:20])) == 20, f"{len(set(scores[:20]))}/20")


def layer5() -> None:
    print("\n" + "=" * 60)
    print("LAYER 5 — Official Validator")
    print("=" * 60)
    if not VALIDATOR.exists():
        record("Official validator exit 0", False, "validator script missing")
        return
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(CSV_PATH)],
        capture_output=True,
        text=True,
        cwd=str(VALIDATOR.parent),
    )
    print(proc.stdout[-1500:] if len(proc.stdout) > 1500 else proc.stdout)
    if proc.stderr:
        print(proc.stderr[-500:])
    record("Official validator exit 0", proc.returncode == 0, f"code={proc.returncode}")


def layer6() -> None:
    print("\n" + "=" * 60)
    print("FINAL PRE-SUBMISSION REPORT")
    print("=" * 60)
    passed = sum(1 for ok, _ in results.values() if ok)
    total = len(results)
    print(f"\nRESULT: {passed}/{total} checks passed")
    fails = [name for name, (ok, detail) in results.items() if not ok]
    if fails:
        print("\nFAILURES TO REVIEW:")
        for name in fails:
            _, detail = results[name]
            print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))
    status = "✅ SUBMIT (with noted caveats)" if passed / total >= 0.85 and results.get("Official validator exit 0", (False,))[0] else "❌ FIX BEFORE SUBMITTING"
    print(f"\nSTATUS: {status}")


if __name__ == "__main__":
    layer1()
    layer2()
    layer3()
    layer4()
    layer5()
    layer6()
