"""
python -m ai_skills.tools.generate
───────────────────────────────────
Quét tất cả module trong ``ai_skills/src/`` → tìm function có ``@tool`` →
tự động sinh JSON vào ``ai_skills/tools/``.

Chạy:
    python -m ai_skills.tools.generate           # sinh JSON
    python -m ai_skills.tools.generate --dry-run  # chỉ in, không ghi file
    python -m ai_skills.tools.generate --verbose   # hiện chi tiết

Kết quả:
    ai_skills/tools/
    ├── tools.json                 ← master list (auto-generated)
    ├── run_command.json           ← từng tool riêng
    └── spawn_and_interact.json
"""

from __future__ import annotations

import json
import importlib
import pkgutil
import argparse
import sys
from pathlib import Path

# Đảm bảo project root trong sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from terminana.tools.decorator import get_registry  # noqa: E402

_TOOLS_DIR = Path(__file__).resolve().parent
_SRC_DIR   = _TOOLS_DIR.parent / "src"


def _discover_modules():
    """Tìm tất cả Python module trong ai_skills/src/."""
    package_name = "ai_skills.src"
    package_path = str(_SRC_DIR)

    modules = []
    for importer, modname, ispkg in pkgutil.walk_packages(
        path=[package_path], prefix=f"{package_name}."
    ):
        modules.append(modname)
    return modules


def _import_all_modules(modules: list[str], verbose: bool = False):
    """Import toàn bộ module → trigger @tool decorator registration."""
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            if verbose:
                print(f"  [OK] {mod_name}")
        except Exception as e:
            if verbose:
                print(f"  [SKIP] {mod_name}: {e}")


def generate(dry_run: bool = False, verbose: bool = False) -> list[dict]:
    """
    Quét modules → lấy registry → sinh JSON.

    Returns: list of tool definitions đã sinh.
    """
    if verbose:
        print("Scanning ai_skills/src/ for @tool functions...")

    # 1. Discover & import → decorator đăng ký vào registry
    modules = _discover_modules()
    _import_all_modules(modules, verbose=verbose)

    # 2. Lấy registry
    registry = get_registry()

    if not registry:
        print("No tools found! Make sure functions are decorated with @tool.")
        return []

    if verbose:
        print(f"\nFound {len(registry)} tool(s): {list(registry.keys())}")

    # 3. Sinh JSON
    tools_list: list[dict] = []

    for name, defn in sorted(registry.items()):
        tools_list.append(defn)

        if not dry_run:
            # File riêng: tools/run_command.json
            individual_path = _TOOLS_DIR / f"{name}.json"
            individual_path.write_text(
                json.dumps(defn, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if verbose:
                print(f"  → {individual_path.relative_to(_PROJECT_ROOT)}")

    if not dry_run:
        # Master list: tools/tools.json
        master_path = _TOOLS_DIR / "tools.json"
        master_path.write_text(
            json.dumps(tools_list, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if verbose:
            print(f"  → {master_path.relative_to(_PROJECT_ROOT)}")

    # 4. Summary
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Generated {len(tools_list)} tool(s):")
    for t in tools_list:
        params = list(t.get("parameters", {}).get("properties", {}).keys())
        required = t.get("parameters", {}).get("required", [])
        print(f"  • {t['name']}({', '.join(params)})")
        print(f"    module:   {t['module']}")
        print(f"    required: {required}")

    return tools_list


def main():
    parser = argparse.ArgumentParser(
        description="Auto-generate tool JSON from @tool decorated functions."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print tools without writing files.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output.")
    args = parser.parse_args()
    generate(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
