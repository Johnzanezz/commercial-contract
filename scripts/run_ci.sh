#!/usr/bin/env bash
# run_ci.sh — OOXML 红线引擎本地一键回归
#
# 解析可用解释器优先级：
#   1) 环境变量 REDLINE_PYTHON（若显式指定且能 import docx/lxml）
#   2) 受管 venv（WorkBuddy 隔离 Python：$HOME/.workbuddy/binaries/python/envs/default）
#   3) 本技能内本地 venv（$SCRIPT_DIR/.venv）
#   4) 以上皆无 → 新建本地 venv 并安装 python-docx + lxml
# 随后用该解释器运行 test_redline_pipeline.py，透传其退出码。
#
# 用法：
#   bash run_ci.sh
#   REDLINE_PYTHON=/path/to/python bash run_ci.sh
#
# 退出码：test_redline_pipeline.py 全通过=0；任意断言失败=非0（CI 据此阻断）。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST="$SCRIPT_DIR/test_redline_pipeline.py"

PY="${REDLINE_PYTHON:-}"
MANAGED="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
LOCAL_VENV="$SCRIPT_DIR/.venv"

can_import() {
  local p="$1"
  [ -n "$p" ] && [ -x "$p" ] && "$p" -c "import docx, lxml" >/dev/null 2>&1
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
  echo "[run_ci] 未找到可用解释器，创建本地 venv: $LOCAL_VENV" >&2
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

echo "[run_ci] 解释器: $PY"

# ---- 单元测试阶段（函数级，先于端到端回归；失败则快速阻断）----
UT_DIR="$SCRIPT_DIR/tests"
RUN_UT_DIR="$UT_DIR"
if command -v cygpath >/dev/null 2>&1 && [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  RUN_UT_DIR="$(cygpath -w "$UT_DIR")"
fi
echo "[run_ci] 运行单元测试: discover $UT_DIR"
"$PY" -m unittest discover -s "$RUN_UT_DIR" -p "test_*.py" -v
ut_rc=$?
if [ "$ut_rc" -ne 0 ]; then
  echo "[run_ci] 单元测试失败，退出码: $ut_rc"
  exit "$ut_rc"
fi
echo "[run_ci] 单元测试通过"

# ---- 端到端回归阶段 ----
echo "[run_ci] 运行: $TEST"

# MSYS/Cygwin 下，python.exe 是原生 Windows 程序：作为命令执行时由 bash 自动翻译路径，
# 但作为「参数」传入的路径不会翻译，需转成 Windows 原生格式，否则被误解为 C:\c\...。
RUN_TEST="$TEST"
RUN_PY="$PY"
if command -v cygpath >/dev/null 2>&1 && [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
  RUN_TEST="$(cygpath -w "$TEST")"
  RUN_PY="$(cygpath -w "$PY")"
fi

"$PY" "$RUN_TEST" --python "$RUN_PY"
rc=$?
echo "[run_ci] 退出码: $rc"
exit $rc
