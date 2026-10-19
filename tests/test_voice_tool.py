"""Behavior tests use synthetic material only; never the owner's corpus."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1]/"scripts"/"voice_tool.py"
spec = importlib.util.spec_from_file_location("voice_tool", SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="voice-test-")
        self.root = Path(self.tmp.name)
        v.init_profile(self.root, "synthetic")

    def tearDown(self):
        self.tmp.cleanup()

    def corpus(self, items):
        manifest = v.read_json(self.root/"manifest.json")
        manifest["segments"] = []
        for i, item in enumerate(items):
            base = dict(id="S"+str(i), source_id="source"+str(i), path=str(i)+".txt",
                        context="wechat", source_kind="article", authorship="user", split="train")
            base.update({k: val for k, val in item.items() if k != "text"})
            (self.root/base["path"]).write_text(item.get("text", "合成文字。"), encoding="utf-8")
            manifest["segments"].append(base)
        v.save_json(self.root/"manifest.json", manifest)
        return manifest

    def feedback(self, **kwargs):
        defaults = dict(root=str(self.root), dimension="D02", scope="task", request="这一段改顺一点",
                        before="旧句", after="新句", rule="", persist_rule=False, supersedes=None)
        defaults.update(kwargs)
        return v.feedback_command(argparse.Namespace(**defaults))

    def rule_profile(self, quote="先看一个例子。", scope=None, confidence="tentative"):
        p = v.read_json(self.root/"profile.json")
        p["status"] = "provisional"
        p["dimensions"]["D05"] = dict(name=v.DIMENSIONS["D05"], status="observed", rules=[
            dict(id="R1", directive="用具体例子解释概念", scope=scope or ["wechat"],
                 confidence=confidence, origin="corpus", state="active",
                 evidence=[dict(segment_id="S0", quote=quote)], feedback_ids=[])])
        return p

    def test_chinese_quotes_and_decimal(self):
        parts = v.sentences('他说：“先看看。”然后再试！值是3.14。GPT-4能用吗？')
        self.assertEqual(len(parts), 4)
        self.assertIn("3.14", parts[2])

    def test_english_mixed_boundaries_and_ellipsis(self):
        self.assertEqual(len(v.sentences("Version 3.14 works. 可以试试。等等……先别急。")), 3)
        self.assertEqual(v.content_chars("中文 A1。"), 4)

    def test_paragraph_and_line_wrapping(self):
        m = v.metrics_for(["这是一个\n换行的句子。\n\n第二段没有句号"])
        self.assertEqual(m["paragraph_chars"]["count"], 2)
        self.assertEqual(m["sentence_chars"]["count"], 2)

    def test_markup_code_removed(self):
        fence = chr(96)*3
        text = "# 题目\n\n正文。\n\n"+fence+"python\nprint('不算语料')\n"+fence
        clean = v.clean_markup(text)
        self.assertNotIn("print", clean)
        self.assertIn("正文", clean)

    def test_sources_excluded_and_exact_dedup(self):
        self.corpus([
            {"text":"这是本人原文。"},
            {"text":"这是本人原文。"},
            {"text":"独立留出资料。","split":"holdout"},
            {"text":"AI生成。","authorship":"ai"},
            {"text":"两个人混在一起。","authorship":"mixed"},
            {"text":"本人改过AI。","authorship":"edited_ai"}])
        m = v.make_metrics(self.root/"manifest.json")
        self.assertEqual(m["included_ids"], ["S0"])
        self.assertEqual(len(m["excluded"]), 5)
        self.assertEqual(m["overall"]["content_chars"], 6)

    def test_same_source_leakage_rejected(self):
        self.corpus([{"text":"前半部分。","source_id":"same"},
                     {"text":"后半部分。","source_id":"same","split":"holdout"}])
        with self.assertRaises(ValueError):
            v.make_metrics(self.root/"manifest.json")

    def test_same_text_leakage_rejected(self):
        self.corpus([{"text":"相同的内容。"},{"text":"相同的内容。","split":"holdout"}])
        with self.assertRaises(ValueError):
            v.make_metrics(self.root/"manifest.json")

    def test_asr_quality_is_explicit(self):
        self.corpus([{"text":"自然说话。","source_kind":"speech_transcript"}])
        with self.assertRaises(ValueError):
            v.make_metrics(self.root/"manifest.json")
        self.corpus([{"text":"自然说话。","source_kind":"speech_transcript","asr_verified":False}])
        self.assertTrue(any("ASR" in w for w in v.make_metrics(self.root/"manifest.json")["warnings"]))

    def test_evidence_exact_match(self):
        self.corpus([{"text":"先看一个例子。"}])
        p = self.rule_profile()
        self.assertEqual(v.validate_profile(p, self.root/"manifest.json", []), [])
        p["dimensions"]["D05"]["rules"][0]["evidence"][0]["quote"] = "我从来都这么说"
        self.assertTrue(v.validate_profile(p, self.root/"manifest.json", []))

    def test_holdout_not_evidence(self):
        self.corpus([{"text":"先看一个例子。","split":"holdout"}])
        self.assertTrue(v.validate_profile(self.rule_profile(), self.root/"manifest.json", []))

    def test_single_context_not_universal(self):
        self.corpus([{"text":"先看一个例子。"}])
        self.assertTrue(v.validate_profile(self.rule_profile(scope=["all"]), self.root/"manifest.json", []))

    def test_support_requires_independent_sources(self):
        self.corpus([{"text":"先看一个例子。"}])
        self.assertTrue(v.validate_profile(self.rule_profile(confidence="supported"), self.root/"manifest.json", []))

    def test_task_feedback_does_not_become_permanent(self):
        before = (self.root/"profile.json").read_bytes()
        result = self.feedback()
        self.assertFalse(result["persisted_rule"])
        self.assertEqual(before, (self.root/"profile.json").read_bytes())
        self.assertEqual(len(v.events_at(self.root)), 1)

    def test_feedback_replacement_authorship(self):
        self.feedback(after="由AI提出的替代句", after_origin="ai")
        self.feedback(after="来源没有明确的替代句")
        events = v.events_at(self.root)
        self.assertEqual(events[0]["after_origin"], "ai")
        self.assertEqual(events[1]["after_origin"], "unknown")

    def test_persistent_feedback_backup_and_context(self):
        self.feedback(scope="wechat", request="以后公众号先讲例子",
                      rule="先用具体例子引入", persist_rule=True)
        p = v.read_json(self.root/"profile.json")
        self.assertEqual(p["status"], "provisional")
        self.assertEqual(p["revision"], 1)
        self.assertEqual(len(list((self.root/"history").glob("*.json"))), 1)
        self.assertFalse(v.validate_profile(p, self.root/"manifest.json", v.events_at(self.root)))
        draft = self.root/"draft.txt"
        draft.write_text("两个变量存在相关。", encoding="utf-8")
        self.assertEqual(v.check_draft(self.root, draft, "academic")["applicable_rules"], [])
        self.assertEqual(len(v.check_draft(self.root, draft, "wechat")["applicable_rules"]), 1)

    def test_supersession_keeps_history_and_rejects_scope_change(self):
        self.feedback(scope="wechat", request="以后公众号这样写", rule="具体例子引入", persist_rule=True)
        old = v.all_rules(v.read_json(self.root/"profile.json"))[0]["id"]
        with self.assertRaises(ValueError):
            self.feedback(scope="academic", rule="改了", persist_rule=True, supersedes=old)
        self.feedback(scope="wechat", request="公众号改为先提问", rule="用真实问题引入",
                      persist_rule=True, supersedes=old)
        rules = v.all_rules(v.read_json(self.root/"profile.json"))
        self.assertEqual([r["state"] for r in rules], ["superseded", "active"])

    def test_register_feedback_inheritance_is_explicit(self):
        p = v.read_json(self.root/"profile.json")
        p["context_registers"].update(wechat_ai="wechat", wechat_physics="wechat")
        v.save_json(self.root/"profile.json", p)
        self.feedback(scope="register:wechat", request="以后所有公众号都不要硬列三点",
                      rule="公众号避免机械列项", persist_rule=True)
        draft = self.root/"draft.txt"
        draft.write_text("先说这次遇到的问题。", encoding="utf-8")
        self.assertEqual(len(v.check_draft(self.root, draft, "wechat_ai")["applicable_rules"]), 1)
        self.assertEqual(len(v.check_draft(self.root, draft, "wechat_physics")["applicable_rules"]), 1)
        self.assertEqual(v.check_draft(self.root, draft, "academic")["applicable_rules"], [])
        self.assertEqual(v.check_draft(self.root, draft, "wechat_unregistered")["applicable_rules"], [])

    def test_specific_scope_never_inherits_by_prefix(self):
        p = v.template("synthetic")
        p["context_registers"].update(wechat_ai="wechat", wechat_physics="wechat")
        self.assertFalse(v.scope_matches(p, ["wechat"], "wechat_ai"))
        self.assertFalse(v.scope_matches(p, ["wechat_ai"], "wechat_physics"))

    def test_no_cross_context_baseline_fallback(self):
        self.corpus([{"text":"先看例子，再来解释。"}])
        draft = self.root/"draft.txt"
        draft.write_text("变量相关，不代表因果关系。", encoding="utf-8")
        report = v.check_draft(self.root, draft, "academic")
        self.assertFalse(report["baseline_available"])
        self.assertEqual(report["descriptive_drift_only"], {})

    def test_calibration_requires_real_review_and_current_corpus(self):
        self.corpus([{"text":"先看一个例子。"}])
        p = self.rule_profile()
        p["status"], p["calibrated_contexts"] = "calibrated", ["wechat"]
        p["corpus_fingerprint"] = v.make_metrics(self.root/"manifest.json")["corpus_fingerprint"]
        self.assertTrue(v.validate_profile(p, self.root/"manifest.json", []))
        p["validation"] = [dict(date="2026-10-19", context="wechat", test_type="new_topic", evaluated_revision=p["revision"],
            context_isolation="independent", user_feedback="合成测试里的模拟评价",
            user_accepted=True, content_ok=True, unresolved=[])]
        self.assertFalse(v.validate_profile(p, self.root/"manifest.json", []))
        self.corpus([{"text":"先看一个例子。新添一段。"}])
        self.assertTrue(v.validate_profile(p, self.root/"manifest.json", []))

    def test_calibrated_empty_profile_rejected(self):
        p = v.read_json(self.root/"profile.json")
        p.update(status="calibrated", calibrated_contexts=["wechat"])
        p["corpus_fingerprint"] = v.make_metrics(self.root/"manifest.json")["corpus_fingerprint"]
        p["validation"] = [dict(date="2026-10-19", context="wechat", test_type="new_topic",
            evaluated_revision=0, context_isolation="independent", user_feedback="合成评价",
            user_accepted=True, content_ok=True, unresolved=[])]
        self.assertTrue(v.validate_profile(p, self.root/"manifest.json", []))

    def test_init_refuses_overwrite(self):
        with self.assertRaises(ValueError):
            v.init_profile(self.root, "another")

    def test_cli_roundtrip(self):
        self.corpus([{"text":"先看例子。再说原因。"}])
        out = self.root/"metrics.json"
        proc = subprocess.run([sys.executable, str(SCRIPT), "metrics", "--manifest",
            str(self.root/"manifest.json"), "--output", str(out)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(v.read_json(out)["included_ids"], ["S0"])
        proc = subprocess.run([sys.executable, str(SCRIPT), "validate", "--root", str(self.root)],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()

