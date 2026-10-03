#!/usr/bin/env python3
"""Pack packages/<name>/ into debs/<pkg>_<ver>_<arch>.deb"""
from __future__ import annotations

import hashlib
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG_ROOT = ROOT / "srcpkgs"
DEB_DIR = ROOT / "debs"


def parse_control(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    key = None
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith((" ", "\t")) and key:
            fields[key] += "\n" + line.strip()
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            fields[key] = val.strip()
    return fields


def tar_gz(files: list[tuple[str, bytes, int]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        for name, data, mode in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "wheel"
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def ar_write(members: list[tuple[str, bytes]]) -> bytes:
    out = io.BytesIO()
    out.write(b"!<arch>\n")
    for name, data in members:
        hdr = f"{name:<16}{int(time.time()):<12}{0:<6}{0:<6}{0o100644:<8}{len(data):<10}`\n"
        out.write(hdr.encode("ascii"))
        out.write(data)
        if len(data) % 2:
            out.write(b"\n")
    return out.getvalue()


def collect_data(data_dir: Path) -> list[tuple[str, bytes, int]]:
    items: list[tuple[str, bytes, int]] = []
    if not data_dir.exists():
        return items
    for path in sorted(data_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(data_dir).as_posix()
        name = "./" + rel
        mode = path.stat().st_mode & 0o777
        items.append((name, path.read_bytes(), mode))
    return items


def pack_one(pkg_dir: Path) -> Path:
    control_path = pkg_dir / "DEBIAN" / "control"
    if not control_path.exists():
        raise SystemExit(f"missing {control_path}")
    control_text = control_path.read_text(encoding="utf-8")
    if not control_text.endswith("\n"):
        control_text += "\n"
    fields = parse_control(control_text)
    for req in ("Package", "Version", "Architecture"):
        if req not in fields:
            raise SystemExit(f"{pkg_dir}: control missing {req}")

    data_files = collect_data(pkg_dir / "data")
    md5_lines = []
    for name, blob, _mode in data_files:
        rel = name[2:] if name.startswith("./") else name
        md5_lines.append(f"{hashlib.md5(blob).hexdigest()}  {rel}")
    md5sums = ("\n".join(md5_lines) + "\n").encode() if md5_lines else b""

    control_members = [("./control", control_text.encode(), 0o644)]
    if md5sums:
        control_members.append(("./md5sums", md5sums, 0o644))
    for extra in ("preinst", "postinst", "prerm", "postrm", "extrainst_"):
        p = pkg_dir / "DEBIAN" / extra
        if p.exists():
            control_members.append(("./" + extra, p.read_bytes(), 0o755))

    control_tar = tar_gz(control_members)
    data_tar = tar_gz(data_files or [("./", b"", 0o755)])
    deb = ar_write(
        [
            ("debian-binary", b"2.0\n"),
            ("control.tar.gz", control_tar),
            ("data.tar.gz", data_tar),
        ]
    )
    DEB_DIR.mkdir(exist_ok=True)
    out = DEB_DIR / f"{fields['Package']}_{fields['Version']}_{fields['Architecture']}.deb"
    out.write_bytes(deb)
    print(f"wrote {out} ({len(deb)} bytes)")
    return out


def main() -> None:
    if not PKG_ROOT.exists():
        raise SystemExit("srcpkgs/ not found")
    dirs = [p for p in sorted(PKG_ROOT.iterdir()) if p.is_dir()]
    if not dirs:
        raise SystemExit("no package dirs under srcpkgs/")
    for d in dirs:
        pack_one(d)


if __name__ == "__main__":
    main()
