#!/usr/bin/env bash
# push.sh — 零下载推送 OOXML 红线引擎至 GitHub
#
# 复用 WorkBuddy 自带的便携 Git（vendor/PortableGit），无需安装 Git for Windows。
# 适用场景：本机未安装 Git for Windows，或官网下载过慢。
#
# 用法（在您本机终端，非 WorkBuddy 沙箱）：
#   双击同目录的 push.bat；或手动执行：
#   "C:\Users\inter\.workbuddy\vendor\PortableGit\bin\bash.exe" push.sh
#
# 说明：
#   - 远端 origin 已切为 SSH：git@github.com:Johnzanezz/commercial-contract.git（走本机 SSH 密钥，无需 PAT）
#   - 首次连接 github.com 会提示接受主机密钥，输入 yes 即可（仅首次）
#   - 若远端为空仓库，pull --rebase 会失败属正常，脚本以 || true 跳过并继续 push
#   - 自动提交本地未提交的改动后再推送，避免「未提交改动阻断 pull --rebase / 漏推」

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

read -rp "Enter your GitHub email: " GH_EMAIL
git config user.name "Johnzanezz"
git config user.email "$GH_EMAIL"

# 自动提交本地待推送改动（受 .gitignore 约束），避免未提交改动阻断 pull 或漏推
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "[push] 检测到未提交改动，自动暂存并提交..."
  git add -A
  git commit -q -m "chore: 自动提交本地待推送改动（push.sh 触发）" \
    && echo "[push] 已提交本地改动" \
    || echo "[push] 无可提交内容，跳过"
fi

git branch -M main
git pull --rebase origin main || true
git push -u origin main

echo ""
echo "Pushed. Verify the CI run at:"
echo "  https://github.com/Johnzanezz/commercial-contract/actions"
