#!/usr/bin/env python3
"""Scan debs/ and write Packages* + Release for a Sileo/Cydia APT repo."""
from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import lzma
import tarfile
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEB_DIR = ROOT / "debs"

REPO = {
    "Origin": "ZZ Repo",
    "Label": "ZZ Repo",
    "Suite": "stable",
    "Version": "1.0",
    "Codename": "ios",
    "Architectures": "iphoneos-arm iphoneos-arm64",
    "Components": "main",
    "Description": "ZZ private Sileo repository",
}
BASE_URL = "https://kmkm209.github.io/sileo"


def sha(data: bytes, name: str) -> str:
    return hashlib.new(name, data).hexdigest()


def parse_ar(blob: bytes) -> dict[str, bytes]:
    if not blob.startswith(b"!<arch>\n"):
        raise ValueError("not an ar archive")
    off = 8
    out: dict[str, bytes] = {}
    while off + 60 <= len(blob):
        hdr = blob[off : off + 60]
        if hdr.strip() == b"":
            break
        name = hdr[0:16].decode("ascii", "replace").strip()
        size = int(hdr[48:58].decode("ascii").strip())
        off += 60
        if name.startswith("#1/"):
            nlen = int(name[3:])
            name = blob[off : off + nlen].split(b"\0", 1)[0].decode("ascii", "replace")
            payload = blob[off + nlen : off + size]
        else:
            name = name.rstrip("/")
            payload = blob[off : off + size]
        off += size + (size % 2)
        out[name] = payload
    return out


def read_control(deb: bytes) -> str:
    members = parse_ar(deb)
    tarball = None
    for key, data in members.items():
        if key.startswith("control.tar"):
            tarball = data
            break
    if tarball is None:
        raise ValueError("no control.tar in deb")
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:*") as tar:
        for info in tar.getmembers():
            if info.name.rstrip("/") in ("control", "./control"):
                f = tar.extractfile(info)
                if f is None:
                    break
                return f.read().decode("utf-8", "replace")
    raise ValueError("control file missing")


def stanza_get(text: str, key: str) -> str:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(key + ":"):
            val = [line.split(":", 1)[1].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")):
                val.append(lines[i].strip())
                i += 1
            return "\n".join(val)
        i += 1
    return ""


def build_packages() -> str:
    blocks: list[str] = []
    for deb_path in sorted(DEB_DIR.glob("*.deb")):
        blob = deb_path.read_bytes()
        control = read_control(blob).strip() + "\n"
        for drop in ("Filename", "Size", "MD5sum", "SHA1", "SHA256"):
            if stanza_get(control, drop):
                kept = []
                skip = False
                for line in control.splitlines(True):
                    if skip:
                        if line.startswith((" ", "\t")):
                            continue
                        skip = False
                    if line.startswith(drop + ":"):
                        skip = True
                        continue
                    kept.append(line)
                control = "".join(kept)
                if not control.endswith("\n"):
                    control += "\n"
        rel = deb_path.relative_to(ROOT).as_posix()
        control += f"Filename: {rel}\n"
        control += f"Size: {len(blob)}\n"
        control += f"MD5sum: {sha(blob, 'md5')}\n"
        control += f"SHA1: {sha(blob, 'sha1')}\n"
        control += f"SHA256: {sha(blob, 'sha256')}\n"
        blocks.append(control.strip() + "\n")
    return "\n".join(blocks)


def write_compressed(packages: bytes) -> dict[str, bytes]:
    files = {
        "Packages": packages,
        "Packages.gz": gzip.compress(packages, mtime=0),
        "Packages.bz2": bz2.compress(packages),
        "Packages.xz": lzma.compress(packages),
    }
    for name, data in files.items():
        (ROOT / name).write_bytes(data)
    return files


def write_release(files: dict[str, bytes]) -> None:
    date = format_datetime(datetime.now(timezone.utc))
    lines = [f"{k}: {v}" for k, v in REPO.items()]
    lines.append(f"Date: {date}")
    hashes = [("MD5Sum", "md5"), ("SHA1", "sha1"), ("SHA256", "sha256")]
    for title, algo in hashes:
        lines.append(f"{title}:")
        for name in ("Packages", "Packages.gz", "Packages.bz2", "Packages.xz"):
            data = files[name]
            digest = sha(data, algo)
            lines.append(f" {digest} {len(data):>16} {name}")
    text = "\n".join(lines) + "\n"
    (ROOT / "Release").write_text(text, encoding="utf-8")


def write_index(packages: str) -> None:
    rows = []
    for block in packages.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        name = stanza_get(block, "Name") or stanza_get(block, "Package")
        ver = stanza_get(block, "Version")
        pkg = stanza_get(block, "Package")
        desc = stanza_get(block, "Description").split("\n", 1)[0]
        rows.append(
            f"<tr><td>{name}</td><td><code>{pkg}</code></td><td>{ver}</td><td>{desc}</td></tr>"
        )
    table = "\n".join(rows) or             "<tr><td colspan='4'>暂无软件包，把 .deb 放到 debs/ 或在 srcpkgs/ 写包后运行 python3 make_deb.py && python3 build.py</td></tr>"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZZ Repo</title>
<style>
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f1115; color: #e8eaed; }}
main {{ max-width: 720px; margin: 48px auto; padding: 0 20px; }}
h1 {{ font-size: 28px; margin: 0 0 8px; }}
.sub {{ color: #9aa0a6; margin-bottom: 24px; }}
.box {{ background: #1a1d24; border: 1px solid #2d3139; border-radius: 12px; padding: 16px 18px; word-break: break-all; }}
code {{ color: #8ab4f8; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 28px; }}
th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #2d3139; font-size: 14px; }}
th {{ color: #9aa0a6; font-weight: 600; }}
</style>
</head>
<body>
<main>
<h1>ZZ Repo</h1>
<p class="sub">Sileo / Cydia 自建源</p>
<div class="box">在 Sileo 添加源：<br><code>{BASE_URL}</code></div>
<table>
<thead><tr><th>名称</th><th>包名</th><th>版本</th><th>说明</th></tr></thead>
<tbody>
{table}
</tbody>
</table>
</main>
</body>
</html>
"""
    (ROOT / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    DEB_DIR.mkdir(exist_ok=True)
    packages = build_packages()
    files = write_compressed(packages.encode("utf-8"))
    write_release(files)
    write_index(packages)
    n = len([p for p in packages.split("\n\n") if p.strip()])
    print(f"built {n} package(s) -> {ROOT}")
    print(f"Sileo URL: {BASE_URL}")


if __name__ == "__main__":
    main()
