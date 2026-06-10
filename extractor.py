import os
import re
import json
import asyncio
import pandas as pd
from datetime import datetime
from openai import AsyncOpenAI


def build_big_table(sources):
    """Build a merged big table from multiple Excel sources.

    Each source dict:
      {path, key_col|None, zh_col, en_col, header=True|False}
    zh_col/en_col can be str (column name) or int (column index when header=False).
    """
    frames = []
    for src in sources:
        path = src["path"]
        has_header = src.get("header", True)
        zh_col = src["zh_col"]
        en_col = src["en_col"]
        key_col = src.get("key_col")

        if has_header:
            df = pd.read_excel(path)
            remap = {}
            if key_col and key_col in df.columns:
                remap[key_col] = "Key"
            remap[zh_col] = "Chinese"
            remap[en_col] = "English"
            df = df.rename(columns=remap)
        else:
            df = pd.read_excel(path, header=None)
            cols = {zh_col: "Chinese", en_col: "English"}
            if key_col is not None:
                cols[key_col] = "Key"
            else:
                cols[len(df.columns)] = "Key"
            df = df.rename(columns=cols)
            # Ensure Key col exists
            if "Key" not in df.columns:
                df["Key"] = ""

        for col in ["Key", "Chinese", "English"]:
            if col not in df.columns:
                df[col] = ""
        frames.append(df[["Key", "Chinese", "English"]])

    big = pd.concat(frames, ignore_index=True)
    big["Chinese"] = big["Chinese"].astype(str)
    return big


