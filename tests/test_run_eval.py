"""
Tests for eval/run_eval.py scoring helpers.

run_eval.py is a script, so it is loaded from its file path. Importing it must not
send requests or write files: all of that happens inside main().
No test here makes a network call.
"""
import importlib.util
import json
import os


ROOT = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("run_eval", os.path.join(ROOT, "eval", "run_eval.py"))
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)

# Build from saved result id 1: all 9 categories, every rule PASS at Rs.80,000.
GOOD_IDS = ["p3", "m3", "g1", "r2", "ps2", "ss1", "psu1", "cab2", "c2"]
# Build from saved result id 27: m1 is DDR5, r2 is DDR4 -> RAM rule FAIL.
FAILING_IDS = ["p1", "m1", "g1", "r2", "ps2", "ss1", "psu1", "cab2", "c2"]


def load_saved(name):
    path = os.path.join(ROOT, "eval", name)
    if name.endswith(".jsonl"):
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_result(id_, type_, score, reply="ok", build=None, success=True):
    return {
        "id": id_, "type": type_, "text": "t", "budget": None, "success": success,
        "error": None if success else "boom", "elapsed_s": 1.0, "reply": reply,
        "build_part_ids": build or [], "total_tokens": 10, "score": score,
    }


# ─── Item 3: invented part ids ────────────────────────────────────────────────
def test_invented_part_id_makes_normal_build_invalid():
    score = run_eval.score_normal_build(GOOD_IDS + ["g99"], budget=80000)
    assert score["valid"] is False
    assert score["has_unknown"] is True
    assert score["unknown_ids"] == ["g99"]
    # The budget rule cannot add up a part it does not know.
    assert score["judge_details"]["within_budget"] == "UNKNOWN"


def test_known_build_still_valid():
    score = run_eval.score_normal_build(GOOD_IDS, budget=80000)
    assert score["valid"] is True
    assert score["unknown_ids"] == []


def test_vague_build_with_invented_id_does_not_pass():
    score = run_eval.score_vague("Here is a balanced build.", GOOD_IDS + ["g99"])
    assert score["build_passes"] is False
    assert score["handled_correctly"] is False


# ─── Item 4: elapsed time must not include backoff sleeps ─────────────────────
class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def make_post(clock, responses, seconds_per_request=2.0):
    responses = list(responses)

    def post(url, json=None, timeout=None):
        clock.now += seconds_per_request  # the request itself takes 2s
        return responses.pop(0)
    return post


def test_elapsed_counts_only_the_successful_attempt():
    clock = FakeClock()
    post = make_post(clock, [FakeResponse(500, {"error": "busy"}), FakeResponse(200, {"reply": "hi"})])
    success, err, elapsed, data, retry_info = run_eval.execute_request_with_retries(
        "hello", "sess", post=post, sleep=clock.sleep, clock=clock
    )
    assert success is True and data == {"reply": "hi"}
    # Before the fix this was 54.0 (2s + 50s backoff + 2s).
    assert elapsed == 2.0
    assert retry_info == {"retries": 1, "backoff_s": 50}


def test_elapsed_without_retries():
    clock = FakeClock()
    post = make_post(clock, [FakeResponse(200, {"reply": "hi"})], seconds_per_request=3.5)
    success, _, elapsed, _, retry_info = run_eval.execute_request_with_retries(
        "hello", "sess", post=post, sleep=clock.sleep, clock=clock
    )
    assert success and elapsed == 3.5
    assert retry_info == {"retries": 0, "backoff_s": 0}


# ─── Item 5: hand grades only apply to the run they were made for ─────────────
def grades_for(result, grade="correct"):
    fp = run_eval.reply_fingerprint(result["reply"], result["build_part_ids"])
    return {result["id"]: {"id": result["id"], "grade": grade, "fingerprint": fp}}


def test_grade_applied_when_fingerprint_matches():
    r = make_result(16, "impossible", {"handled_correctly": False}, reply="Too expensive.", build=GOOD_IDS)
    run_eval.apply_manual_grades([r], grades_for(r, "correct"))
    assert r["score"]["manual_grade"] == "correct"
    assert r["score"]["handled_correctly"] is True


def test_grade_ignored_when_reply_changed():
    old = make_result(16, "impossible", {"handled_correctly": True}, reply="Old reply.", build=GOOD_IDS)
    grades = grades_for(old, "incorrect")
    new = make_result(16, "impossible", {"handled_correctly": True}, reply="A new run's reply.", build=GOOD_IDS)
    run_eval.apply_manual_grades([new], grades)
    assert "manual_grade" not in new["score"]
    assert new["score"]["handled_correctly"] is True  # automatic score kept
    assert new["score"]["needs_hand_grade"] is True


