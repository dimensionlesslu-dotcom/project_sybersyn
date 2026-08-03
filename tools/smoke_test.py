#!/usr/bin/env python3
"""
smoke_test.py — Project Cybersyn 工具链冒烟测试

覆盖:
  S1  L1 极简路径
  S2  L3 全流程 (含审计/移交/研讨厅)
  S3  错误路径 (Nmax/时滞/缺文件/坏JSON)
  S4  边缘情况 (lock/archive/query/migrate/pause/resume)

用法: cd tools && python smoke_test.py
"""

import json, os, subprocess, sys, tempfile, shutil
from pathlib import Path

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

TOOLS = Path(__file__).parent
PASS, FAIL = 0, 0
TMP = TOOLS / "_smoke_tmp"


def setup():
    TMP.mkdir(exist_ok=True)
    os.environ["CYBERSYN_STATE"] = str(TMP / "smoke_state.json")


def teardown():
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)


def run(*args, **kw):
    """运行工具，返回 (returncode, stdout, stderr)。工具统一输出 UTF-8。"""
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(TOOLS), **kw)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check(desc, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {desc}")
    else:
        FAIL += 1
        print(f"  FAIL  {desc}  {'— ' + detail if detail else ''}")


def json_out(stdout):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════
# S1  L1 极简路径: classify → init → checklist → update → convergence
# ═══════════════════════════════════════════════════════════════
def test_s1_l1_minimal():
    print("\n── S1 L1 极简路径 ──")
    global PASS, FAIL
    p0, f0 = PASS, FAIL

    # 1. classify
    rc, out, err = run("complexity_classify.py", "--task", "fix typo in login.py", "--files", "login.py", "--format", "json")
    d = json_out(out)
    check("S1.1 classify → L1", d and d.get("level") == "L1", f"got {d.get('level') if d else err}")

    # 2. init with enforce
    rc2, out2, _ = run("complexity_classify.py", "--task", "fix typo", "--files", "login.py", "--enforce", "--format", "json")
    enf = json_out(out2)
    check("S1.2 classify --enforce → minimal_path_only", enf and enf.get("enforce", {}).get("minimal_path_only") == True)

    # 3. init state
    rc3, out3, err3 = run("cybersyn_state.py", "init", "--level", "L1", "--task", "fix typo", "--output", str(TMP / "smoke_state.json"))
    check("S1.3 init L1 → ok", rc3 == 0, err3)

    # 4. verify init
    rc4, out4, _ = run("cybersyn_state.py", "read", "--field", "level")
    check("S1.4 read level → L1", json_out(out4) == "L1")

    # 5. validate
    rc5, out5, _ = run("cybersyn_state.py", "validate")
    check("S1.5 validate → valid", json_out(out5) == {"valid": True})

    # 6. checklist compare
    rc6, out6, _ = run("checklist_compare.py",
                       "--requirements", '[{"id":"R1","description":"fix typo","test_cmd":null}]',
                       "--actual", "fixed typo in login.py", "--mode", "text", "--format", "json")
    d6 = json_out(out6)
    check("S1.6 checklist → has summary", d6 and "summary" in d6, str(d6)[:80] if d6 else err)

    # 7. update feedback
    rc7, out7, _ = run("cybersyn_state.py", "update", "--stage", "feedback",
                       "--data", '{"e_missing":[],"e_extra":[],"e_wrong":[],"deviation_type":"A"}')
    check("S1.7 feedback update → ok", rc7 == 0, out7)

    # 8. update modify (L1: should NOT trigger safety since minimal_path_only)
    rc8, out8, err8 = run("cybersyn_state.py", "update", "--stage", "modify", "--data", '{"path":"A","k":"minor","changes":"fixed"}')
    check("S1.8 modify under L1 → ok (minimal path bypasses safety)", rc8 == 0, err8)

    # 9. convergence check
    rc9, out9, _ = run("convergence_check.py", "--state", str(TMP / "smoke_state.json"), "--format", "json")
    d9 = json_out(out9)
    check("S1.9 convergence → status present", d9 and "status" in d9, str(d9)[:80] if d9 else str(rc9))

    # 10. summary
    rc10, out10, _ = run("cybersyn_state.py", "summary")
    check("S1.10 summary → contains task name", "fix typo" in out10, out10[:80])

    passed = PASS - p0
    failed = FAIL - f0
    print(f"  S1: {passed} passed, {failed} failed")


# ═══════════════════════════════════════════════════════════════
# S2  L3 全流程 (模拟 3 轮迭代: 计划→反馈→修改→收敛  + 审计)
# ═══════════════════════════════════════════════════════════════
def test_s2_l3_full():
    print("\n── S2 L3 全流程 ──")
    global PASS, FAIL
    p0, f0 = PASS, FAIL

    state_path = str(TMP / "smoke_l3.json")
    os.environ["CYBERSYN_STATE"] = state_path

    # 1. init
    rc, out, err = run("cybersyn_state.py", "init", "--level", "L3", "--task", "refactor auth", "--output", state_path)
    check("S2.1 init L3 → ok", rc == 0, err)

    # 2. verify enforce
    d = json.loads(Path(state_path).read_text("utf-8"))
    enf = d.get("_enforce", {})
    check("S2.2 enforce.allow_audit", enf.get("allow_audit") == True)
    check("S2.3 enforce.allow_vsm", enf.get("allow_vsm") == True)
    check("S2.4 enforce.nmax", enf.get("nmax") == 5)

    # Simulate 3 rounds manually via JSON manipulation for speed
    rounds = [
        {"n": 1, "stage": "completed",
         "feedback": {"e_missing": [], "e_extra": [{"desc": "unused class", "severity": "medium"}],
                      "e_wrong": [{"desc": "500 error", "severity": "critical"}], "deviation_type": "A"},
         "modify": {"path": "A", "k": "local", "changes": "removed unused, fixed injection"},
         "test2": {"verdict": "continuing"}, "plan": {}, "test1": {}},
        {"n": 2, "stage": "completed",
         "feedback": {"e_missing": [{"desc": "missing test", "severity": "high"}], "e_extra": [],
                      "e_wrong": [], "deviation_type": "A"},
         "modify": {"path": "A", "k": "minor", "changes": "added missing test"},
         "test2": {"verdict": "continuing"}, "plan": {}, "test1": {}},
        {"n": 3, "stage": "completed",
         "feedback": {"e_missing": [], "e_extra": [], "e_wrong": [], "deviation_type": "A"},
         "modify": {"path": "A", "k": "minor", "changes": "verified all pass"},
         "test2": {"verdict": "converged"}, "plan": {}, "test1": {}},
    ]
    d["rounds"] = rounds
    d["round"] = 3
    d["audit_counter"] = 3
    d["requirement_evidence"] = [
        {"requirement_id": "R1", "status": "passed",
         "evidence": [{"kind": "test", "source": "smoke-test", "summary": "all checks passed",
                       "captured_at": "2026-01-01T00:00:00+00:00"}], "deviations": []},
    ]
    Path(state_path).write_text(json.dumps(d, ensure_ascii=False), "utf-8")

    # 5. convergence → converged
    rc5, out5, _ = run("convergence_check.py", "--state", state_path, "--format", "json")
    d5 = json_out(out5)
    check("S2.5 convergence → converged", d5 and d5.get("status") == "converged", str(d5)[:120] if d5 else "")

    # 6. convergence with energy
    rc6, out6, _ = run("convergence_check.py", "--state", state_path, "--energy", "--gain", "--format", "json")
    d6 = json_out(out6)
    check("S2.6 convergence --energy → has energy", d6 and "energy" in d6)
    check("S2.7 convergence --gain → has gain_analysis", d6 and "gain_analysis" in d6)

    # 7. audit trigger → should trigger (round 3, every 3)
    rc7, out7, _ = run("audit_trigger.py", "--state", state_path, "--format", "json")
    d7 = json_out(out7)
    check("S2.8 audit trigger → true (round=3, every=3)", d7 and d7.get("trigger") == True, str(d7)[:120] if d7 else "")

    # 8. audit auto-conclude → maintain
    rc8, out8, _ = run("audit_trigger.py", "--state", state_path, "--auto-conclude", "--format", "json")
    d8 = json_out(out8)
    check("S2.9 audit auto-conclude → maintain", d8 and d8.get("recommended_conclusion") == "maintain",
          str(d8.get("recommended_conclusion")) if d8 else "")

    # 9. apply-audit
    rc9, out9, _ = run("cybersyn_state.py", "apply-audit", "--conclusion", "maintain")
    check("S2.10 apply-audit maintain → ok", rc9 == 0, out9)

    # 10. handoff report (even though converged, should still generate)
    rc10, out10, _ = run("handoff_report.py", "--state", state_path, "--format", "json")
    d10 = json_out(out10)
    check("S2.11 handoff → has task", d10 and d10.get("task") == "refactor auth", str(d10)[:80] if d10 else "")

    # 11. diversity generator
    rc11, out11, _ = run("diversity_generator.py", "--task", "refactor auth", "--strategies", "3", "--format", "json")
    d11 = json_out(out11)
    check("S2.12 diversity → 3 strategies", d11 and len(d11.get("strategies", [])) == 3)
    check("S2.13 diversity → has divergence_matrix", d11 and "divergence_matrix" in d11)

    # 12. summary + archive
    rc12, out12, _ = run("cybersyn_state.py", "summary")
    check("S2.14 summary → non-empty", len(out12) > 10)

    rc13, out13, _ = run("cybersyn_state.py", "archive", "--target", str(TMP / "smoke_archive"))
    check("S2.15 archive → ok", rc13 == 0, out13)
    archive_file = TMP / "smoke_archive" / "archive.ndjson"
    check("S2.16 archive.ndjson exists", archive_file.exists())

    passed = PASS - p0
    failed = FAIL - f0
    print(f"  S2: {passed} passed, {failed} failed")


# ═══════════════════════════════════════════════════════════════
# S3  错误路径: Nmax 超限, 时滞增大, 缺文件, 坏 JSON, 死锁
# ═══════════════════════════════════════════════════════════════
def test_s3_error_paths():
    print("\n── S3 错误路径 ──")
    global PASS, FAIL
    p0, f0 = PASS, FAIL

    state_path = str(TMP / "smoke_err.json")
    os.environ["CYBERSYN_STATE"] = state_path

    # ---- 3.1 Nmax 超限 ----
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "err test", "--output", state_path, "--nmax", "2")

    # Simulate round > nmax
    d = json.loads(Path(state_path).read_text("utf-8"))
    d["rounds"] = [
        {"n": 1, "stage": "completed", "feedback": {"e_wrong": [{"desc": "b", "severity": "high"}], "e_missing": [], "e_extra": [], "deviation_type": "A"}, "modify": {}, "test2": {}, "plan": {}, "test1": {}},
        {"n": 2, "stage": "completed", "feedback": {"e_wrong": [{"desc": "b", "severity": "medium"}], "e_missing": [], "e_extra": [], "deviation_type": "A"}, "modify": {}, "test2": {}, "plan": {}, "test1": {}},
    ]
    d["round"] = 3
    d["_enforce"]["minimal_path_only"] = False
    Path(state_path).write_text(json.dumps(d, ensure_ascii=False), "utf-8")

    rc, out, err = run("cybersyn_state.py", "update", "--stage", "modify", "--data", '{"path":"A"}')
    check("S3.1 Nmax exceeded → SafetyBoundaryError", rc != 0, f"rc={rc}, err={err[:80]}")

    # ---- 3.2 时滞增大 (连续两轮偏差同向增大) ----
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "err2", "--output", state_path)
    d = json.loads(Path(state_path).read_text("utf-8"))
    d["rounds"] = [
        {"n": 1, "stage": "completed", "feedback": {"e_wrong": [{"desc": "b1"}], "e_missing": [], "e_extra": [], "deviation_type": "A"}, "modify": {}, "test2": {}, "plan": {}, "test1": {}},
        {"n": 2, "stage": "completed", "feedback": {"e_wrong": [{"desc": "b1"}, {"desc": "b2"}, {"desc": "b3"}], "e_missing": [], "e_extra": [], "deviation_type": "A"}, "modify": {}, "test2": {}, "plan": {}, "test1": {}},
    ]
    d["round"] = 2
    d["_enforce"]["minimal_path_only"] = False
    Path(state_path).write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    rc2, out2, err2 = run("cybersyn_state.py", "update", "--stage", "modify", "--data", '{"path":"A"}')
    check("S3.2 consecutive increase → SafetyBoundaryError", rc2 != 0, f"rc={rc2}")

    # ---- 3.3 缺状态文件 ----
    os.environ["CYBERSYN_STATE"] = str(TMP / "nonexistent.json")
    rc3, out3, err3 = run("cybersyn_state.py", "read", "--field", "level")
    check("S3.3 missing state file → error exit", rc3 != 0, f"rc={rc3}")

    # ---- 3.4 坏 JSON 数据 ----
    rc4, out4, err4 = run("cybersyn_state.py", "update", "--stage", "feedback", "--data", "not-valid-json")
    check("S3.4 invalid JSON data → error exit", rc4 != 0, f"rc={rc4}")

    # ---- 3.5 空需求清单 ----
    os.environ["CYBERSYN_STATE"] = state_path
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "err5", "--output", state_path)
    rc5, out5, _ = run("checklist_compare.py", "--requirements", "[]", "--actual", "anything", "--mode", "text", "--format", "json")
    d5 = json_out(out5)
    check("S3.5 empty requirements → warning", d5 and "warning" in d5, str(d5)[:80] if d5 else "")

    # ---- 3.6 死锁 ----
    os.environ["CYBERSYN_STATE"] = state_path
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "locktest", "--output", state_path)
    rc6a, _, _ = run("cybersyn_state.py", "lock", "--by", "agent-1")
    rc6b, out6b, err6b = run("cybersyn_state.py", "lock", "--by", "agent-2")
    check("S3.6 double lock → LockHeldError", rc6b != 0, f"rc={rc6b}, err={err6b[:60]}")
    run("cybersyn_state.py", "unlock", "--by", "agent-1")  # cleanup

    passed = PASS - p0
    failed = FAIL - f0
    print(f"  S3: {passed} passed, {failed} failed")


