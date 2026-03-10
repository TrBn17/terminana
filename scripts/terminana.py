"""scripts/terminana.py — dev shortcut, goi ai_skills.cli."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terminana.cli import cli

if __name__ == "__main__":
    cli()

