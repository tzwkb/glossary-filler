# glossary-filler — 术语表补全工作台

[中文](README_ZH.md) | English


## Overview

 Glossary English-filling workstation that finds or extracts English renderings for Chinese terms from bilingual Excel project sheets.

## Key Capabilities

- Exact matches can be filled directly.
- Contained matches are sent to AI for context-based extraction.
- No-match terms are kept for later reference batches.

## Usage

 Prepare bilingual source sheets, glossaries, and configuration in the project workspace, then run the CLI/core engine.

## Status

 This repository is maintained or used according to the current README notes.

## Notes

 Different game projects can maintain separate resources in their own workspaces.

## Command and Configuration Reference

The following code blocks are preserved from the primary README. Commands, paths, and configuration keys are not translated; adjust them for the actual environment.

```
target 每条空 EN 术语
├─ 大表唯一精确匹配且有 EN ──→ 直接填（不计费）
├─ 出现在大表原文里（包含） ──→ AI 读 ≤15 条 原文/译文 上下文，提 best + Alt_EN_1~3
│                                （备选严格限于上下文出现过的译法，编造会被过滤；拿不准返回 UNKNOWN 留空）
└─ 零匹配 ────────────────────→ 留空
```

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

```bash
python3 cli.py projects/<项目>/<配置>.yaml --dry-run   # 免费看分类统计
python3 cli.py projects/<项目>/<配置>.yaml             # 正式跑
```

## Detailed Technical Notes

The primary README keeps the original technical details, history notes, full commands, and file layout. This file maintains the English version of the core documentation; consult the primary README code blocks and paths when exact commands are needed.
