"""
Windows autostart installer — Phase 10.

Installs / uninstalls Alice as a Windows Task Scheduler task that runs
on user logon in UI mode.

Usage:
  py -3.14 scripts/autostart.py install    # add to Task Scheduler
  py -3.14 scripts/autostart.py uninstall  # remove from Task Scheduler
  py -3.14 scripts/autostart.py status     # check if installed
"""

import subprocess
import sys
from pathlib import Path

TASK_NAME = "AliceAI"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
MAIN_PY = PROJECT_ROOT / "alice" / "main.py"
PYTHON = sys.executable  # current interpreter


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def install() -> None:
    command = f'"{PYTHON}" "{MAIN_PY}" --ui'

    result = _run([
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", command,
        "/sc", "ONLOGON",
        "/rl", "LIMITED",       # run with standard privileges (no admin needed)
        "/f",                    # force overwrite if exists
        "/delay", "0000:30",    # 30s delay after logon so desktop is ready
    ], check=False)

    if result.returncode == 0:
        print(f"[OK] Alice will start automatically at logon.")
        print(f"     Task: {TASK_NAME}")
        print(f"     Command: {command}")
    else:
        print(f"[FAIL] Could not install autostart:")
        print(result.stderr or result.stdout)
        print("\nYou may need to run this script as Administrator.")


def uninstall() -> None:
    result = _run([
        "schtasks", "/delete", "/tn", TASK_NAME, "/f",
    ], check=False)

    if result.returncode == 0:
        print(f"[OK] Autostart removed (task '{TASK_NAME}' deleted).")
    else:
        if "cannot find" in (result.stderr or "").lower():
            print(f"[INFO] Task '{TASK_NAME}' not found — nothing to remove.")
        else:
            print(f"[FAIL] Could not remove task:")
            print(result.stderr or result.stdout)


def status() -> None:
    result = _run([
        "schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST",
    ], check=False)

    if result.returncode == 0:
        print(f"[OK] Alice autostart is INSTALLED.")
        # Print relevant lines
        for line in result.stdout.splitlines():
            if any(k in line for k in ("Task Name", "Status", "Run As", "Task To Run")):
                print(f"     {line.strip()}")
    else:
        print(f"[INFO] Alice autostart is NOT installed.")
        print(f"       Run: py -3.14 scripts/autostart.py install")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("install", "uninstall", "status"):
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    elif action == "status":
        status()


if __name__ == "__main__":
    main()
