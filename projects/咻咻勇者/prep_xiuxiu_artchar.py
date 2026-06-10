"""Prep xiuxiu art-char term extraction inputs.

term_extractor reads only the first sheet per file, so flatten the two
multi-sheet workbooks into single-sheet inputs it can consume.

TARGET    : 内部工作表格 -> sheet "美术字 术语总表"  (ZH/EN/Note/原文参考/File)
REFERENCE : 定稿美术字统计 -> 4 sheets, pair 简体 -> EN
"""
import pandas as pd
from pathlib import Path

REF = "/Users/spellbook/Library/Containers/com.tencent.WeWorkMac/Data/Documents/Profiles/821FB603491DCFE76AB2D610CB6D9C89/Caches/Files/2026-06/5DF7A9D03D7E01D74F3F670A2FDB8AB6/【定稿】咻咻勇者_台服美术字统计_F列简中译英.xlsx"
TGT = str(Path(__file__).parent / "source" / "咻咻勇者--内部工作表格.xlsx")

DATA = Path(__file__).parent / "data"
OUT_REF = DATA / "xiuxiu_artchar_ref.xlsx"
OUT_TGT = DATA / "xiuxiu_artchar_target.xlsx"

REF_SHEETS = ["功能系統", "戰鬥玩法", "商業活動", "待確認"]


def build_ref():
    frames = []
    for sh in REF_SHEETS:
        d = pd.read_excel(REF, sheet_name=sh)
        if "简体" not in d.columns or "EN" not in d.columns:
            print(f"  [skip] sheet {sh}: missing 简体/EN, cols={list(d.columns)}")
            continue
        sub = d[["简体", "EN"]].copy()
        sub["简体"] = sub["简体"].astype(str).str.strip()
        sub = sub[(sub["简体"] != "") & (sub["简体"].str.lower() != "nan")]
        frames.append(sub)
    big = pd.concat(frames, ignore_index=True)
    big.to_excel(OUT_REF, index=False)
    print(f"REF  -> {OUT_REF.name}: {len(big)} rows, unique 简体={big['简体'].nunique()}, with EN={int(big['EN'].notna().sum())}")


def build_target():
    df = pd.read_excel(TGT, sheet_name="美术字 术语总表")
    cols = [c for c in ["ZH", "EN", "Note", "原文参考", "File"] if c in df.columns]
    out = df[cols].copy()
    out["ZH"] = out["ZH"].astype(str).str.strip()
    out = out[(out["ZH"] != "") & (out["ZH"].str.lower() != "nan")]
    # 仅补空白：只保留 EN 为空的行，已有人工译文不动、不计费
    empty = out["EN"].isna() | (out["EN"].astype(str).str.strip() == "")
    sub = out[empty].copy()
    sub.to_excel(OUT_TGT, index=False)
    print(f"TGT  -> {OUT_TGT.name}: {len(sub)} empty-EN terms (of {len(out)} total; {len(out)-len(sub)} kept untouched)")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    build_ref()
    build_target()
    print("done")
