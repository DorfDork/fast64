import sys

from pathlib import Path

CONTRIB_ROOT = Path(__file__).resolve().parent
DK64_LIB_SRC = CONTRIB_ROOT / "dk64_lib_kongvoluted" / "src"


def install_contrib_path() -> None:
    root = str(DK64_LIB_SRC)
    if root not in sys.path:
        sys.path.append(root)