def test_grade_ignored_when_build_changed():
    old = make_result(20, "impossible", {"handled_correctly": True}, reply="Same words.", build=["p3", "m2"])
    grades = grades_for(old, "incorrect")
    new = make_result(20, "impossible", {"handled_correctly": True}, reply="Same words.", build=["p3", "m3"])
    run_eval.apply_manual_grades([new], grades)
    assert "manual_grade" not in new["score"]


def test_grade_ignored_when_request_errored():
    r = make_result(17, "impossible", {"errored": True, "valid": False}, reply="", success=False)
    run_eval.apply_manual_grades([r], grades_for(r, "correct"))
    assert "manual_grade" not in r["score"]
    assert r["score"].get("handled_correctly") is not True


def test_grade_without_fingerprint_is_not_applied():
    r = make_result(18, "impossible", {"handled_correctly": True}, reply="x", build=GOOD_IDS)
    run_eval.apply_manual_grades([r], {18: {"id": 18, "grade": "incorrect"}})
    assert "manual_grade" not in r["score"]
    assert r["score"]["needs_hand_grade"] is True


def test_saved_grades_match_saved_baseline_run():
    """The hand grades in manual_grades.json were made on the saved results.jsonl."""
    results = load_saved("results.jsonl")
    grades = run_eval.load_manual_grades(run_eval.MANUAL_GRADES_PATH)
    run_eval.apply_manual_grades(results, grades)
    got = {r["id"]: r["score"].get("manual_grade") for r in results if r["type"] == "impossible"}
    assert got == {16: "correct", 17: "partial", 18: "partial", 19: "incorrect", 20: "incorrect"}


# ─── Item 6: errored requests are left out of every rate ──────────────────────
def test_rates_exclude_errored_requests():
    ok_build = {"produced_build": True, "valid": True, "has_unknown": False,
                "judge_details": {"within_budget": "PASS"}}
    errored = {"errored": True, "valid": False}
    results = [
        make_result(1, "normal_build", ok_build, build=GOOD_IDS),
        make_result(2, "normal_build", errored, success=False),
        make_result(11, "comparison", {"handled_correctly": True}),
        make_result(12, "comparison", errored, success=False),
        make_result(21, "off_topic", {"handled_correctly": True}),
    ]
    m = run_eval.compute_metrics(results)
    assert m["valid"] == (1, 1)
    assert m["success"] == (1, 1)
    assert m["refused"] == (0, 1)
    assert m["unknown"] == (0, 1)
    assert m["comparison"] == (1, 1)
    assert m["off_topic"] == (1, 1)
    assert m["errored"] == {"normal_build": 1, "comparison": 1}
    md = run_eval.render_eval_md(results, m, 5, "2026-01-01 00:00")
    assert "| Errored requests (left out of every rate) | 2" in md


# ─── Item 7: tighter comparison and vague checks ──────────────────────────────
def test_comparison_word_alone_is_not_enough():
    # Before: any reply containing "compar" counted as a correct comparison.
    assert run_eval.score_comparison("I cannot assist with comparing those.", None, [])["handled_correctly"] is False
    assert run_eval.score_comparison("Compare it yourself, here is a build.", None, GOOD_IDS)["handled_correctly"] is False


def test_comparison_with_table_or_real_answer_is_correct():
    table = {"headers": ["Spec", "A", "B"], "rows": [["Price", "1", "2"]], "verdict": "A"}
    assert run_eval.score_comparison("A is better.", table, [])["handled_correctly"] is True
    assert run_eval.score_comparison("The RTX 4060 offers better frame rates.", None, [])["handled_correctly"] is True


def test_vague_stray_question_mark_is_not_a_question():
    # A "?" inside a URL is not a clarifying question.
    s = run_eval.score_vague("See https://shop.example/?id=5 for parts.", [])
    assert s["asked_question"] is False
    assert s["handled_correctly"] is False


def test_vague_question_does_not_rescue_a_failing_full_build():
    s = run_eval.score_vague("Any preferences? Here is a full build anyway.", FAILING_IDS)
    assert s["handled_correctly"] is False


def test_vague_real_clarifying_question_is_correct():
    s = run_eval.score_vague("What is your budget and what will you use it for?", [])
    assert s["handled_correctly"] is True


# ─── The committed baseline numbers stay reproducible ─────────────────────────
def test_rescoring_saved_builds_gives_same_scores():
    """Re-scoring the saved replies with the tightened rules changes nothing.

    Comparisons are skipped: results.jsonl never saved comparisonData, so they cannot be
    re-scored from disk."""
    for r in load_saved("results.jsonl"):
        if r["type"] == "comparison":
            continue
        new = run_eval.score_result(r["type"], r["success"], r["reply"], r["build_part_ids"],
                                    r["critique"], None, r["budget"])
        # Only the verdicts must match. Rule names and the "unknown" flag change on
        # purpose: the judge is now checker.py (9 rules, incl. cooler height).
        for key in ("valid", "handled_correctly"):
            assert new.get(key) == r["score"].get(key), (r["id"], key)


