#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
from pathlib import Path


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_index(dist_dir: Path, output_dir: Path, package_name: str) -> None:
    package_dir = output_dir / "packages"
    simple_root = output_dir / "simple"
    normalized_name = normalize_package_name(package_name)
    project_dir = simple_root / normalized_name

    if output_dir.exists():
        shutil.rmtree(output_dir)

    package_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)

    artifacts = sorted(path for path in dist_dir.iterdir() if path.is_file())
    if not artifacts:
        raise SystemExit(f"Keine Paketartefakte in {dist_dir}")

    links: list[str] = []
    for artifact in artifacts:
        target = package_dir / artifact.name
        shutil.copy2(artifact, target)
        checksum = sha256sum(target)
        links.append(
            f'<a href="../../packages/{html.escape(target.name)}#sha256={checksum}">{html.escape(target.name)}</a>'
        )

    (output_dir / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><body>",
                f"<h1>{html.escape(package_name)} Registry</h1>",
                f'<p><a href="simple/{html.escape(normalized_name)}/">{html.escape(package_name)}</a></p>',
                "</body></html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (simple_root / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><body>",
                f'<a href="{html.escape(normalized_name)}/">{html.escape(package_name)}</a>',
                "</body></html>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / "index.html").write_text(
        "\n".join(["<!doctype html>", "<html><body>", *links, "</body></html>"]) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static PEP 503 simple index.")
    parser.add_argument("--dist-dir", default="dist/python-package", help="Directory with wheel and sdist artifacts")
    parser.add_argument("--output-dir", default="dist/pages", help="Output directory for static registry files")
    parser.add_argument("--package-name", default="aidrax-prompt-matrix", help="Published package name")
    args = parser.parse_args()

    build_index(Path(args.dist_dir).resolve(), Path(args.output_dir).resolve(), args.package_name)


if __name__ == "__main__":
    main()
