# Term Extractor

从双语 Excel 翻译工程表中自动提取术语英文译法，支持 AI 辅助多译法识别。

## 快速开始

```bash
# 1. 写一份 YAML 配置文件
# 2. 设置 API Key（二选一）
#    方式 A：环境变量
set DEEPSEEK_API_KEY=sk-xxx
#    方式 B：直接写在配置文件的 ai.api_key 字段

# 3. 干跑（不调 AI，看分类结果）
python3 cli.py my_project.yaml --dry-run

# 4. 正式运行
python3 cli.py my_project.yaml
```

## 配置文件

```yaml
# ========== 大表：多个 Excel 工程文件合并 ==========
big_table:
  sources:
    # 有表头：按列名匹配
    - path: "工程/ui_translations.xlsx"
      key_col: "Key"        # 可选，没有就留空
      zh_col: "中文"
      en_col: "English"

    # 无表头：按列号匹配（从 0 开始）
    - path: "工程/card_translations.xlsx"
      header: false         # 必须声明
      zh_col: 1             # 第 2 列为中文
      en_col: 2             # 第 3 列为英文
      # key_col 不填则自动生成空列

# ========== 目标文件：待填充术语表 ==========
target:
  path: "术语表.xlsx"
  header: true              # 默认 true，可省略
  zh_col: "ZH"              # 中文术语列
  en_col: "EN"              # 英文术语列（需填充）
  note_col: "Note"          # 可选：备注列
  source_col: "原文"         # 可选：原文引用列
  file_col: "File"          # 可选：来源文件列

# ========== 匹配规则 ==========
matching:
  max_contexts: 15          # 传给 AI 的最大上下文条数
  zero_match: "skip"        # 零匹配处理：skip（留空）

# ========== 特殊规则 ==========
special_rules:
  - when: "note == '挂饰名'"   # 触发条件
    action: "copy_from_suffix"  # 动作：从目标文件中找 ZH+suffix 的行复制 EN
    suffix: "挂饰"

  # 更多内置动作：
  # - when: "note == 'xxx'"
  #   action: "skip"             # 跳过，留空
  #
  # - when: "zh matches '.*：$'"
  #   action: "copy_from_prefix" # 找 prefix+ZH 的行复制
  #   prefix: "某种"

  # when 表达式支持：
  #   note == 'xxx'         Note 列精确匹配
  #   zh matches 'regex'    ZH 列正则匹配
  #   file == 'xxx'         File 列精确匹配

# ========== AI 配置 ==========
ai:
  api_key: "${DEEPSEEK_API_KEY}"   # 支持环境变量，也可直接写
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-v4-pro"
  concurrency: 3             # 并发数
  retries: 3                 # 失败重试次数
  max_alt: 3                 # 最多 N 个备选译法

# ========== 输出 ==========
output:
  path: "术语表_filled.xlsx"
  rename_cols:               # 可选：输出时重命名列
    原文: "Source"
```

## CLI 参数

```
用法: python3 cli.py <config.yaml> [选项]

选项:
  --target "新文件.xlsx"    覆盖目标文件路径
  --output "输出.xlsx"      覆盖输出文件路径
  --api-key "sk-xxx"        覆盖 API Key
  --model "deepseek-v4-pro" 覆盖模型
  --dry-run                 干跑，不调 AI，只打印分类统计
  --from-scratch            删除进度文件，从头重跑
```

## 处理流程

```
读取配置 → 构建大表 → 读取目标文件
    ↓
分类：精确匹配 / 包含匹配(需AI) / 特殊规则 / 零匹配
    ↓
精确匹配 → 直接填入 EN 列
包含匹配 → 调 AI 提取 best + alternatives
特殊规则 → 按规则复制/跳过
    ↓
后处理 → 过滤不在大表中的备选译法
    ↓
写入 Excel → EN 列（最佳译法）+ Alt_EN_1/2/3（备选译法）
```

## 断点续传

进度文件自动生成在配置文件同目录下，命名格式：
`<config文件名>_progress.json`

中断后重跑同一配置文件会自动续传，已完成的 AI 调用不会重复。

删除进度文件或使用 `--from-scratch` 可从头重跑。

## 输出格式

| ZH | EN | Note | Alt_EN_1 | Alt_EN_2 | Alt_EN_3 |
|----|-----|------|----------|----------|----------|
| 失眠 | Insomnia | | | | |
| 座驾 | Vehicle | 游戏机制 | Bus | Car | |
| 路边 | Roadside Trinket | 挂饰名 | Roadside Ornament | | |

- EN 列：最佳译法
- Alt_EN_1/2/3：备选译法（严格来自大表上下文，AI 编造的会被过滤）
- 精确匹配的条目没有备选（大表中只有一种英文）
- 挂饰名等特殊规则的条目，EN 与对应完整条目一致
