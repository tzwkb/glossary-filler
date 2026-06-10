# glossary-filler — 术语表补全工作台

为游戏本地化术语表批量补英文译法：从双语 Excel 工程表（大表）中找每条中文术语的译法——精确匹配直填，包含匹配交 AI 从上下文提取，零匹配留空等下一批参考。核心引擎（`extractor.py` + `cli.py`）+ 各游戏项目工作区。

## 原理

```
target 每条空 EN 术语
├─ 大表唯一精确匹配且有 EN ──→ 直接填（不计费）
├─ 出现在大表原文里（包含） ──→ AI 读 ≤15 条 原文/译文 上下文，提 best + Alt_EN_1~3
│                                （备选严格限于上下文出现过的译法，编造会被过滤；拿不准返回 UNKNOWN 留空）
└─ 零匹配 ────────────────────→ 留空
```

- 断点续传：进度存 `runtime/*_progress.json`，中断重跑不重复调 AI；`--from-scratch` 从头
- 同 ZH 多译法冲突：不直填，交 AI 裁决
- AI 原始响应留 `runtime/*_ai_log.jsonl` 可审计

## 目录

```
extractor.py           # 核心引擎：大表构建/分类/AI 批处理/写结果
cli.py                 # 入口（config 驱动）
CONFIG.md              # 配置参考：big_table 多源/特殊规则/CLI 参数
projects/<项目>/
├── *.yaml             # 提取配置（路径相对 yaml 所在目录解析）
├── prep_*.py          # 预处理：参考表+待填表 拍平 → data/
├── merge_*.py         # 回填：filled 结果写回客户工作表
├── source/            # 客户原件（工作表、文本 dump、项目配置表）
├── data/              # prep 产物：参考大表 + 待填 target
├── output/            # *_filled.xlsx 结果
└── runtime/           # 进度 + AI 日志
```

## 使用

```bash
python3 cli.py projects/<项目>/<配置>.yaml --dry-run   # 免费看分类统计
python3 cli.py projects/<项目>/<配置>.yaml             # 正式跑
```

## 新项目流程

1. `prep_<项目>.py`：
   - 参考大表清洗三件套：同 (ZH,EN) 去重 / 权威源优先（客户确认 > 工程表）/ **剔除 EN=中文占位行**
   - target 只留空 EN 行，带 `_row` 列（原 Excel 行号，回填定位用）
2. 抄一份 yaml 改路径
3. `--dry-run` 看分类数字 → 确认后正式跑 → 审 `output/*_filled.xlsx`
4. `merge_*.py` 回填：自动备份客户表、按 `_row` 定位、逐行核对 ZH、只写空 EN 单元格

## 项目状态

| 项目 | 配置 | 状态 |
|------|------|------|
| 末日下班特快 | term_extract_config.yaml / term_extract_p2.yaml | 完结（2026-05） |
| h72 | 无（仅 dedup_reference.py 预处理，原跑在 Windows） | 完结（2026-05） |
| 咻咻勇者 | xiuxiu_artchar.yaml（美术字，完结）/ xiuxiu_termsheet.yaml | 术语总表 177/3676 已填，回填待批 |

## 注意

- API key 走环境变量：`DEEPSEEK_API_KEY=sk-xxx python3 cli.py ...`（yaml 中 `${DEEPSEEK_API_KEY}` 自动解析）
- 客户数据不入库：source/data/output/runtime 及全部 xlsx 已 gitignore，仓库只含代码与文档
- 参考表里 EN 列非空 ≠ 有翻译：见过整列抄中文原文当占位的（LanguageDesc），prep 必须过滤
- 本机 pandas 3.x：`astype(str)` 不再把 NaN 变 `'nan'`，清洗一律先 `fillna("")`
