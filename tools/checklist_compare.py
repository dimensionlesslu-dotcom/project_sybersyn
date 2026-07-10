#!/usr/bin/env python3
"""
checklist_compare.py — Project Cybersyn 验收清单对比器

对比 r(t) 需求清单与实际产物 y(t)，自动生成 缺失/多余/错误 三项清单。
支持 code 和 text 两种模式。

用法示例:
  checklist_compare.py --requirements '[{"id":"R1","description":"...","test_cmd":"pytest test.py"}]' --actual "@output.txt" --mode code
  checklist_compare.py --requirements '@reqs.json' --actual "some text content" --mode text --baseline ./baseline/
"""

import argparse
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


# ── 加载 ──────────────────────────────────────────────────
def load_requirements(source: str) -> list[dict]:
    """从 JSON 字符串或 @file.json 加载需求列表。"""
    if source.startswith("@"):
        path = source[1:]
        if not os.path.exists(path):
            raise FileNotFoundError(f"需求文件不存在: {path}")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        data = json.loads(source)
    if not isinstance(data, list):
        raise ValueError("requirements 必须是 JSON 数组")
    # 自动补全 id
    for i, r in enumerate(data):
        if "id" not in r:
            r["id"] = f"auto-R{i + 1}"
        if "severity" not in r:
            r["severity"] = "medium"
    return data


def load_actual(source: str) -> str:
    """从 @file 或直接文本获取 y(t)。"""
    if source.startswith("@"):
        path = source[1:]
        if not os.path.exists(path):
            raise FileNotFoundError(f"产物文件不存在: {path}")
        return Path(path).read_text(encoding="utf-8")
    return source


