# 方法来源与适配

版本 1.0.0，2026-10-19。

- [kkarpushin/tone-of-voice](https://github.com/kkarpushin/tone-of-voice)：主要参考多维分析、原句依据、稳定声音与场景语气区分。采用 MIT，许可保留在 ../THIRD_PARTY_NOTICES.txt。
- [liangjfblue/writer-dna](https://github.com/liangjfblue/writer-dna)：参考其公开说明的中文多源语料、可追溯知识库、场景拆分和用户纠错思路。核验时未见明确 LICENSE；没有复制其源码、提示词或模板，本包重新编写。
- [Hiro-Inagawa/write-like-me](https://github.com/Hiro-Inagawa/write-like-me)：参考留出测试与可执行检查原则，不复用其英文分词或统一禁词表。
- [TinyStyler / EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.781/)：参考区分话题与风格的验证原则，不复用模型或训练资料。

九维组织和 Python 工具为本任务编写。中文适配包括中文标点、字符口径、ASR 证据限制、来源分组防泄漏、文体适配和纠错版本。无声线克隆、无微调、无心理诊断。统计、原句可溯源和本人认可分别验证。

