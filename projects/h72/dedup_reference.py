"""按状态优先级去重参考 Excel：原文相同→取最高优先级，同级多条译文全保留"""
import sys
import pandas as pd
from pathlib import Path

STATUS_TIER = {
    "Designer Reviewed": 1,
    "Designer_不进TM": 1,
    "CQA_Done": 2,
    "Done_LQA edited": 3,
    "Done_VO": 3,
    "Done": 4,
    "Done by TM": 4,
    "v1.1 Done by TM": 4,
    "Translate": 5,
    "Auto-fill": 5,
    "小语种自动机翻": 5,
    "New": 5,
}

INPUT = Path(r"E:\Documents\WXWork\1688854428801306\Cache\File\2026-05\h72_global_trunk_Strings_20260514132646.xlsx")
OUTPUT = Path(r"E:\Langlobal\5.11芷伊术语提取\data\h72_global_trunk_Strings_dedup.xlsx")


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    print(f"读取 {INPUT.name} ...")
    df = pd.read_excel(INPUT)
    print(f"  总行数: {len(df)}")

    df["_tier"] = df["状态"].map(STATUS_TIER).fillna(99).astype(int)

    # 每组取最高优先级（最小 tier）
    best_tier = df.groupby("原文")["_tier"].transform("min")
    keep = df[df["_tier"] == best_tier].copy()

    # 同原文同译文去重（完全相同的翻译只留一条）
    keep.drop_duplicates(subset=["原文", "译文"], inplace=True)

    deduped = keep[["Ukey", "原文", "译文", "状态"]].sort_values("原文").reset_index(drop=True)

    print(f"  去重后: {len(deduped)} 行 (移除 {len(df) - len(deduped)} 行)")

    # 统计
    multi_groups = (deduped.groupby("原文").size() > 1).sum()
    print(f"  保留多条译文的原文组: {multi_groups}")

    deduped.to_excel(OUTPUT, index=False)
    print(f"输出: {OUTPUT}")


if __name__ == "__main__":
    main()
