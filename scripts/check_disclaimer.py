#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
执业安全机检：免责声明位置 + 绝对化措辞双检。

本地补齐说明
------------
上游市场包（skillId skill_2084220429014720512）未随包提供 scripts/ 目录，
而 SKILL.md §6.7 / §7.121 将本脚本列为交付前硬门禁。本文件依据 SKILL.md
中记载的 CLI 约定与退出码语义在本地实现，行为与文档一致。
若后续市场方提供官方脚本，请以官方版本覆盖本文件。

用法
----
    python check_disclaimer.py --file 交付文本.md
    python check_disclaimer.py --file 交付文本.md --require-quick-prefix

退出码
------
    0  ok         —— 免责声明齐备且未命中绝对化措辞
    1  violation  —— 免责声明缺失/位置不符，或命中绝对化措辞
    2  usage      —— 参数或文件错误
"""

import argparse
import re
import sys
from pathlib import Path

# --- 免责声明识别 ---------------------------------------------------------
DISCLAIMER_PATTERNS = [
    r"仅供参考",
    r"不构成(?:正式)?法律意见",
    r"不构成对.{0,12}的承诺",
    r"需(?:经)?(?:执业)?律师(?:审核|确认|复核)",
    r"最终以.{0,20}为准",
    r"本(?:意见|文件|分析|报告).{0,10}(?:不替代|非)(?:正式)?法律意见",
    r"免责声明",
]

# --- 绝对化措辞（执业风险） -----------------------------------------------
# 「绝对」需负向预查排除「绝对化」自身，避免规则文本自命中
ABSOLUTE_PATTERNS = [
    r"绝对(?!化)",
    r"必然(?:胜诉|败诉|获赔|支持)?",
    r"百分之百",
    r"100\s*%",
    r"保证(?:胜诉|赢|获赔|通过)",
    r"(?:必|稳)(?:胜|赢)",
    r"包(?:赢|胜)",
    r"毫无疑问",
    r"万无一失",
    r"零风险",
    r"无任何风险",
    r"完全没有(?:问题|风险)",
    r"一定(?:能|会)(?:赢|胜诉|获赔)",
    r"绝无(?:可能|风险|例外)",
]

# --- 越权 / 超范围承诺 ----------------------------------------------------
OVERREACH_PATTERNS = [
    r"我(?:方)?承诺(?:胜诉|赔付|退款)",
    r"本所保证",
    r"可以确保(?:胜诉|获赔|通过)",
    r"无需(?:再)?(?:请|委托)律师",
    r"不用(?:请|委托)律师",
    r"代(?:为|您)决策",
    r"替(?:您|你)签署",
]

QUOTE_CHARS = "「」『』“”‘’\"'《》【】()（）[]"


def strip_quotes(text: str) -> str:
    """剥离引号类字符，避免被引用的示例文本逃过或误触规则匹配。"""
    return re.sub("[" + re.escape(QUOTE_CHARS) + "]", "", text)


def scan(patterns, text):
    hits = []
    for p in patterns:
        for m in re.finditer(p, text):
            s = max(0, m.start() - 18)
            e = min(len(text), m.end() + 18)
            hits.append((p, m.group(0), text[s:e].replace("\n", " ")))
    return hits


def has_disclaimer(text: str) -> bool:
    return any(re.search(p, text) for p in DISCLAIMER_PATTERNS)


def main() -> int:
    ap = argparse.ArgumentParser(description="执业安全机检：免责声明 + 绝对化措辞")
    ap.add_argument("--file", required=True, help="待检查的交付文本（.md/.txt）")
    ap.add_argument(
        "--require-quick-prefix",
        action="store_true",
        help="要求免责声明出现在正文前 3 个非空行内（quick 模式前缀约定）",
    )
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"[usage] 文件不存在: {path}", file=sys.stderr)
        return 2

    raw = path.read_text(encoding="utf-8", errors="replace")
    text = strip_quotes(raw)

    violations = []

    # 1. 免责声明存在性
    if not has_disclaimer(text):
        violations.append("免责声明缺失：未检出「仅供参考 / 不构成法律意见 / 需律师审核」等表述")

    # 2. 免责声明位置（quick 前缀）
    if args.require_quick_prefix:
        head_lines = [ln for ln in text.splitlines() if ln.strip()][:3]
        if not has_disclaimer("\n".join(head_lines)):
            violations.append("免责声明位置不符：--require-quick-prefix 要求其出现在前 3 个非空行内")

    # 3. 绝对化措辞
    abs_hits = scan(ABSOLUTE_PATTERNS, text)
    for _p, word, ctx in abs_hits:
        violations.append(f"绝对化措辞「{word}」→ …{ctx}…")

    # 4. 越权承诺
    over_hits = scan(OVERREACH_PATTERNS, text)
    for _p, word, ctx in over_hits:
        violations.append(f"越权承诺「{word}」→ …{ctx}…")

    if violations:
        print(f"[violation] {path.name} 共 {len(violations)} 项，须修正后重检：")
        for i, v in enumerate(violations, 1):
            print(f"  {i}. {v}")
        return 1

    print(f"[ok] {path.name} 通过执业安全机检（免责声明齐备，未命中绝对化措辞与越权承诺）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
