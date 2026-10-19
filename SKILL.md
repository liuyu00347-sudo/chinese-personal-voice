---
name: chinese-personal-voice
description: 从用户本人提供的中文讲话转写、聊天与原创文章，蒸馏有原句依据的九维个人风格档案，并持续吸收纠错。为用户本人署名的中文文章、公众号、论文、报告及口播稿写作或改写时默认应用，也处理“按我的口吻”“这句不像我”和更新语料。按文体保留个人表达，论文不强行口语化。没有语料或档案时明确未校准；普通问答、纯翻译、他人代笔或只改格式不强制启动。
metadata:
  short-description: 中文九维风格蒸馏、分文体写作与持续纠错
---

# 中文个人风格蒸馏

把本人真实表达提炼成可解释、可验证、可更新的写作规则。当前事实与任务要求决定说什么，个人档案决定怎么说。没有本人语料时，工具就绪不等于已经学会本人风格。

## 默认作用与优先级

- 为本机用户本人署名的中文长文默认使用，包含公众号、论文和报告；本次指定其他作者、风格或局部修改时遵从本次范围。
- 优先级：当前明确要求与事实准确性 → 文体/期刊必要规范 → 同场景明确反馈 → 有原句支持的个人规则 → 通用自然表达建议。
- 与其他写作 Skill 配合时，本 Skill 提供个人语言规则；其他 Skill 负责事实调研、专业格式、配图、账号身份和固定结尾。个人实证规则优先于泛化去 AI 味禁词，不重复启动第二套风格蒸馏。
- 不把某个公众号口吻扩展到论文或另一账号，不把旧风格示例里的经历、数据和立场带入新文章。

## 定位档案

1. 用户本次指定的作者/档案优先。
2. 否则读本 Skill 的 `settings.local.json` 中 `profile_root`。它只有本机定位信息，不随分享包分发。
3. 可迁移包没有本机设置时，复用任务已有档案；确无档案且用户要求建立时，在其归档目录下初始化，并记录绝对路径。不扫描硬盘、聊天或邮箱寻找私人语料。
4. 读 `profile.json` 状态、版本与场景，再按任务读 `voice.md`、代表原句及相关反馈。缺少档案不等于用户没有写作样本。

## 按任务选模式

**蒸馏/新语料**：读 [语料与蒸馏](references/corpus-and-distillation.md)、[九维分析](references/dimensions.md)。完成作者核对、分场景统计、原句证据规则、留出/新题验证。已有资料复用，不为数量门槛拖延试分析。

**起草/改写**：读 [写作与文体](references/writing-and-registers.md)。加载匹配场景的规则、代表原话及近期明确反馈，先锁事实再写作。未校准仍可完成普通写作，但不声称已还原本人风格。通常只交成稿，不附内部画像与检查表。

**纠错**：读 [反馈与验证](references/feedback-and-validation.md)。先改本稿；清楚且适用于后续的反馈按场景持久化。一次性的内容修改不升级成永久偏好。

## 九维与证据

D01 用词与搭配；D02 句式与语序；D03 节奏与信息密度；D04 思路展开；D05 解释与论证；D06 语气与判断力度；D07 听众关系；D08 情绪与修辞；D09 场景变化与表达边界。

允许待观察，不为填满维度虚构规律或揣测人格。每条规则记录可执行写法、场景、原句与来源、置信等级；本人明确反馈关联反馈事件。高频只是候选，未出现不等于禁用，研究话题不等于个人风格。

## 本地工具

Python 3 标准库，无联网/模型训练/音频识别依赖。脚本本身不上传资料；AI 阅读资料仍经过当前会话使用的模型服务，不能宣称整个流程完全离线。

把 SKILL、PROFILE 换成实际目录：
```bash
python3 "SKILL/scripts/voice_tool.py" status --root "PROFILE"
python3 "SKILL/scripts/voice_tool.py" init --root "PROFILE" --author-id default
python3 "SKILL/scripts/voice_tool.py" metrics --manifest "PROFILE/manifest.json" --output "PROFILE/metrics.json"
python3 "SKILL/scripts/voice_tool.py" validate --root "PROFILE"
python3 "SKILL/scripts/voice_tool.py" check --root "PROFILE" --draft "稿件.md" --context wechat --output "检查.json"
```

init 拒绝覆盖已有档案。metrics 只统计本人原创训练片段；中文按明确的字符口径，不冒充分词。validate 核对来源、原句和反馈关联；check 仅给漂移线索，不能证明像本人。见 [数据约定](references/data-contract.md)。

## 完成条件

- 工具：结构有效，脚本实际运行，中文、来源隔离、纠错行为有验证。
- 蒸馏：真实样本可定位；稳定风格与场景语气分开；内容保真、自然度、本人认可分别记录。
- 区分 untrained、provisional、calibrated。只有本人评审过新题/留出测试、内容通过且无关键未解决问题，该场景才可标已校准；其他场景仍待验证。
- 不从几道盲测推导相似度百分比，不把自动检查通过等同于本人认可。
- 版本 1.0.0，见 [来源与许可](references/provenance.md)。