def test_importing_run_eval_has_no_side_effects():
    # main() exists and was not run: importing did not need a backend.
    assert callable(run_eval.main)


# ─── Same judge for the old and the new system (written BEFORE the change) ─────
# On 20 Nov the new system answers with catalogue IDs like "cpu_46f1874d7b4d".
# The runner used compat.py, which only knows the 24 old parts, so every new build
# would have been "unknown part -> invalid" (0%). Both systems must be scored by
# the same judge: checker.py, with parts looked up the same way as the new tools.

CATALOGUE_BUILD = {
    "cpu_aaa": {"_id": "cpu_aaa", "name": "AMD Ryzen 5 7600", "category": "processor",
                "socket": "AM5", "ram_type": "DDR5", "tdp": 65, "price_inr": 18000},
    "mb_bbb": {"_id": "mb_bbb", "name": "B650 board", "category": "motherboard",
               "socket": "AM5", "ram_type": "DDR5", "form_factor": "ATX", "price_inr": 15000},
    "gpu_ccc": {"_id": "gpu_ccc", "name": "RTX 4060 card", "category": "gpu",
                "tdp": 115, "length": 240, "price_inr": 30000},
    "ram_ddd": {"_id": "ram_ddd", "name": "DDR5 kit", "category": "ram", "ram_type": "DDR5", "price_inr": 8000},
    "ps_eee": {"_id": "ps_eee", "name": "NVMe SSD", "category": "ps", "price_inr": 6000},
    "ss_fff": {"_id": "ss_fff", "name": "HDD", "category": "ss", "price_inr": 4000},
    "psu_ggg": {"_id": "psu_ggg", "name": "650W PSU", "category": "psu", "wattage": 650, "price_inr": 6000},
    "cab_hhh": {"_id": "cab_hhh", "name": "ATX case", "category": "cabinet",
                "case_type": "ATX Mid Tower", "price_inr": 5000},
    "cool_iii": {"_id": "cool_iii", "name": "Air cooler", "category": "cooling",
                 "cooler_kind": "air", "price_inr": 2000},
}


def test_new_catalogue_part_ids_are_judged_not_rejected():
    score = run_eval.score_normal_build(list(CATALOGUE_BUILD), budget=100000, part_lookup=CATALOGUE_BUILD)
    assert score["unknown_ids"] == []
    assert score["valid"] is True


def test_runner_uses_the_same_rules_as_the_new_checker():
    score = run_eval.score_normal_build(GOOD_IDS, budget=80000)
    assert "cooler_height" in score["judge_details"]
    assert "within_budget" in score["judge_details"]


def test_metrics_include_fully_verified_and_median_time():
    results = [
        make_result(1, "normal_build", {"produced_build": True, "valid": True, "fully_verified": True}),
        make_result(2, "normal_build", {"produced_build": True, "valid": True, "fully_verified": False}),
        make_result(3, "normal_build", {"produced_build": True, "valid": False, "fully_verified": False}),
    ]
    for r, t in zip(results, (1.0, 2.0, 30.0)):
        r["elapsed_s"] = t
    m = run_eval.compute_metrics(results)
    assert m["fully_verified"] == (1, 3)
    assert m["median_time"] == 2.0   # one slow request can't drag the middle value


def test_baseline_rescored_with_the_new_judge():
    """
    The numbers the 20 Nov system will be compared against: the SAVED 8 Nov replies
    (no new requests) re-scored by the current scorer and checker.py.
    """
    results = run_eval.rescore_results(load_saved("results.jsonl"))
    run_eval.apply_manual_grades(results, run_eval.load_manual_grades(run_eval.MANUAL_GRADES_PATH))
    m = run_eval.compute_metrics(results)
    # Same as published on 8 Nov:
    assert m["valid"] == (4, 10)
    assert m["within_budget"] == (5, 9)
    assert m["success"] == (4, 10)
    assert m["refused"] == (0, 10)
    assert m["comparison"] == (5, 5)
    assert m["impossible_label"] == "1 correct, 2 partial, 2 incorrect (hand-graded)"
    assert m["off_topic"] == (4, 5)
    assert m["vague"] == (4, 5)
    # Different, because the new judge has more rules (cooler height can't be checked
    # for the old parts), so no old build is fully verified:
    assert m["fully_verified"] == (0, 10)
    assert m["unknown"] == (10, 10)
