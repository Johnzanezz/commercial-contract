#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_review_outputs.py — 交付门禁自校验（商事合同专家 · 工具增强版）

读取红线 docx + operations.json，校验：
  1. 每条操作均已落地（insert/delete/replace 的修订文本存在；comment 批注存在）；
  2. 所有 w:ins / w:del / w:comment 的 author 均为「法大大iTerms」（执业身份红线）；
  3. verification_record.json 结构含 6 个必填字段。

产出：
  --verification  verification_record.json（必含 6 字段）
  --report        report.json（门禁明细）

退出码：
  0 = passed      （可交付）
  1 = needs_retry （操作未落地 / 结构缺字段，可补跑修正）
  2 = policy_blocked （作者红线被突破，必须转人工）
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from docx import Document
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

REQUIRED_AUTHOR = "法大大iTerms"
EXPERT = "commercial-contract-expert"
SCHEMA_VERSION = "1.0.0"
REQUIRED_VR_FIELDS = [
    "schema_version", "expert", "generated_at",
    "operations_summary", "disclaimer_checked", "policy_status",
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ins_text(e):
    return "".join(t.text or "" for t in e.iter(qn("w:t")))


def del_text(e):
    return "".join(t.text or "" for t in e.iter(qn("w:delText")))


def gather_comments(doc):
    """返回 (comments_root, all_comment_texts_by_id)。"""
    for rel in doc.part.rels.values():
        if rel.reltype == RT.COMMENTS:
            root = rel.target_part._element
            texts = {}
            for c in root.findall(qn("w:comment")):
                cid = c.get(qn("w:id"))
                txt = "".join(t.text or "" for t in c.iter(qn("w:t")))
                texts[cid] = txt
                author = c.get(qn("w:author"))
                if author != REQUIRED_AUTHOR:
                    return root, texts, False  # author violation
            return root, texts, True
    return None, {}, True


def op_landed(op, ins_els, del_els, comment_texts):
    """校验单条操作是否已在红线中落地。返回 (ok, reason)。"""
    t = op.get("type")
    if t == "insert":
        text = op.get("text", "")
        if not text:
            return False, "insert 缺 text"
        for e in ins_els:
            if text in ins_text(e):
                return True, None
        return False, "insert 文本未出现在任何 w:ins"
    if t == "delete":
        find = op.get("find", "")
        if not find:
            return False, "delete 缺 find"
        for e in del_els:
            if find in del_text(e):
                return True, None
        return False, "delete 文本未出现在任何 w:del"
    if t == "replace":
        find = op.get("find", "")
        text = op.get("text", "")
        if not find or not text:
            return False, "replace 缺 find/text"
        del_ok = any(find in del_text(e) for e in del_els)
        ins_ok = any(text in ins_text(e) for e in ins_els)
        if del_ok and ins_ok:
            return True, None
        return False, "replace 未同时落地 w:del(旧)+w:ins(新)"
    if t == "comment":
        comment = op.get("comment", "")
        basis = op.get("basis", "")
        if not comment_texts:
            return False, "comments.xml 缺失或为空"
        for cid, txt in comment_texts.items():
            if comment and comment in txt:
                return True, None
            if basis and basis in txt:
                return True, None
        return False, "comment 批注正文未出现在 comments.xml"
    return False, "未知 type: %r" % t


def main():
    ap = argparse.ArgumentParser(description="红线交付门禁自校验")
    ap.add_argument("--redline", required=True, help="红线 docx")
    ap.add_argument("--ops", required=True, help="operations.json")
    ap.add_argument("--verification", required=True, help="输出 verification_record.json 路径")
    ap.add_argument("--report", required=True, help="输出 report.json 路径")
    ap.add_argument("--disclaimer-checked", dest="disclaimer_checked",
                    action="store_true", help="标注已通过 check_disclaimer.py 机检")
    args = ap.parse_args()

    with open(args.ops, "r", encoding="utf-8") as f:
        ops = json.load(f)
    op_list = ops.get("operations", [])

    doc = Document(args.redline)
    root = doc.element

    ins_els = root.findall(".//" + qn("w:ins"))
    del_els = root.findall(".//" + qn("w:del"))
    comment_refs = root.findall(".//" + qn("w:commentReference"))

    # 作者红线校验
    author_violation = False
    authors = set()
    for e in ins_els + del_els:
        a = e.get(qn("w:author"))
        authors.add(a)
        if a != REQUIRED_AUTHOR:
            author_violation = True
    comments_root, comment_texts, comments_author_ok = gather_comments(doc)
    if not comments_author_ok:
        author_violation = True
    if comment_refs and comments_root is None:
        # 正文引用了批注但未找到 comments.xml
        author_violation = author_violation  # 结构问题，走 needs_retry

    # 逐条操作落地校验
    findings = []
    ops_summary = []
    all_landed = True
    for op in op_list:
        ok, reason = op_landed(op, ins_els, del_els, comment_texts)
        ops_summary.append({
            "id": op.get("id"),
            "type": op.get("type"),
            "risk": op.get("risk"),
            "basis": op.get("basis"),
        })
        if not ok:
            all_landed = False
            findings.append({
                "id": op.get("id"), "type": "unlanded",
                "severity": "error", "message": reason,
            })

    # 作者红线发现
    if author_violation:
        findings.append({
            "type": "author_redline", "severity": "critical",
            "message": "存在 author 非「%s」的修订/批注（执业身份红线被突破）" % REQUIRED_AUTHOR,
            "authors_found": sorted(a for a in authors if a is not None),
        })

    # 结构校验：6 字段（本脚本负责产出，若因异常无法产出则视为 needs_retry）
    vr_structure_ok = True
    for fld in REQUIRED_VR_FIELDS:
        # operations_summary 由本脚本生成；disclaimer_checked 由参数决定；其余固定产出
        if fld not in ("operations_summary", "disclaimer_checked", "policy_status",
                       "schema_version", "expert", "generated_at"):
            vr_structure_ok = False

    # 判定 policy_status 与退出码
    if author_violation:
        policy_status = "policy_blocked"
        exit_code = 2
    elif (not all_landed) or (not vr_structure_ok) or (comment_refs and comments_root is None):
        policy_status = "needs_retry"
        exit_code = 1
    else:
        policy_status = "passed"
        exit_code = 0

    generated_at = now_iso()

    verification_record = {
        "schema_version": SCHEMA_VERSION,
        "expert": EXPERT,
        "generated_at": generated_at,
        "operations_summary": ops_summary,
        "disclaimer_checked": bool(args.disclaimer_checked),
        "policy_status": policy_status,
    }
    with open(args.verification, "w", encoding="utf-8") as f:
        json.dump(verification_record, f, ensure_ascii=False, indent=2)

    report = {
        "schema_version": SCHEMA_VERSION,
        "policy_status": policy_status,
        "passed": policy_status == "passed",
        "operations_total": len(op_list),
        "operations_landed": sum(1 for op in op_list
                                 if op_landed(op, ins_els, del_els, comment_texts)[0]),
        "revision_counts": {
            "insert": len(ins_els),
            "delete": len(del_els),
            "comment_reference": len(comment_refs),
        },
        "authors": sorted(a for a in authors if a is not None),
        "required_author": REQUIRED_AUTHOR,
        "author_redline_ok": not author_violation,
        "generated_at": generated_at,
        "findings": findings,
    }
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "policy_status": policy_status,
        "exit_code": exit_code,
        "operations_landed": report["operations_landed"],
        "operations_total": report["operations_total"],
        "author_redline_ok": report["author_redline_ok"],
        "findings_count": len(findings),
    }, ensure_ascii=False, indent=2))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
