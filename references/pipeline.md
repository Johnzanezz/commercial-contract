# 工具增强版 · 脚本标准管线

本文件规范「商事合同专家 · 工具增强版」三个脚本的输入/输出契约与调用顺序。运行环境需 Python 3.10+ 与 `python-docx`（`pip install python-docx`）。所有修订与批注 author 固定为 **法大大iTerms**（执业身份红线，不可改）。

---

## 一、总览

```
合同.docx ──┐
            ├─▶ review_docx.py ──▶ 红线.docx（w:ins/w:del + comments.xml）
operations.json ─┘                              │
                                               ▼
                              validate_review_outputs.py ──▶ report.json + verification_record.json
                                               │ （退出码 0/1/2）
                                               ▼
交付文本.md ──▶ check_disclaimer.py ──▶ 免责/绝对化机检（退出码 0/1）
```

- `review_docx.py`：把审查意图变成真实 Word 修订 + 批注。
- `validate_review_outputs.py`：交付门禁自校验（操作是否落地、作者红线、verification_record 结构）。
- `check_disclaimer.py`：对交付文本做执业安全机检（免责声明 + 绝对化措辞）。

---

## 二、operations.json 字段规范

```json
{
  "author": "法大大iTerms",           // 可选，缺省用脚本 --author
  "date": "2026-07-28T19:00:00Z",     // 可选，批注/修订时间
  "operations": [
    { "id": 1, "type": "insert",  "para": 2, "text": "新增文本",
      "position": "append", "risk": "medium", "basis": "《民法典》第510条" },
    { "id": 2, "type": "delete",  "para": 3, "find": "要删除的文本",
      "risk": "high", "basis": "《民法典》第497条", "comment": "该格式条款可能无效" },
    { "id": 3, "type": "replace", "para": 4, "find": "旧文本", "text": "新文本",
      "risk": "high", "basis": "...", "comment": "违约金过高可调减" },
    { "id": 4, "type": "comment", "para": 5, "find": "锚定文本可选",
      "risk": "high", "basis": "...", "comment": "高风险说明" }
  ]
}
```

### 字段说明
| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 操作序号（用于校验报告定位） |
| `type` | 是 | `insert` / `delete` / `replace` / `comment` |
| `para` | 条件 | 段落索引（0 起）；与 `anchor` 二选一 |
| `anchor` | 条件 | 锚定文本，命中含该文本的段落（与 `para` 二选一，优先级低于 `para`） |
| `find` | 条件 | `delete`/`replace`/`comment` 需命中的正文字 |
| `text` | 条件 | `insert`/`replace` 的新文本 |
| `position` | 否 | `insert`：`append`(默认)/`before` |
| `risk` | 否 | `high`/`medium`/`low` |
| `basis` | 否 | 法律依据（写入批注/报告） |
| `comment` | 否 | 批注正文；`delete`/`replace` 亦可附带，会在该段追加批注 |

> `para` 索引基于 `doc.paragraphs` 顺序（python-docx 的段落迭代顺序）。`find` 在当前段落内首个命中的 run 上操作；若命中文本跨多个 run，需先用 `anchor` 定位整段或将文本合并到同一 run。

---

## 三、verification_record.json 字段规范

`validate_review_outputs.py` 要求以下 6 个字段齐备（缺字段 → `needs_retry` 退出码 1）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 契约版本，如 `"1.0.0"` |
| `expert` | string | 专家标识，如 `"commercial-contract-expert"` |
| `generated_at` | string | ISO8601 生成时间 |
| `operations_summary` | array | 每条操作的 `{id,type,risk,basis}` 摘要 |
| `disclaimer_checked` | bool | 是否已过 `check_disclaimer.py` |
| `policy_status` | string | `passed` / `needs_retry` / `policy_blocked` |

示例：
```json
{
  "schema_version": "1.0.0",
  "expert": "commercial-contract-expert",
  "generated_at": "2026-07-28T19:00:00Z",
  "operations_summary": [
    {"id":1,"type":"insert","risk":"medium","basis":"《民法典》第510条"},
    {"id":2,"type":"delete","risk":"high","basis":"《民法典》第497条"}
  ],
  "disclaimer_checked": true,
  "policy_status": "passed"
}
```

---

## 四、调用示例（端到端）

```bash
# 0) 环境
pip install python-docx

# 1) 生成红线
python scripts/review_docx.py \
    --source 采购合同.docx --ops operations.json --output 红线.docx

# 2) 门禁自校验（必须 passed 才能交付）
python scripts/validate_review_outputs.py \
    --redline 红线.docx --ops operations.json \
    --verification verification_record.json --report report.json
#   退出码 0=passed / 1=needs_retry / 2=policy_blocked

# 3) 执业安全机检（交付文本）
python scripts/check_disclaimer.py --file 审查意见.md --require-quick-prefix
#   退出码 0=ok / 1=violation
```

---

## 五、降级策略

- 运行环境无 Python / python-docx：`review_docx.py` 与 `validate_review_outputs.py` 不可用，降级为「文本级红线 + 人工声明」，交付说明中标注"未生成 OOXML 红线"。
- `check_disclaimer.py` 对纯文本/Markdown 不依赖 python-docx，仅 `.docx` 输入需要；建议始终运行。
- 任一脚本退出码非零：先按提示修正，**禁止**带着红线/红线违规交付；`policy_blocked` 必须转人工。

---

