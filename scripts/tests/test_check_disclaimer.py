#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_check_disclaimer.py — check_disclaimer.py 函数级单元测试

覆盖：
  - strip_quotes：剥离各类引号，避免引用文本误触/逃逸规则
  - has_disclaimer：免责声明命中
  - scan：绝对化措辞命中且「绝对化」自身不误伤
  - main 退出码语义：0(ok) / 1(violation) / 2(usage)

运行：python -m unittest tests.test_check_disclaimer -v
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HERE, "check_disclaimer.py")

_spec = importlib.util.spec_from_file_location("check_disclaimer", SCRIPT)
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)


class TestStripQuotes(unittest.TestCase):
    def test_removes_fullwidth_quotes(self):
        self.assertEqual(cd.strip_quotes("「仅供参考」"), "仅供参考")

    def test_removes_ascii_quotes(self):
        self.assertEqual(cd.strip_quotes('"绝对胜诉"'), "绝对胜诉")

    def test_removes_brackets(self):
        self.assertEqual(cd.strip_quotes("（示例：保证胜诉）"), "示例：保证胜诉")

    def test_idempotent(self):
        s = "无任何风险"
        self.assertEqual(cd.strip_quotes(cd.strip_quotes(s)), cd.strip_quotes(s))


class TestHasDisclaimer(unittest.TestCase):
    def test_present_various(self):
        for s in ["本分析仅供参考", "不构成法律意见", "需经执业律师审核", "免责声明：……"]:
            self.assertTrue(cd.has_disclaimer(s), msg=s)

    def test_absent(self):
        self.assertFalse(cd.has_disclaimer("这是一段普通的合同条款描述。"))


class TestScan(unittest.TestCase):
    def test_finds_absolute(self):
        hits = cd.scan(cd.ABSOLUTE_PATTERNS, "我们保证胜诉")
        self.assertTrue(any("保证胜诉" in w for _, w, _ in hits))

    def test_finds_percent(self):
        hits = cd.scan(cd.ABSOLUTE_PATTERNS, "胜率百分之百")
        self.assertTrue(any("百分之百" in w for _, w, _ in hits))

    def test_excludes_self_absolute(self):
        # 「绝对化」不应命中「绝对(?!化)」
        hits = cd.scan(cd.ABSOLUTE_PATTERNS, "避免绝对化表述")
        self.assertFalse(any("绝对化" == w for _, w, _ in hits))

    def test_overreach_detected(self):
        hits = cd.scan(cd.OVERREACH_PATTERNS, "本所保证您一定赢")
        self.assertTrue(any("本所保证" in w for _, w, _ in hits))


class TestMainExitCodes(unittest.TestCase):
    def _write(self, content):
        f = tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False)
        try:
            f.write(content)
        finally:
            f.close()
        return f.name

    def _run(self, *extra):
        p = self._write("免责声明：本分析仅供参考，不构成法律意见。\n这是正常的交付文本。")
        return subprocess.run(
            [sys.executable, SCRIPT, "--file", p, *extra],
            capture_output=True, text=True)

    def test_ok_exit0(self):
        rc = self._run().returncode
        self.assertEqual(rc, 0)

    def test_missing_disclaimer_exit1(self):
        p = self._write("我们保证胜诉，一定赢。")
        rc = subprocess.run([sys.executable, SCRIPT, "--file", p],
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 1)

    def test_quick_prefix_violation_exit1(self):
        # 免责声明存在（全局通过），但不在前 3 个非空行内 → quick 前缀校验失败
        content = (
            "正文第一段业务描述内容较长。\n"
            "正文第二段继续说明事项。\n"
            "正文第三段补充背景信息。\n"
            "免责声明：本分析仅供参考，不构成法律意见。\n"
        )
        p = self._write(content)
        rc = subprocess.run([sys.executable, SCRIPT, "--file", p, "--require-quick-prefix"],
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 1)

    def test_quick_prefix_ok_exit0(self):
        p = self._write("免责声明：本分析仅供参考。\n正文段落。")
        rc = subprocess.run([sys.executable, SCRIPT, "--file", p, "--require-quick-prefix"],
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 0)

    def test_missing_file_exit2(self):
        rc = subprocess.run([sys.executable, SCRIPT, "--file", "nope_does_not_exist.md"],
                            capture_output=True, text=True).returncode
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
