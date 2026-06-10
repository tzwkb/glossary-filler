"""Strip CJK pseudo-translations from termsheet output and progress cache.

EN values containing CJK came from untranslated LanguageDesc placeholder rows
(EN cell = copied ZH). Clears them in the filled xlsx and deletes the matching
progress entries so future runs re-classify those terms.
"""
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
FILLED = HERE / "output" / "咻咻勇者_术语总表_filled.xlsx"
PROGRESS = HERE / "runtime" / "xiuxiu_termsheet_progress.json"
CJK = re.compile(r"[一-鿿]")


def main():
    df = pd.read_excel(FILLED)
    cleared = 0
    for col in ["EN", "Alt_EN_1", "Alt_EN_2", "Alt_EN_3"]:
        if col not in df.columns:
            continue
        mask = df[col].fillna("").astype(str).str.contains(CJK)
        if col == "EN":
            cleared = int(mask.sum())
            print(f"clearing {cleared} CJK values in EN:")
            print(df.loc[mask, "ZH"].to_string(index=False))
        df.loc[mask, col] = ""
    df.to_excel(FILLED, index=False)
    en = df["EN"].fillna("").astype(str).str.strip()
    print(f"output rewritten, filled now: {(en != '').sum()}/{len(df)}")

    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    bad = [k for k, v in prog.items() if isinstance(v, dict) and CJK.search(v.get("best", ""))]
    for k in bad:
        del prog[k]
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"progress entries removed: {len(bad)}, remaining: {len(prog)}")


if __name__ == "__main__":
    main()