## 六、调用时序与失败处置

### 6.1 调用时序（标准顺序，不可颠倒）

```
operations.json ──▶ [1] review_docx.py ──▶ 红线.docx
                                          │
                              [2] validate_review_outputs.py ──▶ report.json + verification_record.json
                                          │ （退出码 0 / 1 / 2）
                              [3] check_disclaimer.py ──▶ 免责/绝对化机检
                                          │ （退出码 0 / 1）
                              [4] 带 --disclaimer-checked 重跑 validate，落定 disclaimer_checked=true
```

1. **生成 operations.json**：由代理将风险项与修改意图结构化为操作清单（字段见第二节），`author` 缺省即「法大大iTerms」。
2. **生成红线**：`review_docx.py` 落地真实 OOXML 修订 + 批注。退出码 **0 = 全部操作已落地**；**1 = 至少一个操作未落地**（find 未命中 / 段落未定位 / 参数缺失）。
3. **门禁自校验**：`validate_review_outputs.py` 校验操作落地、作者红线、verification_record 六字段。退出码 **0 = passed** / **1 = needs_retry** / **2 = policy_blocked**。
4. **执业安全机检**：`check_disclaimer.py` 对交付文本做免责 + 绝对化双检。退出码 **0 = ok** / **1 = violation**。
5. **落定免责标记**：步骤 3 的 `verification_record.json` 含 `disclaimer_checked` 字段；步骤 4 通过后，以 `--disclaimer-checked` 重跑步骤 3，将该字段置 `true` 并定稿（否则保持 `false`，视为未过机检）。

> 时序约束：步骤 2 必须在步骤 3 之前（门禁校验的是红线稿）；步骤 4 可与 2/3 并行，但其结论必须在步骤 5 落定前得出——**禁止 `disclaimer_checked=true` 而实际未过机检**。

### 6.2 失败处置矩阵

| 失败点 | 退出码 | 含义 | 处置 |
|---|---|---|---|
| review | 1 | 操作未落地（find/para/anchor 问题） | 读 review 输出的 `details[].error` 定位；修正 operations.json 后**重跑 review → validate**。定点续写封顶 2 轮（见 §4）。 |
| validate | 1 (needs_retry) | 操作未落地 / verification_record 结构缺字段 | 读 `report.json` 的 `findings` 逐条回到 review 修正；同一红线稿定点补正，**禁止全量重跑**。 |
| validate | 2 (policy_blocked) | 作者红线被突破（出现非「法大大iTerms」的修订/批注） | **执业安全零容忍**，禁止自动修正；转人工（执业律师）复核并确认红线身份后，方可重新生成。 |
| check_disclaimer | 1 (violation) | 交付文本缺免责声明 / 命中绝对化措辞 | 修正交付文本（补声明或去绝对化词）后重检；**不得带着红线交付**。 |
| 环境缺失 | — | 无 Python / python-docx | 走 §5 降级：文本级红线 + 人工声明，交付说明标注"未生成 OOXML 红线"。 |

### 6.3 总原则

- **硬门禁非零即阻断**：review / validate / check_disclaimer 任一退出码非零，均禁止带着红线或违规文本交付。
- **定点续写、禁止全量重跑**：制品隔离（红线只补红线、报告只补报告）；同一定位问题补正封顶 2 轮，仍不过则转 `policy_blocked` 转人工（§4 性能铁律）。
- **作者红线不可妥协**：所有 `w:ins` / `w:del` / `w:comment` 的 author 必须为「法大大iTerms」；一旦校验发现异值，视为 `policy_blocked`，**绝不自动改写身份**。

> 回归测试：本技能 `scripts/test_redline_pipeline.py` 固化了上述时序与退出码语义（正向全 PASS、作者篡改→2、未落地→1）。改动任一脚本后务必跑通该测试再交付。

### 6.4 CI 接入（防止门禁语义回归）

回归测试已接入三类 CI 载体，改动 `scripts/` 后任一通道均可自动验证 0/1/2 退出码不被破坏：

1. **GitHub Actions（随技能发布即用）**
   - 工作流文件：`commercial-contract/.github/workflows/redline-regression.yml`
   - 触发：push/PR 命中 `scripts/**` 或 `references/**` 自动跑；亦支持 `workflow_dispatch` 手动触发。
   - 发布注意：GitHub 仅读取**仓库根** `.github/workflows/`。将技能纳入 Git 仓库时，须把本文件移到仓库根；技能位于子目录（如 `commercial-contract/`）时，保持 `env.SKILL_DIR` 不变即可。

2. **本地一键跑测（run_ci.sh）**
   - 路径：`commercial-contract/scripts/run_ci.sh`
   - 用法：`bash run_ci.sh`（或 `REDLINE_PYTHON=/path/to/python bash run_ci.sh`）
   - 自动解析解释器优先级：环境变量 `REDLINE_PYTHON` → 受管 venv → 本地 venv → 新建 venv 并装 python-docx/lxml；透传退出码。
   - 路径已兼容 MSYS/Git Bash（cygpath 转 Windows 原生格式）与 Linux CI。

3. **WorkBuddy 定时自动化（当前无远端环境真实运行）**
   - 已建每日（RRULE:FREQ=DAILY）自动化，调用 `run_ci.sh`，退出码非 0 即回报失败、不自动改写引擎代码。
   - 在 WorkBuddy「设置 → 自动化」中可查看运行历史、调整频率或暂停。
