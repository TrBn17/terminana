"""Generate tool JSON metadata from @tool-decorated core modules."""

from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from terminana.tools.decorator import get_registry  # noqa: E402

_PACKAGE_NAME = "terminana.core"
_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "core"
_TOOLS_JSON_DIR = Path(__file__).resolve().parent / "json"


def _discover_modules() -> list[str]:
    """Return importable modules under terminana.core."""
    return [
        modname
        for _, modname, ispkg in pkgutil.walk_packages(
            path=[str(_PACKAGE_DIR)],
            prefix=f"{_PACKAGE_NAME}.",
        )
        if not ispkg
    ]


def _import_all_modules(modules: list[str], *, verbose: bool = False) -> None:
    """Import all candidate modules so @tool decorators register definitions."""
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            if verbose:
                print(f"  [OK] {mod_name}")
        except Exception as exc:
            if verbose:
                print(f"  [SKIP] {mod_name}: {exc}")


def generate(*, dry_run: bool = False, verbose: bool = False) -> list[dict]:
    """Generate tool definition JSON files from the current registry."""
    if verbose:
        print("Scanning terminana.core for @tool functions...")

    modules = _discover_modules()
    _import_all_modules(modules, verbose=verbose)
    registry = get_registry()

    if not registry:
        print("No tools found. Make sure functions are decorated with @tool.")
        return []

    tools_list = [definition for _, definition in sorted(registry.items())]

    if not dry_run:
        _TOOLS_JSON_DIR.mkdir(parents=True, exist_ok=True)
        for definition in tools_list:
            path = _TOOLS_JSON_DIR / f"{definition['name']}.json"
            path.write_text(
                json.dumps(definition, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if verbose:
                print(f"  -> {path.relative_to(_PROJECT_ROOT)}")

        master_path = _TOOLS_JSON_DIR / "tools.json"
        master_path.write_text(
            json.dumps(tools_list, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if verbose:
            print(f"  -> {master_path.relative_to(_PROJECT_ROOT)}")

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Generated {len(tools_list)} tool(s):")
    for definition in tools_list:
        params = list(definition.get("parameters", {}).get("properties", {}).keys())
        required = definition.get("parameters", {}).get("required", [])
        print(f"  - {definition['name']}({', '.join(params)})")
        print(f"    module:   {definition['module']}")
        print(f"    required: {required}")

    return tools_list


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate tool JSON metadata from @tool-decorated functions."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered tools without writing files.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed import and file output.",
    )
    args = parser.parse_args()
    generate(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
