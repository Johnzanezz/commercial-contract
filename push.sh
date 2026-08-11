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
#   - 远端 origin 已在部署时配置为 https://github.com/Johnzanezz/commercial-contract.git
#   - 推送时需输入 GitHub 用户名(Johnzanezz) + Personal Access Token（非登录密码，需勾选 repo）
#   - 若远端为空仓库，pull --rebase 会失败属正常，脚本以 || true 跳过并继续 push

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

read -rp "Enter your GitHub email: " GH_EMAIL
git config user.name "Johnzanezz"
git config user.email "$GH_EMAIL"

git branch -M main
git pull --rebase origin main || true
git push -u origin main

echo ""
echo "Pushed. Verify the CI run at:"
echo "  https://github.com/Johnzanezz/commercial-contract/actions"
