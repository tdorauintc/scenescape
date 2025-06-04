import argparse
import subprocess
import shutil
import tempfile
import os
from pathlib import Path
import sys

def check_git_clean():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        print("Error: Not a git repository or git is not installed.", file=sys.stderr)
        sys.exit(1)
    if result.stdout.strip():
        print("Error: Git working directory is not clean. Please commit or stash your changes before running this script.", file=sys.stderr)
        sys.exit(1)

def run_build(build_cmd):
    try:
        result = subprocess.run(build_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception:
        return False

def prune_file(req_file, build_cmd):
    req_path = Path(req_file)
    with req_path.open() as f:
        lines = f.readlines()

    needed_lines = []
    removed_lines = []
    unchecked_lines = lines.copy()

    idx = 0
    while len(unchecked_lines) > 0:
        line = unchecked_lines[0]
        stripped = line.strip()
        idx += 1
        if not stripped or stripped.startswith("#"):
            continue

        # Try removing this line
        test_lines = needed_lines + unchecked_lines[1:]
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.writelines(test_lines)
            tmp_path = tmp.name

        shutil.copy(tmp_path, req_file)
        os.unlink(tmp_path)

        if run_build(build_cmd):
            removed_lines.append((idx, line.rstrip()))
        else:
            needed_lines.append(line)

        unchecked_lines.pop(0)

    # At the end, write the pruned file
    with req_path.open("w") as f:
        f.writelines(needed_lines)

    return removed_lines

def main():
    check_git_clean()  # <--- Added check here

    parser = argparse.ArgumentParser(description="Prune unused requirements.")
    parser.add_argument("build_command", help="Build command to test requirements")
    parser.add_argument("requirements", nargs="+", help="Requirement files to prune")
    args = parser.parse_args()

    all_removed = {}
    for req_file in args.requirements:
        print(f"Processing {req_file}...")
        removed = prune_file(req_file, args.build_command)
        if removed:
            all_removed[req_file] = removed

    if all_removed:
        print("\nRemoved dependencies:")
        for req_file, deps in all_removed.items():
            print(f"{req_file}:")
            for idx, dep in deps:
                print(f"  Line {idx+1}: {dep}")

        # Commit changes
        files = " ".join(all_removed.keys())
        subprocess.run(f"git add {files}", shell=True)
        subprocess.run(f"git commit -m 'Prune unused dependencies from requirements files'", shell=True)
        print("\nChanges committed to git.")
    else:
        print("No dependencies could be removed.")

if __name__ == "__main__":
    main()
