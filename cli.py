"""Term Extractor CLI — config-driven terminology extraction from bilingual Excel files."""

import io
import os
import re
import sys
import json
import yaml
import asyncio
import argparse
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

from extractor import (
    build_big_table,
    load_progress,
    save_progress,
    load_target,
    classify_terms,
    apply_special_rules,
    run_ai_batch,
    write_results,
)


def resolve_env(value: str) -> str:
    """Resolve ${VAR} or $VAR in string values."""
    if not isinstance(value, str):
        return value
    # Match ${VAR} pattern
    def repl(m):
        return os.environ.get(m.group(1), "")
    return re.sub(r"\$\{(\w+)\}", repl, value)


def resolve_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve environment variables in config values."""
    if isinstance(config, dict):
        return {k: resolve_config(v) for k, v in config.items()}
    if isinstance(config, list):
        return [resolve_config(v) for v in config]
    if isinstance(config, str):
        return resolve_env(config)
    return config


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config and resolve env vars."""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return resolve_config(config)


def resolve_paths(config: Dict[str, Any], config_dir: str):
    """Make relative paths absolute, relative to config file directory."""
    for src in config.get("big_table", {}).get("sources", []):
        if "path" in src and not os.path.isabs(src["path"]):
            src["path"] = os.path.join(config_dir, src["path"])

    target = config.get("target", {})
    if "path" in target and not os.path.isabs(target["path"]):
        target["path"] = os.path.join(config_dir, target["path"])

    output = config.get("output", {})
    if "path" in output and not os.path.isabs(output["path"]):
        output["path"] = os.path.join(config_dir, output["path"])

    ai = config.get("ai", {})
    if "progress_file" not in ai:
        ai["progress_file"] = os.path.join(
            config_dir, os.path.splitext(os.path.basename(config.get("_config_path", "config")))[0] + "_progress.json"
        )
    if "log_file" not in ai:
        ai["log_file"] = os.path.join(
            config_dir, os.path.splitext(os.path.basename(config.get("_config_path", "config")))[0] + "_ai_log.jsonl"
        )
    for key in ("progress_file", "log_file"):
        if ai.get(key) and not os.path.isabs(ai[key]):
            ai[key] = os.path.join(config_dir, ai[key])


def dry_run(target, big_df, progress, ai_config, matching_config, special_rules):
    """Analyze and print classification without making AI calls."""
    print(f"\n{'='*50}")
    print("DRY RUN — 不会调用 AI API")
    print(f"{'='*50}")

    max_contexts = matching_config.get("max_contexts", 15)
    exact, ai_needed, skip = classify_terms(target, big_df, max_contexts)

    # Identify special rule indices
    special_indices = set()
    for rule in (special_rules or []):
        from extractor import parse_special_when
        condition = parse_special_when(rule["when"])
        for idx, row in target.iterrows():
            zh = str(row.get("ZH", ""))
            if condition(idx, row):
                special_indices.add(f"{idx}_{zh}")

    # Filter AI-needed: remove special rule items
    pending_ai = [item for item in ai_needed if item[1] not in special_indices and item[1] not in progress]
    pending_skip = [(i, ck) for i, ck in skip if ck not in progress]
    pending_special = [ck for ck in special_indices if ck not in progress]

    print(f"  精确匹配（直接填入）: {len(exact)} 条")
    print(f"  包含匹配（需 AI）:   {len(pending_ai)} 条")
    print(f"  特殊规则处理:        {len(pending_special)} 条")
    print(f"  零匹配（留空）:      {len(pending_skip)} 条")
    print(f"  已缓存进度:          {len(progress)} 条")
    print()


