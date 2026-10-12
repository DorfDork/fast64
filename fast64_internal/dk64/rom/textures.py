from __future__ import annotations

from pathlib import Path

from ..contrib import install_contrib_path
from .catalog import ACTOR, PROP, STAGE, TABLES, get_folder_name, open_rom, read_table

install_contrib_path()

from dk64_lib.f3dex2.texture_export import TexturedObjExporter  # noqa: E402  vendored

TEXTURE_FOLDER = "textures"

TABLE_FOLDERS = {ACTOR: "actors", PROP: "props", STAGE: "stages"}


def get_assets_root(rom_path: str | Path) -> Path:
    rom = Path(rom_path)
    return rom.parent / f"{rom.stem}_assets"


def get_texture_folder(rom_path: str | Path, table: str, index: int, name: str) -> Path:
    return get_assets_root(rom_path) / TABLE_FOLDERS[table] / get_folder_name(index, name) / TEXTURE_FOLDER


def write_textures(rom_path: str | Path) -> dict:
    rom = open_rom(rom_path)
    exporter = TexturedObjExporter(rom.get_geometry_texture_data(), rom.get_animated_texture_data())
    written, skipped, failed = 0, 0, 0

    for table in TABLES:
        for model in read_table(rom_path, table):
            folder = get_texture_folder(rom_path, table, model.index, model.name)
            if folder.exists():
                skipped += 1
                continue
            try:
                images = exporter.export_texture_images(model.mesh_groups, texture_folder="")
            except ValueError:
                failed += 1
                continue
            if not images:
                failed += 1
                continue
            folder.mkdir(parents=True, exist_ok=True)
            for image in images:
                (folder / image.filename).write_bytes(image.data)
            written += 1

    return {"written": written, "skipped": skipped, "failed": failed}