def load_progress(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def make_prompt(term, contexts, note, source_text, max_alts):
    ctx_lines = []
    for i, (zh, en) in enumerate(contexts, 1):
        ctx_lines.append(f"{i}. 原文：{zh}\n   译文：{en}")
    ctx_block = "\n".join(ctx_lines)

    extra = ""
    if pd.notna(note) and str(note).strip():
        extra += f"\n- Note：{note}"
    if pd.notna(source_text) and str(source_text).strip():
        extra += f"\n- 目标文件原文：{source_text}"

    return (
        f"你是一名游戏本地化术语提取专家。\n\n"
        f"中文术语：{term}\n\n"
        f"以下是从游戏工程翻译表中提取的包含该术语的原文和译文对（共{len(contexts)}条）：\n"
        f"{ctx_block}\n"
        f"{extra}\n\n"
        f"请根据以上上下文，提取\"{term}\"最合适的英文术语，并列出其他备选译法。\n"
        f"请严格按以下JSON格式返回，不要包含任何其他内容（如markdown代码块标记、解释文字等）：\n\n"
        f'{{"best": "最佳译法", "alternatives": ["备选1", "备选2", "备选3"]}}\n\n'
        f"要求：\n"
        f"1. best选择最通用、最适合作为游戏\"术语\"的那个译法\n"
        f"2. alternatives必须是以上上下文中实际出现的、不同于best的其他英文译法，严禁编造上下文中不存在的译法\n"
        f"3. alternatives最多{max_alts}个，按优先级排序；如果上下文中只有一种译法，alternatives必须为空数组\n"
        f"4. 如果确实无法确定，best填\"UNKNOWN\"，alternatives为空数组\n"
        f"5. 提取的英文术语必须保持原中文术语的标点符号格式统一。例如：中文术语末尾有中文全角冒号\"：\"的，英文术语末尾也应加英文冒号\":\"；中文术语带括号的，英文术语也应带对应括号\n"
        f"6. 必须输出完整的JSON，不要截断"
    )


def parse_ai_result(text, term, max_alts):
    text = text.strip() if text else ""
    if not text:
        print(f"  [Parse Error] {term}: empty response")
        return {"best": "", "alts": []}

    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    fixed = text
    if not fixed.endswith("}"):
        last_brace = fixed.rfind("}")
        last_bracket = fixed.rfind("]")
        if last_bracket > last_brace:
            fixed += "}"
        elif fixed.rfind('"') > fixed.rfind("{"):
            fixed += ']}"' if "alternatives" in fixed else '"}'

    for attempt_text in [text, fixed]:
        try:
            data = json.loads(attempt_text)
            best = str(data.get("best", "")).strip()
            alts = data.get("alternatives", [])
            if not isinstance(alts, list):
                alts = []
            alts = [str(a).strip() for a in alts if str(a).strip()]
            if best.upper() == "UNKNOWN":
                best = ""
            return {"best": best, "alts": alts[:max_alts]}
        except Exception:
            continue

    print(f"  [Parse Error] {term}: '{text[:100]}...'")
    return {"best": "", "alts": []}


def get_contexts_for_term(term, big_df, max_contexts):
    mask = big_df["Chinese"].str.contains(term, regex=False, na=False)
    matches = big_df[mask]
    valid = matches[matches["English"].notna()]
    return [(m["Chinese"], m["English"]) for _, m in valid.head(max_contexts).iterrows()]


def filter_alts(alts, contexts):
    if not alts or not contexts:
        return []
    valid = []
    for alt in alts:
        if not isinstance(alt, str):
            continue
        alt_lower = alt.lower()
        for zh, en in contexts:
            if pd.notna(en) and alt_lower in str(en).lower():
                valid.append(alt)
                break
    return valid


def load_target(target_config):
    """Load target file with flexible column mapping.

    target_config:
      path, header=True, zh_col, en_col, note_col, source_col, file_col
    zh_col/en_col can be str (name) or int (index when header=False).
    """
    path = target_config["path"]
    has_header = target_config.get("header", True)
    zh_col = target_config["zh_col"]
    en_col = target_config["en_col"]
    note_col = target_config.get("note_col")
    source_col = target_config.get("source_col")
    file_col = target_config.get("file_col")

    if has_header:
        df = pd.read_excel(path)
        remap = {zh_col: "ZH", en_col: "EN"}
        if note_col:
            remap[note_col] = "Note"
        if source_col:
            remap[source_col] = "Source"
        if file_col:
            remap[file_col] = "File"
        df = df.rename(columns=remap)
    else:
        df = pd.read_excel(path, header=None)
        remap = {zh_col: "ZH", en_col: "EN"}
        if note_col is not None:
            remap[note_col] = "Note"
        if source_col is not None:
            remap[source_col] = "Source"
        if file_col is not None:
            remap[file_col] = "File"
        df = df.rename(columns=remap)

    for col in ["ZH", "EN", "Note", "Source", "File"]:
        if col not in df.columns:
            df[col] = ""
    return df


def classify_terms(target, big_df, max_contexts):
    """Classify every row in target.

    Returns:
      exact: list of (idx, cache_key, best_en)  -> direct fill
      ai_needed: list of (idx, cache_key, zh, contexts, note, source_text)  -> need AI
      skip: list of (idx, cache_key)  -> zero match, leave empty
    """
    exact = []
    ai_needed = []
    skip = []
    zh_col = "ZH"
    note_col = "Note"
    source_col = "Source"

    for idx, row in target.iterrows():
        zh = str(row[zh_col]) if pd.notna(row.get(zh_col)) else ""
        if not zh:
            continue

        cache_key = f"{idx}_{zh}"

        exact_mask = big_df["Chinese"] == zh
        exact_count = exact_mask.sum()
        if exact_count == 1:
            en = big_df[exact_mask]["English"].iloc[0]
            if pd.notna(en) and str(en).strip():
                exact.append((idx, cache_key, str(en).strip()))
                continue

        contexts = get_contexts_for_term(zh, big_df, max_contexts)
        if not contexts:
            skip.append((idx, cache_key))
            continue

        note = str(row.get(note_col)) if pd.notna(row.get(note_col)) else ""
        source_text = (
            str(row.get(source_col))
            if source_col in row.index and pd.notna(row.get(source_col))
            else ""
        )
        ai_needed.append((idx, cache_key, zh, contexts, note, source_text))

    return exact, ai_needed, skip


def parse_special_when(when_expr):
    """Parse a 'when' expression like "note == 'xx'" or "zh matches 'regex'".

    Returns a callable: f(idx, row) -> bool
    """
    m = re.match(r"note\s*==\s*'(.+)'", when_expr)
    if m:
        val = m.group(1)
        return lambda idx, row: str(row.get("Note", "")) == val

    m = re.match(r"zh\s*matches\s*'(.+)'", when_expr)
    if m:
        pattern = m.group(1)
        return lambda idx, row: bool(re.search(pattern, str(row.get("ZH", ""))))

    m = re.match(r"file\s*==\s*'(.+)'", when_expr)
    if m:
        val = m.group(1)
        return lambda idx, row: str(row.get("File", "")) == val

    return lambda idx, row: False


def execute_special_action(action, idx, row, target, progress, big_df, max_contexts):
    """Execute a special rule action for a row.

    Returns: (cache_key, result_dict) or None if no action taken.
    """
    zh = str(row.get("ZH", ""))
    cache_key = f"{idx}_{zh}"

    if action["action"] == "skip":
        progress[cache_key] = {"best": "", "alts": []}
        return cache_key

    if action["action"] == "copy_from_suffix":
        suffix = action.get("suffix", "")
        full_name = zh + suffix
        match_rows = target[target["ZH"] == full_name]
        if len(match_rows) == 0:
            return None
        matched_idx = match_rows.index[0]
        matched_cache_key = f"{matched_idx}_{full_name}"
        if matched_cache_key in progress and progress[matched_cache_key].get("best"):
            progress[cache_key] = progress[matched_cache_key]
            return cache_key
        # Try exact match from big table
        exact_mask = big_df["Chinese"] == full_name
        if exact_mask.sum() == 1:
            en = big_df[exact_mask]["English"].iloc[0]
            if pd.notna(en) and str(en).strip():
                progress[cache_key] = {"best": str(en).strip(), "alts": []}
                return cache_key
        return None

    if action["action"] == "copy_from_prefix":
        prefix = action.get("prefix", "")
        full_name = prefix + zh
        match_rows = target[target["ZH"] == full_name]
        if len(match_rows) == 0:
            return None
        matched_idx = match_rows.index[0]
        matched_cache_key = f"{matched_idx}_{full_name}"
        if matched_cache_key in progress and progress[matched_cache_key].get("best"):
            progress[cache_key] = progress[matched_cache_key]
            return cache_key
        exact_mask = big_df["Chinese"] == full_name
        if exact_mask.sum() == 1:
            en = big_df[exact_mask]["English"].iloc[0]
            if pd.notna(en) and str(en).strip():
                progress[cache_key] = {"best": str(en).strip(), "alts": []}
                return cache_key
        return None

    return None


async def ask_ai_once(client, term, contexts, note, source_text, model, max_alts, log_file):
    prompt = make_prompt(term, contexts, note, source_text, max_alts)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        result_text = resp.choices[0].message.content
        if log_file:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {"term": term, "time": datetime.now().isoformat(), "raw": result_text},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        return parse_ai_result(result_text, term, max_alts)
    except Exception as e:
        print(f"  [AI Error] {term}: {e}")
        return {"best": "", "alts": []}


async def ask_ai(client, term, contexts, note, source_text, model, max_alts, retries, semaphore, log_file):
    for attempt in range(1, retries + 1):
        async with semaphore:
            result = await ask_ai_once(client, term, contexts, note, source_text, model, max_alts, log_file)
        if result["best"]:
            return result
        if attempt < retries:
            print(f"  [Retry {attempt}/{retries}] {term}")
            await asyncio.sleep(1)
    return result


async def run_ai_batch(ai_needed, ai_config, progress, semaphore):
    """Process all AI-needed items with concurrency control."""
    client = AsyncOpenAI(api_key=ai_config["api_key"], base_url=ai_config["base_url"])
    model = ai_config.get("model", "deepseek-v4-pro")
    max_alts = ai_config.get("max_alt", 3)
    retries = ai_config.get("retries", 3)
    log_file = ai_config.get("log_file")

    tasks = []
    task_indices = []
    for item in ai_needed:
        idx, cache_key, zh, contexts, note, source_text = item
        coro = ask_ai(
            client, zh, contexts, note, source_text,
            model, max_alts, retries, semaphore, log_file
        )
        tasks.append(coro)
        task_indices.append((idx, cache_key, zh))

    print(f"[{datetime.now():%H:%M:%S}] 需要 AI 处理: {len(tasks)} 条")

    completed = 0
    batch_size = 10
    for i in range(0, len(tasks), batch_size):
        batch_tasks = tasks[i : i + batch_size]
        batch_indices = task_indices[i : i + batch_size]
        results = await asyncio.gather(*batch_tasks)
        for (idx, cache_key, zh), result in zip(batch_indices, results):
            progress[cache_key] = result
            completed += 1
        save_progress(progress, ai_config.get("progress_file", "term_extraction_progress.json"))
        print(f"  ...已完成 {completed}/{len(tasks)}")


def apply_special_rules(target, progress, big_df, special_rules, max_contexts):
    """Apply special rules to any unprocessed rows.

    Returns number of rows processed.
    """
    applied = 0
    for rule in special_rules:
        condition = parse_special_when(rule["when"])
        for idx, row in target.iterrows():
            if not condition(idx, row):
                continue
            zh = str(row.get("ZH", ""))
            cache_key = f"{idx}_{zh}"
            if cache_key in progress and progress[cache_key].get("best"):
                continue
            result = execute_special_action(rule, idx, row, target, progress, big_df, max_contexts)
            if result:
                applied += 1
    return applied


def write_results(target, progress, big_df, output_config, max_contexts, max_alts):
    """Write results to target DataFrame and save to Excel."""
    output_path = output_config["path"]
    rename_cols = output_config.get("rename_cols", {})

    for old, new in rename_cols.items():
        if old in target.columns:
            target = target.rename(columns={old: new})

    alt_cols = [f"Alt_EN_{i+1}" for i in range(max_alts)]
    for col in alt_cols:
        if col not in target.columns:
            target[col] = ""

    # pandas >=3.0 refuses to set str into an all-NaN float64 column; force object dtype
    for col in ["EN", "ZH", "Note", "Source", "File"]:
        if col in target.columns:
            target[col] = target[col].astype(object)

    filtered_count = 0
    filled = 0
    for idx, row in target.iterrows():
        zh = str(row.get("ZH", "")) if pd.notna(row.get("ZH")) else ""
        if not zh:
            continue
        cache_key = f"{idx}_{zh}"
        if cache_key not in progress:
            continue

        data = progress[cache_key]
        if isinstance(data, str):
            data = {"best": data, "alts": []}

        best = data.get("best", "")
        alts = data.get("alts", [])

        if alts:
            contexts = get_contexts_for_term(zh, big_df, max_contexts)
            original_alts = alts[:]
            alts = filter_alts(alts, contexts)
            if len(alts) < len(original_alts):
                filtered_count += 1

        if best:
            target.at[idx, "EN"] = best
            filled += 1
        for i, col in enumerate(alt_cols):
            target.at[idx, col] = alts[i] if i < len(alts) else ""

    target.to_excel(output_path, index=False)
    return filled, filtered_count
