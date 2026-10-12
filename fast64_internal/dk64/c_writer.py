from dataclasses import dataclass
from pathlib import Path

from ..utility import writeFile


@dataclass(frozen=True)
class ExportResult:
    model_folder: Path
    vertices: int
    triangles: int
    textures: int
    bones: int = 0


def get_symbol(table: str, index: int) -> str:
    return f"{table}_{index:04X}"


def write_c_files(
    model_folder: Path,
    table: str,
    index: int,
    name: str,
    defines: list[tuple[str, str]],
    asset: list[str],
    externs: str,
) -> None:
    guard = f"{get_symbol(table, index).upper()}_HEADER_H"
    description = f"{name}, Donkey Kong 64 {table} {index:04X}."
    width = max(len(define) for define, _ in defines)
    header = [f"#ifndef {guard}", f"#define {guard}", "", '#include "ultra64.h"', "", f"/* {description} */", ""]
    header += [f"#define {define:<{width}} {value}" for define, value in defines]
    header += ["", externs.rstrip("\n"), "", f"#endif /* {guard} */", ""]
    writeFile(str(model_folder / "header.h"), "\n".join(header))

    source = [
        f"// {description} Exported from Blender by fast64.",
        "",
        '#include "ultra64.h"',
        '#include "custom_asset.h"',
        '#include "header.h"',
        '#include "model.inc.c"',
        "",
    ]
    writeFile(str(model_folder / f"{index:04X}.c"), "\n".join(source + asset))
