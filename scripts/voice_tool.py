#!/usr/bin/env python3
"""Chinese personal-voice helpers. Standard library only, no network."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import uuid

DIMENSIONS = dict(zip(["D%02d" % i for i in range(1, 10)], [
    "用词与搭配", "句式与语序", "节奏与信息密度", "思路展开", "解释与论证",
    "语气与判断力度", "听众关系", "情绪与修辞", "场景变化与表达边界"]))
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002a6df]")
CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002a6df]+")
END = re.compile(r"""(?:[。！？!?]+|(?<!\.)\.(?!\.)(?=\s|$|[”’"」』]))[”’"」』]*""")
MARKERS = ("其实", "就是", "所以", "但是", "不过", "可能", "大概", "一定", "必须",
           "比如", "例如", "换句话说", "说白了", "你看", "我觉得", "我认为", "也就是说")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex[:10] + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def clean_markup(text):
    text = re.sub(r"(?s)\A---\s*\n.*?\n---\s*(?:\n|$)", "", text, count=1)
    text = re.sub(r"(?ms)^\s*(\x60{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"\x60([^\x60\n]+)\x60", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text.strip()


def content_chars(text):
    return sum(c.isalnum() for c in text)


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if content_chars(p)]


def sentences(text):
    out = []
    for p in paragraphs(text):
        start = 0
        for match in END.finditer(p):
            item = p[start:match.end()].strip()
            if content_chars(item):
                out.append(item)
            start = match.end()
        if content_chars(p[start:]):
            out.append(p[start:].strip())
    return out


def summary(values):
    if not values:
        return dict(count=0, mean=None, median=None, p10=None, p90=None, stdev=None)
    vals = sorted(values)
    def percentile(q):
        pos = (len(vals) - 1) * q
        low, high = int(pos), min(int(pos) + 1, len(vals) - 1)
        return round(vals[low] + (vals[high] - vals[low]) * (pos - low), 2)
    return dict(count=len(vals), mean=round(statistics.mean(vals), 2),
                median=round(statistics.median(vals), 2), p10=percentile(.1),
                p90=percentile(.9), stdev=round(statistics.pstdev(vals), 2))


def metrics_for(texts):
    cleaned = [clean_markup(t) for t in texts]
    text = "\n\n".join(cleaned)
    denom = content_chars(text)
    lens = [content_chars(s) for t in cleaned for s in sentences(t)]
    grams = Counter()
    for run in CJK_RUN.findall(text):
        for n in (2, 3, 4):
            grams.update(run[i:i+n] for i in range(max(0, len(run)-n+1)))
    return {
        "content_chars": denom, "chinese_chars": len(CJK.findall(text)),
        "latin_word_count": len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", text)),
        "sentence_chars": summary(lens),
        "paragraph_chars": summary([content_chars(p) for t in cleaned for p in paragraphs(t)]),
        "short_sentence_share_le15": round(sum(n <= 15 for n in lens)/len(lens), 4) if lens else None,
        "punctuation_per_1000_content_chars": {c: round(text.count(c)*1000/denom, 3) if denom else None for c in "，。！？；：、…—（）!?;:"},
        "marker_literal_counts": {s: text.count(s) for s in MARKERS},
        "repeated_character_ngrams": [{"text": s, "count": n} for s, n in grams.most_common() if n >= 2][:25],
    }


def load_manifest(path):
    path = Path(path).resolve()
    data = read_json(path)
    if data.get("schema_version") != "1.0" or not isinstance(data.get("segments"), list):
        raise ValueError("manifest 需要 schema_version=1.0 和 segments 数组")
    entries, ids, source_splits, hash_splits, seen = [], set(), {}, {}, set()
    for raw in data["segments"]:
        required = ("id", "source_id", "path", "context", "source_kind", "authorship", "split")
        if not isinstance(raw, dict) or any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in required):
            raise ValueError("每段需非空字符串：" + ", ".join(required))
        if raw["id"] in ids:
            raise ValueError("重复 segment id: " + raw["id"])
        ids.add(raw["id"])
        if raw["authorship"] not in {"user", "ai", "edited_ai", "third_party", "mixed"} or raw["split"] not in {"train", "holdout", "exclude"}:
            raise ValueError("未知 authorship/split: " + raw["id"])
        if raw["context"] in {"all", "task"} or raw["context"].startswith("register:"):
            raise ValueError("语料 context 需要具体场景")
        if raw["source_kind"] == "speech_transcript" and not isinstance(raw.get("asr_verified"), bool):
            raise ValueError("讲话转写需声明 asr_verified 布尔值")
        src = Path(raw["path"]).expanduser()
        src = src if src.is_absolute() else path.parent / src
        if src.suffix.lower() not in {".txt", ".md"} or not src.is_file():
            raise ValueError("语料须为明确列出的 txt/md 文件: " + str(src))
        text = src.read_text(encoding="utf-8-sig")
        normalized = re.sub(r"\s+", "", clean_markup(text))
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        if raw["authorship"] == "user" and raw["split"] in {"train", "holdout"} and content_chars(normalized):
            source_splits.setdefault(raw["source_id"], set()).add(raw["split"])
            hash_splits.setdefault(digest, set()).add(raw["split"])
        duplicate = raw["split"] == "train" and raw["authorship"] == "user" and digest in seen
        usable = raw["authorship"] == "user" and raw["split"] == "train" and bool(content_chars(normalized)) and not duplicate
        if usable:
            seen.add(digest)
        entries.append(dict(raw, text=text, sha256=digest, usable=usable, duplicate=duplicate))
    if any(len(v) > 1 for v in source_splits.values()):
        raise ValueError("同一来源跨 train/holdout，验证泄漏")
    if any(len(v) > 1 for v in hash_splits.values()):
        raise ValueError("重复文本跨 train/holdout，验证泄漏")
    fingerprint = hashlib.sha256(json.dumps(
        [{k: e.get(k) for k in ("id", "source_id", "context", "source_kind", "authorship", "split", "asr_verified", "sha256")} for e in entries],
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return data, entries, fingerprint


def make_metrics(path):
    data, entries, fingerprint = load_manifest(path)
    usable = [e for e in entries if e["usable"]]
    warnings = []
    if not usable:
        warnings.append("无本人原创训练片段，未建立个人基线。")
    if any(e["source_kind"] == "speech_transcript" for e in usable):
        warnings.append("转写标点不能直接认定为本人书写习惯。")
    if any(e["source_kind"] == "speech_transcript" and not e["asr_verified"] for e in usable):
        warnings.append("存在未校对 ASR，句长与节奏仅作低置信参考。")
    if not any(e["split"] == "holdout" and e["authorship"] == "user" for e in entries):
        warnings.append("无独立留出集，不能声称通过留出验证。")
    return {
        "tool_version": "1.0.0", "author_id": data.get("author_id"),
        "corpus_fingerprint": fingerprint, "created_at": now(),
        "measurement": {
            "sentence_unit": "每个汉字/英文字母/数字计1字符，排除标点与空白；不是词数。",
            "segmentation": "中文。！？及!?断句；英文句点只在边界断句，小数点保留；段末无句号片段计一句。",
            "paragraphs": "空行分段，单换行不自动当新句。",
            "lexicon": "中文2-4字符片段非分词；表达按字面子串计数，有重叠可能。",
            "limitations": "不自动测定思维、情绪、作者身份或本人风格相似度。",
        },
        "included_ids": [e["id"] for e in usable],
        "excluded": [{k: e[k] for k in ("id", "authorship", "split", "duplicate")} for e in entries if not e["usable"]],
        "by_context": {c: metrics_for([e["text"] for e in usable if e["context"] == c]) for c in sorted({e["context"] for e in usable})},
        "overall": metrics_for([e["text"] for e in usable]), "warnings": warnings,
    }


def template(author_id):
    return {
        "schema_version": "1.0", "author_id": author_id, "revision": 0, "status": "untrained",
        "updated_at": now(), "corpus_fingerprint": "", "calibrated_contexts": [],
        "context_registers": {"wechat": "wechat", "academic": "academic", "report": "report",
                              "spoken": "spoken", "casual": "casual"},
        "dimensions": {k: {"name": v, "status": "unobserved", "rules": []} for k, v in DIMENSIONS.items()},
        "validation": [],
    }


def events_at(root):
    path = Path(root)/"feedback.jsonl"
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()] if path.exists() else []


def all_rules(profile):
    return [r for b in profile.get("dimensions", {}).values() for r in b.get("rules", [])]

def scope_matches(profile, scopes, context):
    register = profile.get("context_registers", {}).get(context)
    return ("all" in scopes or context in scopes or
            (register is not None and "register:" + register in scopes))


def validate_profile(profile, manifest_path, events):
    data, entries, fingerprint = load_manifest(manifest_path)
    errors = []
    if profile.get("schema_version") != "1.0":
        errors.append("未知 profile schema_version")
    if profile.get("author_id") != data.get("author_id"):
        errors.append("profile 与 manifest 作者不一致")
    if profile.get("status") not in {"untrained", "provisional", "calibrated"}:
        errors.append("未知档案状态")
    if set(profile.get("dimensions", {})) != set(DIMENSIONS):
        errors.append("必须保留 D01-D09，缺证据可标 unobserved")
    context_registers = profile.get("context_registers", {})
    if not isinstance(context_registers, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip()
            for k, v in context_registers.items()):
        errors.append("context_registers 须为场景到文体的明确映射")
        context_registers = {}
    lookup, feedback, rule_ids = {e["id"]: e for e in entries}, {e["id"]: e for e in events}, set()
    for dimension, block in profile.get("dimensions", {}).items():
        if block.get("status") not in {"unobserved", "observed"} or not isinstance(block.get("rules"), list):
            errors.append("维度结构无效: " + dimension)
            continue
        if block["status"] == "unobserved" and any(r.get("state") == "active" for r in block["rules"]):
            errors.append("活动规则不能归入 unobserved: " + dimension)
        for r in block["rules"]:
            rid = r.get("id", "")
            if not rid or rid in rule_ids:
                errors.append("缺失/重复规则 id: " + rid)
            rule_ids.add(rid)
            if not isinstance(r.get("directive"), str) or not r["directive"].strip():
                errors.append(rid + ": 缺可执行规则")
            scopes = r.get("scope", [])
            if not isinstance(scopes, list) or not scopes or any(not isinstance(s, str) or not s.strip() for s in scopes):
                errors.append(rid + ": scope 须为非空字符串数组")
                scopes = []
            if "task" in scopes or ("all" in scopes and len(scopes) > 1):
                errors.append(rid + ": task 不能为长期规则，all 不与其他范围混用")
            families = [s.split(":", 1)[1] for s in scopes if s.startswith("register:")]
            if any(f not in context_registers.values() for f in families):
                errors.append(rid + ": 文体范围未在 context_registers 中登记")
            if families and r.get("origin") != "feedback":
                errors.append(rid + ": 文体范围继承仅用于本人明确持续反馈")
            if r.get("state") not in {"active", "superseded"}:
                errors.append(rid + ": 未知 state")
            if r.get("confidence") not in {"tentative", "supported", "user_confirmed"}:
                errors.append(rid + ": 未知 confidence")
            sources, contexts = set(), set()
            for ev in r.get("evidence", []):
                entry, quote = lookup.get(ev.get("segment_id")), ev.get("quote")
                if not entry or not entry["usable"]:
                    errors.append(rid + ": 证据须为去重后的本人原创训练片段")
                    continue
                if not isinstance(quote, str) or not quote.strip() or quote not in entry["text"]:
                    errors.append(rid + ": 引文无法逐字回查")
                sources.add(entry["source_id"])
                contexts.add(entry["context"])
            fids = r.get("feedback_ids", [])
            valid_feedback = [feedback[f] for f in fids if f in feedback]
            if any(f not in feedback for f in fids):
                errors.append(rid + ": 反馈事件不存在")
            if r.get("origin") == "corpus":
                if not r.get("evidence"):
                    errors.append(rid + ": 语料规则缺原句")
                if r.get("confidence") == "supported" and len(sources) < 2:
                    errors.append(rid + ": supported 需两个独立来源")
                if "all" in scopes and len(contexts) < 2 and not any(e.get("scope") == "all" and e.get("persistent") for e in valid_feedback):
                    errors.append(rid + ": 单场景不能推出 all")
                if scopes and "all" not in scopes and not set(scopes).issubset(contexts):
                    errors.append(rid + ": 范围超出证据场景")
            elif r.get("origin") == "feedback":
                if not any(e.get("persistent") and [e.get("scope")] == scopes and e.get("dimension") == dimension and e.get("rule") == r.get("directive") for e in valid_feedback):
                    errors.append(rid + ": 反馈关联/范围/规则不匹配")
            else:
                errors.append(rid + ": 未知 origin")
            if r.get("confidence") == "user_confirmed" and not valid_feedback:
                errors.append(rid + ": user_confirmed 缺本人反馈")
    if profile.get("status") == "untrained" and all_rules(profile):
        errors.append("有规则后状态应为 provisional")
    calibrated = profile.get("calibrated_contexts", [])
    if profile.get("status") != "calibrated" and calibrated:
        errors.append("未校准状态不能保留校准场景")
    if profile.get("status") == "calibrated":
        if not calibrated:
            errors.append("calibrated 缺场景")
        if not any(e["usable"] for e in entries) or not any(r.get("state") == "active" for r in all_rules(profile)):
            errors.append("calibrated 需要真实训练语料及活动风格规则")
        if fingerprint != profile.get("corpus_fingerprint"):
            errors.append("语料变化或未记录 fingerprint，需要复测")
        for context in calibrated:
            if not any(v.get("context") == context and v.get("test_type") in {"held_out", "new_topic"}
                       and v.get("evaluated_revision") == profile.get("revision")
                       and v.get("user_accepted") is True and v.get("content_ok") is True
                       and v.get("unresolved") == [] and v.get("user_feedback") and v.get("date")
                       and v.get("context_isolation") in {"independent", "not_independent"}
                       for v in profile.get("validation", [])):
                errors.append("缺本人认可的新题/留出验证: " + context)
    return errors


def init_profile(root, author_id):
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("档案已有内容，拒绝覆盖")
    root.mkdir(parents=True, exist_ok=True)
    save_json(root/"manifest.json", {"schema_version": "1.0", "author_id": author_id, "segments": []})
    save_json(root/"profile.json", template(author_id))
    return {"status": "untrained", "root": str(root.resolve()), "message": "尚无本人语料或风格结论"}


def feedback_command(args):
    root = Path(args.root)
    profile, events = read_json(root/"profile.json"), events_at(root)
    errors = validate_profile(profile, root/"manifest.json", events)
    if errors:
        raise ValueError("现有档案需先修复: " + "; ".join(errors))
    if args.persist_rule and (args.scope == "task" or not args.rule.strip() or not args.scope.strip()):
        raise ValueError("长期规则需具体场景或 all，以及非空 --rule")
    if args.supersedes and not args.persist_rule:
        raise ValueError("supersedes 仅适用于长期规则")
    if not args.request.strip():
        raise ValueError("反馈需有用户原话")
    event = dict(id="F-"+uuid.uuid4().hex[:12], created_at=now(), dimension=args.dimension,
                 scope=args.scope, request=args.request, before=args.before, after=args.after,
                 after_origin=getattr(args, "after_origin", "unknown"),
                 rule=args.rule, persistent=args.persist_rule, supersedes=args.supersedes)
    candidate = deepcopy(profile)
    if args.persist_rule:
        if args.supersedes:
            matched = [r for r in all_rules(candidate) if r["id"] == args.supersedes]
            if len(matched) != 1 or matched[0]["state"] != "active":
                raise ValueError("要替换的活动规则不存在")
            if matched[0]["scope"] != [args.scope]:
                raise ValueError("替换范围不一致，先人工拆分规则")
            matched[0]["state"] = "superseded"
        block = candidate["dimensions"][args.dimension]
        block["status"] = "observed"
        block["rules"].append(dict(
            id="R-"+uuid.uuid4().hex[:12], directive=args.rule, scope=[args.scope],
            confidence="user_confirmed", origin="feedback", state="active",
            evidence=[], feedback_ids=[event["id"]]))
        candidate.update(revision=candidate["revision"]+1, status="provisional",
                         calibrated_contexts=[], updated_at=now())
        errors = validate_profile(candidate, root/"manifest.json", events+[event])
        if errors:
            raise ValueError("; ".join(errors))
        backup = root/"history"/(now().replace(":", "-")+"-"+uuid.uuid4().hex[:6]+"-profile.json")
        save_json(backup, profile)
    with (root/"feedback.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False)+"\n")
    if args.persist_rule:
        save_json(root/"profile.json", candidate)
    return dict(event_id=event["id"], persisted_rule=args.persist_rule,
                profile_status=candidate["status"] if args.persist_rule else profile["status"])


def check_draft(root, draft, context):
    root = Path(root)
    profile = read_json(root/"profile.json")
    errors = validate_profile(profile, root/"manifest.json", events_at(root))
    if errors:
        raise ValueError("; ".join(errors))
    corpus, current = make_metrics(root/"manifest.json"), metrics_for([Path(draft).read_text(encoding="utf-8")])
    baseline, drift = corpus["by_context"].get(context), {}
    if baseline:
        for field in ("sentence_chars", "paragraph_chars"):
            target, actual = baseline[field]["mean"], current[field]["mean"]
            drift[field] = dict(baseline_mean=target, draft_mean=actual,
                               relative_change=round((actual-target)/target, 4) if target and actual is not None else None)
    return {
        "context": context, "profile_status": profile["status"],
        "context_calibrated": context in profile.get("calibrated_contexts", []),
        "draft_metrics": current, "baseline_available": baseline is not None,
        "descriptive_drift_only": drift,
        "applicable_rules": [r for r in all_rules(profile) if r["state"] == "active" and scope_matches(profile, r["scope"], context)],
        "human_checks": ["事实/数字/引用/因果限定", "原句对照与过量模仿", "文体适配", "本人认可"],
        "notice": "非相似度或自动通过证明；无同场景基线不回退至总体平均。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "status", "validate", "feedback", "check"):
        p = sub.add_parser(command)
        p.add_argument("--root", required=True)
        if command == "init":
            p.add_argument("--author-id", default="default")
        elif command == "feedback":
            p.add_argument("--dimension", choices=DIMENSIONS, required=True)
            p.add_argument("--scope", default="task")
            p.add_argument("--request", required=True)
            p.add_argument("--before", default="")
            p.add_argument("--after", default="")
            p.add_argument("--after-origin", choices=("user", "ai", "unknown"), default="unknown")
            p.add_argument("--rule", default="")
            p.add_argument("--persist-rule", action="store_true")
            p.add_argument("--supersedes")
        elif command == "check":
            p.add_argument("--draft", required=True)
            p.add_argument("--context", required=True)
            p.add_argument("--output", required=True)
    p = sub.add_parser("metrics")
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init_profile(args.root, args.author_id)
        elif args.command == "status":
            path = Path(args.root)/"profile.json"
            profile = read_json(path) if path.exists() else {}
            result = dict(root=str(Path(args.root).resolve()), status=profile.get("status", "missing"),
                          revision=profile.get("revision"), calibrated_contexts=profile.get("calibrated_contexts", []))
        elif args.command == "metrics":
            result = make_metrics(args.manifest)
            save_json(args.output, result)
        elif args.command == "validate":
            root = Path(args.root)
            errors = validate_profile(read_json(root/"profile.json"), root/"manifest.json", events_at(root))
            print(json.dumps(dict(valid=not errors, errors=errors, notice="结构/证据检查，不代表本人认可"), ensure_ascii=False, indent=2))
            return 1 if errors else 0
        elif args.command == "feedback":
            result = feedback_command(args)
        else:
            result = check_draft(args.root, args.draft, args.context)
            save_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

