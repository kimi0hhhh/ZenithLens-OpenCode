# -*- coding: utf-8 -*-
"""build-r2 与源码根逐文件 MD5 对齐校验（S4 · G-DL-02 证据）。

输出 build_manifest.json：files[]（相对路径 / 源 MD5 / build MD5 / 是否一致 / 字节）
统计：total / matched / mismatched / builder_authored（构建者新增，不含对齐对象）。
运行：python verify_build_alignment.py
"""
import hashlib
import io
import json
import os

SRC = r"C:\Users\10719\Documents\ZenithLens-OpenCode"
DST = os.path.join(SRC, "docs", "04-integration", "build-r2")
HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER_AUTHORED = {"README-START.md", "start.cmd", "start.ps1"}
SKIP_DIRS = {"__pycache__"}


def md5(path):
    h = hashlib.md5()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn.endswith(".tmp"):
                continue
            full = os.path.join(base, fn)
            rel = os.path.relpath(full, root)
            out.append(rel.replace("\\", "/"))
    return sorted(out)


def main():
    files = []
    mismatched = []
    for rel in walk(DST):
        if rel in BUILDER_AUTHORED:
            continue
        dst = os.path.join(DST, rel.replace("/", os.sep))
        src = os.path.join(SRC, rel.replace("/", os.sep))
        rec = {"rel": rel, "size": os.path.getsize(dst)}
        if not os.path.isfile(src):
            rec.update({"src_md5": None, "dst_md5": md5(dst), "match": False,
                        "note": "source counterpart missing"})
            mismatched.append(rel)
        else:
            s, d = md5(src), md5(dst)
            rec.update({"src_md5": s, "dst_md5": d, "match": s == d})
            if s != d:
                mismatched.append(rel)
        files.append(rec)
    report = {
        "source_root": SRC,
        "build_root": DST,
        "total_content_files": len(files),
        "matched": sum(1 for f in files if f["match"]),
        "mismatched": mismatched,
        "builder_authored": sorted(BUILDER_AUTHORED),
        "excluded_roots": ["_archive_round1/", "docs/", "README-START.md(源根 R1 版)"],
        "note": "content files = 根 *.py + static/** + tests/** + data/** + ledger/**；builder authored 为构建者新增文件，不参与对齐",
        "files": files,
    }
    out = os.path.join(HERE, "build_manifest.json")
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=1))
    print("total=%d matched=%d mismatched=%d" % (
        report["total_content_files"], report["matched"], len(mismatched)))
    for m in mismatched[:20]:
        print("MISMATCH:", m)
    return 0 if not mismatched else 1


if __name__ == "__main__":
    raise SystemExit(main())