def main():
    parser = argparse.ArgumentParser(description="术语提取工具")
    parser.add_argument("config", help="YAML 配置文件路径")
    parser.add_argument("--target", help="覆盖目标文件路径")
    parser.add_argument("--output", help="覆盖输出文件路径")
    parser.add_argument("--api-key", help="覆盖 API key")
    parser.add_argument("--model", help="覆盖模型")
    parser.add_argument("--dry-run", action="store_true", help="干跑，不调 AI")
    parser.add_argument("--from-scratch", action="store_true", help="删除进度文件重跑")
    args = parser.parse_args()

    config_dir = os.path.dirname(os.path.abspath(args.config))
    config = load_config(args.config)
    config["_config_path"] = args.config
    resolve_paths(config, config_dir)

    # CLI overrides
    if args.target:
        config["target"]["path"] = args.target
    if args.output:
        config["output"]["path"] = args.output
    if args.api_key:
        config["ai"]["api_key"] = args.api_key
    if args.model:
        config["ai"]["model"] = args.model

    ai_config = config.get("ai", {})
    matching_config = config.get("matching", {})
    special_rules = config.get("special_rules", [])
    target_config = config.get("target", {})
    output_config = config.get("output", {})
    big_table_config = config.get("big_table", {})

    if args.from_scratch:
        progress_file = ai_config.get("progress_file")
        if progress_file and os.path.exists(progress_file):
            os.remove(progress_file)
            print("已删除进度文件")

    print(f"[{datetime.now():%H:%M:%S}] 构建大表...")
    big_df = build_big_table(big_table_config.get("sources", []))
    print(f"  大表行数: {len(big_df)}")

    print(f"[{datetime.now():%H:%M:%S}] 读取目标文件...")
    target = load_target(target_config)
    print(f"  目标行数: {len(target)}")

    progress_file = ai_config.get("progress_file")
    progress = load_progress(progress_file) if progress_file else {}

    # Remove failed entries (best is empty)
    removed = 0
    for k in list(progress.keys()):
        val = progress[k]
        if isinstance(val, dict) and not val.get("best"):
            del progress[k]
            removed += 1
        elif isinstance(val, str) and not val.strip():
            del progress[k]
            removed += 1
    if removed:
        print(f"  清除失败记录: {removed} 条")
        save_progress(progress, progress_file)

    print(f"  已有进度: {len(progress)} 条")

    if args.dry_run:
        dry_run(target, big_df, progress, ai_config, matching_config, special_rules)
        return

    # First pass: classify
    max_contexts = matching_config.get("max_contexts", 15)
    max_alts = ai_config.get("max_alt", 3)
    exact, ai_needed, skip = classify_terms(target, big_df, max_contexts)

    # Build set of indices that match special rules (skip from AI batch)
    special_indices = set()
    for rule in (special_rules or []):
        from extractor import parse_special_when
        condition = parse_special_when(rule["when"])
        for idx, row in target.iterrows():
            zh = str(row.get("ZH", ""))
            if condition(idx, row):
                special_indices.add(f"{idx}_{zh}")

    # Fill exact matches directly
    for idx, cache_key, best_en in exact:
        if cache_key not in progress:
            progress[cache_key] = {"best": best_en, "alts": []}
    # Fill zero-match as empty
    for idx, cache_key in skip:
        if cache_key not in progress:
            progress[cache_key] = {"best": "", "alts": []}

    save_progress(progress, progress_file)

    direct_count = sum(1 for v in progress.values() if isinstance(v, dict) and v.get("best"))
    print(f"[{datetime.now():%H:%M:%S}] 直接填入（精确匹配+缓存）: {direct_count} 条")

    # Run AI batch — skip special rule items and already completed
    pending_ai = [
        item for item in ai_needed
        if item[1] not in progress and item[1] not in special_indices
    ]

    if pending_ai:
        semaphore = asyncio.Semaphore(ai_config.get("concurrency", 3))
        asyncio.run(run_ai_batch(pending_ai, ai_config, progress, semaphore))
        save_progress(progress, progress_file)

    # Apply special rules
    print(f"[{datetime.now():%H:%M:%S}] 处理特殊规则...")
    applied = apply_special_rules(target, progress, big_df, special_rules, max_contexts)
    if applied:
        print(f"  特殊规则处理: {applied} 条")
    save_progress(progress, progress_file)

    # Write results
    print(f"[{datetime.now():%H:%M:%S}] 写入结果...")
    filled, filtered = write_results(target, progress, big_df, output_config, max_contexts, max_alts)
    print(f"  已填充: {filled}/{len(target)} 条")
    if filtered:
        print(f"  过滤掉无效备选: {filtered} 条")
    print(f"  输出文件: {output_config['path']}")
    print(f"[{datetime.now():%H:%M:%S}] 完成")


if __name__ == "__main__":
    main()
