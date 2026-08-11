#!/usr/bin/env bash
# run_unit_tests.sh — OOXML 红线引擎函数级单元测试本地运行器
#
# 解释器解析优先级（与 run_ci.sh 一致）：
#   1) 环境变量 REDLINE_PYTHON
#   2) 受管 venv（WorkBuddy 隔离 Python）
#   3) 本地 venv（$SCRIPT_DIR/.venv）
#   4) 以上皆无 → 新建本地 venv 并安装 python-docx + lxml
#
# 用法：
#   bash run_unit_tests.sh
#   REDLINE_PYTHON=/path/to/python bash run_unit_tests.sh
#
# 退出码：全部测试通过=0；任意用例失败/错误=非0。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UT_DIR="$SCRIPT_DIR/tests"

PY="${REDLINE_PYTHON:-}"
MANAGED="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
LOCAL_VENV="$SCRIPT_DIR/.venv"

can_import() {
  local p="$1"
  [ -n "$p" ] && [ -x "$p" ] && "$p" -c "import docx, lxml, unittest" >/dev/null 2>&1
}

if can_import "$PY"; then
  :
elif can_import "$MANAGED"; then
  PY="$MANAGED"
elif [ -x "$LOCAL_VENV/Scripts/python.exe" ] && can_import "$LOCAL_VENV/Scripts/python.exe"; then
  PY="$LOCAL_VENV/Scripts/python.exe"
elif [ -x "$LOCAL_VENV/bin/python" ] && can_import "$LOCAL_VENV/bin/python"; then
  PY="$LOCAL_VENV/bin/python"
fi

if ! can_import "$PY"; then
  echo "[run_unit_tests] 未找到可用解释器，创建本地 venv: $LOCAL_VENV" >&2
  python3 -m venv "$LOCAL_VENV"
  if [ -x "$LOCAL_VENV/Scripts/python.exe" ]; then
    VPY="$LOCAL_VENV/Scripts/python.exe"
  else
    VPY="$LOCAL_VENV/bin/python"
  fi
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install python-docx lxml
  PY="$VPY"
fi

echo "[run_unit_tests] 解释器: $PY"
echo "[run_unit_tests] 运行单元测试: discover $UT_DIR"

RUN_UT_DIR="$UT_DIR"
if command -v cygpath >/dev/null 2>&1 && [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  RUN_UT_DIR="$(cygpath -w "$UT_DIR")"
fi

"$PY" -m unittest discover -s "$RUN_UT_DIR" -p "test_*.py" -v
rc=$?
echo "[run_unit_tests] 退出码: $rc"
exit $rc
