"""Run all local provider gates; never install, publish, or launch a client."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("Running: " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    lua, luac = shutil.which("lua5.1"), shutil.which("luac5.1")
    if not lua or not luac:
        raise SystemExit("Lua 5.1 lua5.1 and luac5.1 are required; no automatic install")
    for tool in (lua, luac):
        version = subprocess.run([tool, "-v"], capture_output=True, check=True)
        if b"Lua 5.1" not in version.stdout + version.stderr:
            raise SystemExit("The Lua tools must use the 5.1 language")
    run([sys.executable, "tools/generate.py", "--check"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    for path in sorted((ROOT / "tests").glob("test_*.lua")):
        run([lua, str(path.relative_to(ROOT))])
    for path in sorted(ROOT.rglob("*.lua")):
        if not any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            run([luac, "-p", str(path.relative_to(ROOT))])
    print("All local provider gates passed; native acceptance remains separate.")


if __name__ == "__main__":
    main()