# ═══════════════════════════════════════════════════════════════
# S4  边缘情况: lock/unlock, archive, query, migrate, pause/resume
# ═══════════════════════════════════════════════════════════════
def test_s4_edge_cases():
    print("\n── S4 边缘情况 ──")
    global PASS, FAIL
    p0, f0 = PASS, FAIL

    state_path = str(TMP / "smoke_edge.json")
    os.environ["CYBERSYN_STATE"] = state_path
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "edge test", "--output", state_path)

    # ---- 4.1 lock/unlock 正常 ----
    rc1, _, _ = run("cybersyn_state.py", "lock", "--by", "agent-1")
    check("S4.1 lock → ok", rc1 == 0)
    rc1b, _, _ = run("cybersyn_state.py", "unlock", "--by", "agent-1")
    check("S4.2 unlock → ok", rc1b == 0)

    # ---- 4.2 query ----
    run("cybersyn_state.py", "update", "--stage", "feedback",
        "--data", '{"e_wrong":[{"desc":"critical bug in token refresh","severity":"critical"}],"e_missing":[],"e_extra":[],"deviation_type":"A"}')
    rc2, out2, _ = run("cybersyn_state.py", "query", "--pattern", "token", "--scope", "rounds", "--format", "json")
    d2 = json_out(out2)
    check("S4.2b query 'token' → 1 match", d2 and len(d2.get("matches", [])) >= 1, str(d2)[:80] if d2 else "")

    # ---- 4.3 archive + overwrite ----
    rc3, _, _ = run("cybersyn_state.py", "archive", "--target", str(TMP / "smoke_archive2"))
    check("S4.3 archive → ok", rc3 == 0)
    rc3b, _, _ = run("cybersyn_state.py", "archive", "--target", str(TMP / "smoke_archive2"), "--overwrite")
    check("S4.4 archive --overwrite → ok", rc3b == 0)

    # ---- 4.4 pause/resume ----
    rc4, _, _ = run("cybersyn_state.py", "pause", "--reason", "need user decision", "--options", "A,B,C")
    check("S4.5 pause → ok", rc4 == 0)
    # Verify paused
    d4 = json.loads(Path(state_path).read_text("utf-8"))
    check("S4.6 paused.active → true", d4.get("paused", {}).get("active") == True)
    check("S4.7 paused.options", d4.get("paused", {}).get("decision_options") == ["A", "B", "C"])

    rc4b, _, _ = run("cybersyn_state.py", "resume")
    check("S4.8 resume → ok", rc4b == 0)
    d4b = json.loads(Path(state_path).read_text("utf-8"))
    check("S4.9 paused.active → false after resume", d4b.get("paused", {}).get("active") == False)

    # ---- 4.5 apply-audit restructure ----
    run("cybersyn_state.py", "update", "--stage", "audit",
        "--data", '{"round":1,"conclusion":"maintain","questions":{"r_t_still_valid":true}}')
    rc5, _, _ = run("cybersyn_state.py", "apply-audit", "--conclusion", "restructure")
    check("S4.10 apply-audit restructure → ok", rc5 == 0)
    d5 = json.loads(Path(state_path).read_text("utf-8"))
    check("S4.11 nmax increased after restructure", d5.get("nmax") == 7, f"got {d5.get('nmax')}")  # 5 + 2
    check("S4.12 audit_every decreased", d5.get("audit_every") == 2, f"got {d5.get('audit_every')}")  # max(2, 3-1)

    # ---- 4.6 apply-audit upgrade-forum ----
    rc6, _, _ = run("cybersyn_state.py", "apply-audit", "--conclusion", "upgrade-forum")
    check("S4.13 apply-audit upgrade-forum → ok", rc6 == 0)
    d6 = json.loads(Path(state_path).read_text("utf-8"))
    check("S4.14 upgrade_to_forum → true", d6.get("upgrade_to_forum") == True)

    # ---- 4.7 migrate dry-run on v2.0 file ----
    rc7, out7, _ = run("cybersyn_state.py", "migrate", "--state", state_path, "--dry-run")
    check("S4.15 migrate v2.0 → already current", rc7 == 0)

    # ---- 4.8 patterns_summary auto-computed ----
    d8 = json.loads(Path(state_path).read_text("utf-8"))
    ps = d8.get("_patterns_summary", {})
    check("S4.16 patterns_summary.dominant_type", ps.get("dominant_type") is not None)
    check("S4.17 patterns_summary.convergence_trend", ps.get("convergence_trend") is not None)

    # ---- 4.9 validate ----
    rc9, out9, _ = run("cybersyn_state.py", "validate")
    check("S4.18 validate → valid", json_out(out9) == {"valid": True})

    # ---- 4.10 diversity with context ----
    rc10, out10, _ = run("diversity_generator.py", "--task", "edge test", "--context", state_path,
                          "--strategies", "3", "--format", "json")
    d10 = json_out(out10)
    check("S4.19 diversity with forum context → has strategies", d10 and len(d10.get("strategies", [])) == 3)
    check("S4.20 diversity context → upgrade_to_forum reflected",
          d10 and d10.get("context_from_state", {}).get("upgrade_to_forum") == True)

    # ---- 4.11 convergence --periodic --drift ----
    rc11, out11, _ = run("convergence_check.py", "--state", state_path, "--energy", "--periodic", "--drift", "--format", "json")
    d11 = json_out(out11)
    check("S4.21 convergence --periodic → has periodic key", d11 and "periodic" in d11)
    check("S4.22 convergence --drift → has env_drift key", d11 and "env_drift" in d11)

    passed = PASS - p0
    failed = FAIL - f0
    print(f"  S4: {passed} passed, {failed} failed")