# ── 代码模式 ──────────────────────────────────────────────
def run_test(test_cmd: str, timeout: int) -> tuple:
    """运行测试命令，返回 (passed: bool|None, output: str)。None=超时。"""
    try:
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, (result.stdout + "\n" + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"


def check_baseline_diff(baseline_path: str, requirements: list) -> list[dict]:
    """检测新增/修改文件中未在 requirements 引用的项。"""
    extras = []
    req_keywords = set()
    for r in requirements:
        desc = r.get("description", "") + " " + (r.get("test_cmd") or "")
        req_keywords.update(re.findall(r'\b\w+\b', desc.lower()))

    if not os.path.exists(baseline_path):
        return extras

    # 简化实现：列出目录中的所有 .py 文件，检测未引用的
    for root, dirs, files in os.walk(baseline_path):
        for f in files:
            if f.endswith(('.py', '.ts', '.js', '.go', '.rs')):
                name_no_ext = f.rsplit('.', 1)[0]
                # 检查文件名/类名是否在需求关键词中
                if name_no_ext.lower() not in req_keywords and f.lower() not in req_keywords:
                    extras.append({
                        "description": f"文件 {f} 未在任何 requirement 中引用",
                        "location": os.path.join(root, f),
                        "severity": "medium",
                    })
    return extras[:20]  # 上限防止过多


def compare_code(requirements: list, actual: str, baseline: str, timeout: int) -> dict:
    """代码模式主逻辑。"""
    missing, wrong, unverified = [], [], []
    covered = 0

    for req in requirements:
        test_cmd = req.get("test_cmd")
        if test_cmd:
            passed, output = run_test(test_cmd, timeout)
            if passed is None:
                unverified.append({
                    "requirement_id": req["id"],
                    "description": req.get("description", ""),
                    "reason": f"测试超时 ({timeout}s): {test_cmd}",
                    "severity": req.get("severity", "medium"),
                })
            elif passed:
                covered += 1
            else:
                wrong.append({
                    "requirement_id": req["id"],
                    "description": req.get("description", ""),
                    "expected": req.get("expected", "测试通过"),
                    "actual": output[:500],
                    "severity": req.get("severity", "medium"),
                })
        else:
            # 无 test_cmd：在 actual 中搜索相关关键词
            kw = re.findall(r'\b\w+\b', req.get("description", "").lower())
            matched = any(k in actual.lower() for k in kw if len(k) > 3)
            if matched:
                unverified.append({
                    "requirement_id": req["id"],
                    "description": req.get("description", ""),
                    "reason": "无 test_cmd，通过关键词匹配检测到相关变更（需 Agent 确认）",
                    "severity": req.get("severity", "medium"),
                })
            else:
                missing.append({
                    "requirement_id": req["id"],
                    "description": req.get("description", ""),
                    "reason": "无 test_cmd 且未检测到相关代码变更",
                    "severity": req.get("severity", "medium"),
                })

    extras = check_baseline_diff(baseline, requirements) if baseline else []

    return _build_result(missing, extras, wrong, unverified, len(requirements), covered)


# ── 文本模式 ──────────────────────────────────────────────
def keyword_match(criterion: dict, actual: str) -> dict:
    """对单条 criterion 做关键词匹配。"""
    keywords = criterion.get("keywords", [])
    if not keywords:
        keywords = re.findall(r'\b\w{3,}\b', criterion.get("criterion", "").lower())
    matched = []
    missed = []
    for kw in keywords:
        if re.search(re.escape(kw), actual, re.IGNORECASE):
            matched.append(kw)
        else:
            missed.append(kw)
    rate = len(matched) / len(keywords) if keywords else 0
    status = "covered" if rate >= 0.8 else ("partial" if rate >= 0.3 else "missing")
    return {"status": status, "match_rate": rate, "matched_kw": matched, "missed_kw": missed}


def detect_text_extra(actual: str, all_keywords: set) -> list[dict]:
    """检测文本中超出需求的段落/要点。"""
    extras = []
    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', actual)
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if len(para) < 30:
            continue
        # 计算与所有关键词的相似度
        max_sim = max(
            (SequenceMatcher(None, para.lower(), kw.lower()).ratio() for kw in all_keywords),
            default=1.0
        )
        if max_sim < 0.3:
            extras.append({
                "description": f"段落 {i + 1} 与需求关键词相似度低",
                "snippet": para[:200],
                "similarity": round(max_sim, 2),
                "severity": "low",
            })
    return extras[:15]


def compare_text(requirements: list, actual: str) -> dict:
    """文本模式主逻辑。"""
    missing, extra, wrong, unverified = [], [], [], []
    covered = 0
    all_kw = set()

    for req in requirements:
        kw = req.get("keywords", [])
        all_kw.update(k.lower() for k in kw)

    for req in requirements:
        result = keyword_match(req, actual)
        if result["status"] == "covered":
            covered += 1
        elif result["status"] == "partial":
            wrong.append({
                "requirement_id": req["id"],
                "description": req.get("criterion", req.get("description", "")),
                "expected": f"包含关键词: {result['missed_kw']}",
                "actual": "部分匹配",
                "severity": req.get("severity", "medium"),
            })
        else:
            missing.append({
                "requirement_id": req["id"],
                "description": req.get("criterion", req.get("description", "")),
                "reason": f"未匹配关键词: {result['missed_kw']}",
                "severity": req.get("severity", "medium"),
            })

    extras = detect_text_extra(actual, all_kw)
    return _build_result(missing, extras, wrong, unverified, len(requirements), covered)


# ── 公共 ──────────────────────────────────────────────────
def _build_result(missing: list, extra: list, wrong: list, unverified: list,
                  total: int, covered: int) -> dict:
    return {
        "missing": missing,
        "extra": extra,
        "wrong": wrong,
        "unverified": unverified,
        "summary": {
            "total": total,
            "covered": covered,
            "missing": len(missing),
            "extra": len(extra),
            "wrong": len(wrong),
            "unverified": len(unverified),
        },
        "suggested_deviation_type": suggest_deviation_type(missing, extra, wrong, unverified, total),
    }


def suggest_deviation_type(missing: list, extra: list, wrong: list, unverified: list, total: int) -> str:
    """推断偏差类型。"""
    if total == 0:
        return "B"
    unverified_ratio = len(unverified) / total
    if unverified_ratio > 0.5:
        return "B"
    if len(extra) > (len(missing) + len(wrong) + 1):
        return "C"
    return "A"


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 验收清单对比器")
    parser.add_argument("--requirements", required=True, help="JSON 数组或 @file.json")
    parser.add_argument("--actual", required=True, help="文本内容或 @file")
    parser.add_argument("--mode", default="code", choices=["code", "text"])
    parser.add_argument("--baseline", help="基线目录路径（code mode extra 检测）")
    parser.add_argument("--test-timeout", type=int, default=60, dest="test_timeout")
    parser.add_argument("--format", default="json", choices=["json", "text"])

    args = parser.parse_args()

    try:
        requirements = load_requirements(args.requirements)
        actual = load_actual(args.actual)

        if not requirements:
            result = {
                "missing": [], "extra": [], "wrong": [], "unverified": [],
                "summary": {"total": 0, "covered": 0, "missing": 0, "extra": 0, "wrong": 0, "unverified": 0},
                "suggested_deviation_type": "B",
                "warning": "无验收标准，无法自动对比",
            }
        elif args.mode == "code":
            result = compare_code(requirements, actual, args.baseline, args.test_timeout)
        else:
            result = compare_text(requirements, actual)

        if args.format == "text":
            s = result["summary"]
            print(f"总计: {s['total']}  |  通过: {s['covered']}  |  缺失: {s['missing']}  |  多余: {s['extra']}  |  错误: {s['wrong']}  |  未验证: {s['unverified']}")
            print(f"建议偏差类型: {result.get('suggested_deviation_type', '?')}")
            for cat, label in [("missing", "缺失"), ("extra", "多余"), ("wrong", "错误"), ("unverified", "未验证")]:
                items = result.get(cat, [])
                if items:
                    print(f"\n--- {label} ({len(items)}) ---")
                    for item in items[:5]:
                        print(f"  [{item.get('severity','?')}] {item.get('description', item.get('requirement_id','?'))}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

        # exit code：有 critical 错误时返回 1
        has_critical = any(
            item.get("severity") == "critical"
            for cat in ("missing", "extra", "wrong")
            for item in result.get(cat, [])
        )
        if has_critical:
            sys.exit(1)

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
