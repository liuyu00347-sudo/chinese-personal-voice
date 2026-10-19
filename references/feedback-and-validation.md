# 反馈与版本

先解决本稿“哪里不像”。比较改变的是事实、词句、节奏还是文体：
- 一次性内容修正默认 scope=task，只记录，不变永久偏好。
- “以后都…”“论文里…”等范围明确的持续偏好可持久化；已有持续校准授权下无需每条重复确认。
- 只有“不对”时给具体替代或问一项关键差异，不猜永久禁词。
- 新旧规则冲突，本稿按最新明确要求；长期替换须同范围，保留 supersedes 和旧版本。语义冲突/重复由 agent 回读判断。
- 用户没有说过的替代句不能伪装成本人修改。
- 用 --after-origin user/ai/unknown 标记替代句来源，默认 unknown；只有用户亲自提供的修改句才标 user。用户仅认可 AI 提案时仍标 ai，并在 request 记录认可原话；认可可以成为偏好依据，但不会把 AI 文本变成本人原创。

工具命令（演示，不代表真实反馈，不要执行写入个人档案）：
```bash
python3 "SKILL/scripts/voice_tool.py" feedback --root "PROFILE" --dimension D06 --scope academic --request "以后论文里别把相关写成因果" --before "X导致Y" --after "X与Y相关" --rule "按证据保留因果限定" --persist-rule
```
一次性反馈不加 --persist-rule。替换规则用 --supersedes 规则ID。脚本保存历史备份与反馈关联；重要规则变更使 calibrated 降回 provisional，重新验证后恢复。

## 范围继承

“所有公众号/以后公众号都…”用 scope=register:wechat；“这个科技号…”用具体场景如 wechat_ai；所有文体才用 all。profile.context_registers 显式把 wechat_ai、wechat_physics 等映射到 wechat，新增账号先登记映射。普通 wechat 范围仍为精确场景，不凭名称前缀继承。只有本人明确持续反馈可以使用 register 范围，某账号的语料归纳规则不得自动扩散。

## 真人验证

完整来源留出，另给新话题及事实简报。生成者只读训练规则和简报，评审者再读留出资料。无法分离上下文时说明可能泄漏，不称严格盲测。

可给用户 A/B 短片段隐藏通用/个人标签。原话和仿写混排只作辅助，尽量控制主题、长度、熟悉度；不要因用户认得原文而误判风格能力。

分别记录：
1. 事实保真：是否遗漏、编造、改变判断力度；
2. 自然与文体：中文是否顺畅且适用；
3. 本人认可：哪些句子会说/不会说，具体原因。

不把一次猜中一半视作通过，不给无标定的“95%像本人”或“AI率”。validation 记录日期、场景、evaluated_revision（当前规则版本）、test_type、context_isolation、用户实际反馈、content_ok、user_accepted、unresolved。只有本人对新题/留出测试明确认可、内容通过且无未解决项，才能将该场景列为 calibrated。自动检查不能代替本人认可。

新增语料或重要规则后重测受影响部分；未变化的检查复用。所有 AI 测试文本明确标识，禁止回流为本人原创。

