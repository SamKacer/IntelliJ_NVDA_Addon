#!/usr/bin/env python3
"""Build script for the JetBrains NVDA Addon.

Produces JetBrains-<version>.nvda-addon in the project root.
An .nvda-addon file is a ZIP archive containing manifest.ini and the addon tree.
"""

import codecs
import os
import sys
import zipfile

sys.dont_write_bytecode = True
import buildVars  # noqa: E402


def generate_manifest(template_path: str, dest_path: str) -> None:
    info = dict(buildVars.addon_info)
    # NVDA manifest expects the literal string "None" for missing url
    if info.get("addon_url") is None:
        info["addon_url"] = "None"
    with codecs.open(template_path, "r", "utf-8") as f:
        template = f.read()
    manifest = template.format(**info)
    with codecs.open(dest_path, "w", "utf-8") as f:
        f.write(manifest)


def create_addon_bundle(addon_dir: str, dest_path: str) -> None:
    basedir = os.path.abspath(addon_dir)
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirnames, filenames in os.walk(basedir):
            rel = os.path.relpath(dirpath, basedir)
            for filename in filenames:
                arcname = os.path.join(rel, filename)
                fullpath = os.path.join(dirpath, filename)
                z.write(fullpath, arcname)
    print(f"Created: {dest_path}")


def main() -> None:
    info = buildVars.addon_info
    manifest_dest = os.path.join("addon", "manifest.ini")
    generate_manifest("manifest.ini.tpl", manifest_dest)
    print(f"Generated: {manifest_dest}")

    addon_file = f"{info['addon_name']}-{info['addon_version']}.nvda-addon"
    create_addon_bundle("addon", addon_file)


if __name__ == "__main__":
    main()
