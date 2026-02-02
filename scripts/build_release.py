import argparse
import os
import shutil
import zipfile
from pathlib import Path


def copy_tree(src: Path, dest: Path):
    if not src.exists():
        return
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_bundle(root: Path, out_dir: Path, name: str):
    bundle_dir = out_dir / name
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Core files
    copy_tree(root / "bin", bundle_dir / "bin")
    copy_tree(root / "config", bundle_dir / "config")
    copy_tree(root / "data", bundle_dir / "data")
    copy_tree(root / "docs", bundle_dir / "docs")
    copy_tree(root / "src", bundle_dir / "src")
    copy_tree(root / "ui", bundle_dir / "ui")
    copy_tree(root / "snapshots", bundle_dir / "snapshots")
    copy_tree(root / "exports", bundle_dir / "exports")

    # Top-level metadata
    for fname in ["README.md", "requirements.txt", "pyproject.toml", "CONTRIBUTING.md"]:
        copy_tree(root / fname, bundle_dir / fname)

    copy_tree(root / "bin" / "demo_launcher.bat", bundle_dir / "bin" / "demo_launcher.bat")
    copy_tree(root / "bin" / "demo_launcher.sh", bundle_dir / "bin" / "demo_launcher.sh")

    return bundle_dir


def zip_bundle(bundle_dir: Path, out_zip: Path):
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in bundle_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(bundle_dir))


def main():
    parser = argparse.ArgumentParser(description="Build a release bundle for lab transfer.")
    parser.add_argument("--name", default="hil_verifier_bundle", help="Bundle folder name")
    parser.add_argument("--out", default="dist", help="Output directory")
    parser.add_argument("--zip", action="store_true", help="Create a zip archive")
    parser.add_argument("--pyinstaller", action="store_true", help="Placeholder flag for exe build")

    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_dir = build_bundle(root, out_dir, args.name)

    if args.zip:
        zip_bundle(bundle_dir, out_dir / f"{args.name}.zip")

    if args.pyinstaller:
        print("PyInstaller build is not implemented in this script. Use a separate pipeline if needed.")

    print(f"Bundle created at: {bundle_dir}")


if __name__ == "__main__":
    main()
