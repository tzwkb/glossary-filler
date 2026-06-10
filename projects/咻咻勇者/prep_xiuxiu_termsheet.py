"""Prep xiuxiu main term-sheet extraction inputs.

TARGET    : 内部工作表格 -> sheet "术语总表", empty-EN rows only.
            `_row` column carries the original Excel row number for safe merge-back.
REFERENCE : confirmed art-char glossary (反馈+Final, 简体 -> EN-Final/EN)
            + LanguageDesc bilingual dump (ZH -> EN).
            Glossary wins: LanguageDesc rows whose ZH equals a glossary term are dropped.
            LanguageDesc rows whose EN still contains CJK are untranslated
            placeholders (EN cell = copied ZH) and are dropped.
            Identical (ZH, EN) pairs dedup to one row so unique exact matches fill
            without AI; conflicting translations stay and go to AI adjudication.
"""
import pandas as pd
from pathlib import Path

GLOSSARY = "/Users/spellbook/Library/Containers/com.tencent.WeWorkMac/Data/Documents/Profiles/821FB603491DCFE76AB2D610CB6D9C89/Caches/Files/2026-06/99D5CB8527366A511B85DABF30CD3E86/咻咻勇者_台服美术字统计_反馈+Final.xlsx"
LANGDESC = str(Path(__file__).parent / "source" / "LanguageDesc.xlsx")
TGT = str(Path(__file__).parent / "source" / "咻咻勇者--内部工作表格.xlsx")

DATA = Path(__file__).parent / "data"
OUT_REF = DATA / "xiuxiu_termsheet_ref.xlsx"
OUT_TGT = DATA / "xiuxiu_termsheet_target.xlsx"

GLOSSARY_SHEETS = [
    ("功能系統", "EN-Final"),
    ("戰鬥玩法", "EN-Final"),
    ("商業活動", "EN-Final"),
    ("待確認", "EN"),
]
INCLUDE_PENDING_SHEET = True
INCLUDE_LANGDESC = True


def clean(s):
    return s.fillna("").astype(str).str.strip()


def build_ref():
    frames = []
    for sh, encol in GLOSSARY_SHEETS:
        if sh == "待確認" and not INCLUDE_PENDING_SHEET:
            continue
        d = pd.read_excel(GLOSSARY, sheet_name=sh)
        d = d.rename(columns={"简体": "ZH", encol: "EN"})
        d["ZH"], d["EN"] = clean(d["ZH"]), clean(d["EN"])
        d = d[(d["ZH"] != "") & (d["EN"] != "")]
        d["src"] = f"glossary:{sh}"
        frames.append(d[["ZH", "EN", "src"]])
    gloss = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["ZH", "EN"])
    gloss_zh = set(gloss["ZH"])
    print(f"glossary: {len(gloss)} pairs, unique ZH={gloss['ZH'].nunique()}")

    parts = [gloss]
    if INCLUDE_LANGDESC:
        ld = pd.read_excel(LANGDESC)
        ld = ld[~ld["##var"].astype(str).str.startswith("##")]
        ld = ld.rename(columns={"ZH": "ZH", "EN": "EN"})
        ld["ZH"], ld["EN"] = clean(ld["ZH"]), clean(ld["EN"])
        ld = ld[(ld["ZH"] != "") & (ld["EN"] != "")]
        ld = ld[~ld["EN"].str.contains(r"[一-鿿]", regex=True)]
        ld["src"] = "LanguageDesc"
        ld = ld[~ld["ZH"].isin(gloss_zh)]
        ld = ld[["ZH", "EN", "src"]].drop_duplicates(subset=["ZH", "EN"])
        print(f"LanguageDesc: {len(ld)} pairs after dedup/glossary-override")
        parts.append(ld)

    ref = pd.concat(parts, ignore_index=True)
    conflicts = (ref.groupby("ZH").size() > 1).sum()
    ref.to_excel(OUT_REF, index=False)
    print(f"REF -> {OUT_REF.name}: {len(ref)} rows, ZH groups with multiple EN: {conflicts}")


def build_target():
    df = pd.read_excel(TGT, sheet_name="术语总表")
    df["_row"] = df.index + 2
    cols = ["_row"] + [c for c in ["Date", "ZH", "EN", "Note", "原文参考", "File"] if c in df.columns]
    out = df[cols].copy()
    out["ZH"] = clean(out["ZH"])
    out = out[out["ZH"] != ""]
    empty = out["EN"].isna() | (out["EN"].astype(str).str.strip() == "")
    sub = out[empty].copy()
    sub.to_excel(OUT_TGT, index=False)
    print(f"TGT -> {OUT_TGT.name}: {len(sub)} empty-EN terms (of {len(out)} total; {len(out) - len(sub)} kept untouched)")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    build_ref()
    build_target()
    print("done")