# ═══════════════════════════════════════════════════════════════
# S5  轮次推进与重置: next-round / reset
# ═══════════════════════════════════════════════════════════════
def test_s5_round_lifecycle():
    print("\n── S5 next-round / reset ──")
    global PASS, FAIL
    p0, f0 = PASS, FAIL

    state_path = str(TMP / "smoke_s5.json")
    os.environ["CYBERSYN_STATE"] = state_path
    run("cybersyn_state.py", "init", "--level", "L3", "--task", "round lifecycle", "--output", state_path)

    # 5.1 next-round 推进
    rc1, out1, err1 = run("cybersyn_state.py", "next-round")
    check("S5.1 next-round → ok", rc1 == 0, err1)
    d1 = json.loads(Path(state_path).read_text("utf-8"))
    check("S5.2 round == 1", d1.get("round") == 1)

    # 5.2 再推进一轮，上一轮标记 completed
    rc2, _, _ = run("cybersyn_state.py", "next-round")
    d2 = json.loads(Path(state_path).read_text("utf-8"))
    check("S5.3 round == 2", d2.get("round") == 2)
    check("S5.4 previous round stage → completed", d2["rounds"][0].get("stage") == "completed")

    # 5.3 Nmax 边界: nmax=2 时第 3 轮禁止
    d2["nmax"] = 2
    Path(state_path).write_text(json.dumps(d2, ensure_ascii=False), "utf-8")
    rc3, _, err3 = run("cybersyn_state.py", "next-round")
    check("S5.5 next-round beyond nmax → SafetyBoundaryError", rc3 != 0, f"rc={rc3}")

    # 5.4 reset: 备份并重建
    rc4, out4, err4 = run("cybersyn_state.py", "reset")
    check("S5.6 reset → ok", rc4 == 0, err4)
    d4 = json.loads(Path(state_path).read_text("utf-8"))
    check("S5.7 reset → round 0, rounds empty", d4.get("round") == 0 and d4.get("rounds") == [])
    check("S5.8 reset → task preserved", d4.get("task") == "round lifecycle")
    check("S5.9 reset → backup created", (TMP / "smoke_s5.json.bak").exists())

    passed = PASS - p0
    failed = FAIL - f0
    print(f"  S5: {passed} passed, {failed} failed")


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    setup()
    try:
        test_s1_l1_minimal()
        test_s2_l3_full()
        test_s3_error_paths()
        test_s4_edge_cases()
        test_s5_round_lifecycle()

        print(f"\n{'='*50}")
        print(f"TOTAL: {PASS} passed, {FAIL} failed")
        if FAIL > 0:
            print("SOME SMOKE TESTS FAILED")
            sys.exit(1)
        else:
            print("ALL SMOKE TESTS PASSED")
    finally:
        teardown()
