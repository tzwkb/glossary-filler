# Glossary Filler

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)

English | [中文](README_ZH.md)

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

The following code blocks keep commands, paths, filenames, and configuration keys literal; explanatory comments are translated for the English README.

```
target rows with blank EN terms
├─ unique exact match in the big table with EN ──→ fill directly (no AI cost)
├─ appears in big-table source text (contains match) ──→ AI reads up to 15 source/target context rows and extracts best + Alt_EN_1~3
│                                (alternatives must come from observed context; hallucinations are filtered; return UNKNOWN if uncertain)
└─ no match ───────────────────→ leave blank
```

```
extractor.py           # core engine: big-table building, classification, AI batching, result writing
cli.py                 # entry point (config-driven)
CONFIG.md              # configuration reference: multi-source big_table, special rules, CLI parameters
projects/<project>/
├── *.yaml             # extraction config (paths resolved relative to the YAML file)
├── prep_*.py          # preprocessing: flatten reference and target sheets into data/
├── merge_*.py         # merge-back: write filled results back to the client workbook
├── source/            # client source files (workbooks, text dumps, project config sheets)
├── data/              # prep outputs: reference big table + target rows to fill
├── output/            # *_filled.xlsx results
└── runtime/           # progress + AI logs
```

```bash
python3 cli.py projects/<project>/<config>.yaml --dry-run   # preview classification stats for free
python3 cli.py projects/<project>/<config>.yaml             # run the full fill job
```

## Detailed Technical Notes

This README keeps the English version of the core documentation. Code blocks, paths, commands, and file-layout examples are kept literal so they can be copied and checked against the repository.
