# 数据约定与命令

## 文件与状态

本机 settings.local.json 只保存 profile_root（绝对路径）。档案目录包含 manifest.json、profile.json；蒸馏后增加 metrics.json、voice.md、examples.md；纠错时增加 feedback.jsonl 和 history。原始资料仍按任务的 inputs/work 约定保存。

init 从代码模板生成空档案，已有内容拒绝覆盖。修改 profile/manifest 前先保存到 history，增加 revision 和 updated_at；原始语料不覆盖。新增语料使相应风格结论待验证，重新统计并记录新的 corpus_fingerprint。脚本对已校准档案的语料变化会报错，不静默沿用。

## manifest

schema_version=1.0，author_id 与 profile 一致，segments 数组每项：
- id：片段唯一 ID；
- source_id：完整来源 ID，同一录音/文章的片段用同一 ID；
- path：相对 manifest 目录或用户指定的绝对 UTF-8 txt/md 路径；
- context：具体场景（wechat、academic、spoken 等），不能填 all/task；
- source_kind：speech_transcript、chat、article、paper 或其他可解释类型；
- authorship：user、ai、edited_ai、third_party、mixed；
- split：train、holdout、exclude；
- asr_verified：speech_transcript 必须明确 true/false；
- 可附 date、audience、original_source、time_range、cleanup_notes。

空模板见 ../assets/manifest-template.json。只有 user+train 进入统计，完全重复的训练片段去重，训练/留出同来源或完全重复则报错。近似重复和作者判断仍由 agent 核对。引用他人的文字应在制作训练片段时分开，脚本不会自动判断引语归属。

## profile

schema_version=1.0，author_id、revision、updated_at、status、corpus_fingerprint、calibrated_contexts、context_registers、dimensions、validation。空模板见 ../assets/profile-template.json。

dimensions 保留 D01-D09；每项 name、status（unobserved/observed）、rules。规则：
```json
{
  "id": "R01",
  "directive": "具体可执行的表达规则，须来自真实材料",
  "scope": ["wechat"],
  "confidence": "tentative",
  "origin": "corpus",
  "state": "active",
  "evidence": [{"segment_id": "S01", "quote": "必须替换成真实原句"}],
  "feedback_ids": []
}
```
以上只是结构示例，不是用户规则。scope 为具体场景、本人明确持续反馈的 register:文体，或单独 all；task 不能长期写入。context_registers 显式映射场景到文体，如 {"wechat_ai":"wechat","wechat_physics":"wechat"}；不能凭前缀推断。register:wechat 适用于已映射的所有公众号场景，语料规则不得这样扩散。confidence 为 tentative/supported/user_confirmed；origin 为 corpus/feedback；state 为 active/superseded。corpus 引文需逐字出现在去重后的训练片段中；supported 需至少两个来源；all 需两个场景证据或明确跨场景反馈。feedback 规则须匹配实际持久反馈的维度、范围和内容。

validation 每项至少 date、context、evaluated_revision（与当前 profile revision 一致）、test_type（held_out/new_topic）、context_isolation（independent/not_independent）、user_feedback（本人实际意见）、user_accepted、content_ok、unresolved 数组。所有未验证场景不列入 calibrated_contexts。仅结构通过不能由 agent 编造 user_accepted=true。

## 调用与返回

- status --root：只读，未创建返回 missing。
- init --root --author-id：创建空档案，不覆写。
- metrics --manifest --output：写出逐场景统计和 fingerprint，不写 profile。中文字符片段非语言学分词；数字、小数和中英混合有明确计量口径。
- validate --root：0=通过结构/证据检查，1=检查失败，2=输入错误；不能验证本人认可是否真实，agent 必须依据实际对话。
- feedback --root --dimension --scope --request [--before --after --after-origin user/ai/unknown --rule --persist-rule --supersedes]：默认 task，只追加事件；after_origin 默认 unknown，标清替代句作者；持久规则先备份 profile，再追加事件和规则，更新版本。
- check --root --draft --context --output：同场景基线对比、适用规则、需人工核对项。无全局相似度/自动通过阈值，不把口头禅当命中目标。

先运行 metrics 保存结果，再把 fingerprint 记录到 profile；这不是自动校准。输出路径须在当前任务的 work/outputs 规则范围内，若要覆盖重要既有文件先留版本。

