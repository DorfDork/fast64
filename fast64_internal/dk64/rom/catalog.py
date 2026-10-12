from __future__ import annotations

from pathlib import Path

from ..contrib import install_contrib_path

install_contrib_path()

from dk64_lib.rom import Rom  # noqa: E402  vendored, needs the path above

ACTOR = "actor"
PROP = "prop"
STAGE = "stage"
TABLES = (ACTOR, PROP, STAGE)

TABLE_LABELS = {ACTOR: "Actor", PROP: "Prop", STAGE: "Stage"}

_roms: dict[Path, Rom] = {}


def open_rom(rom_path: str | Path) -> Rom:
    path = Path(rom_path).resolve()
    if path not in _roms:
        _roms[path] = Rom(str(path))
    return _roms[path]


def close_roms() -> None:
    _roms.clear()


def read_table(rom_path: str | Path, table: str) -> list:
    rom = open_rom(rom_path)
    if table == ACTOR:
        return rom.actor_geometry_tables
    if table == PROP:
        return rom.prop_geometry_tables
    if table == STAGE:
        return rom.stage_geometry_tables
    raise ValueError(f"Unknown table {table!r}")


def read_model(rom_path: str | Path, table: str, index: int):
    for model in read_table(rom_path, table):
        if model.index == index:
            return model
    raise ValueError(f"No {table} {index:04X} in the ROM")


def get_folder_name(index: int, name: str) -> str:
    safe_name = "".join(character if character.isalnum() else "_" for character in name)
    while "__" in safe_name:
        safe_name = safe_name.replace("__", "_")
    return f"{index:04X}_{safe_name}".strip("_")
