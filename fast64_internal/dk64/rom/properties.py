from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup, UILayout

from ...utility import PluginError
from .catalog import TABLE_LABELS, TABLES, read_table
from .textures import get_assets_root, write_textures

HEX_DIGITS = "0123456789abcdefABCDEF"


class DK64RomEntry(PropertyGroup):
    index: IntProperty(name="Index")


class DK64RomCatalog(PropertyGroup):
    actor_entries: CollectionProperty(type=DK64RomEntry)
    prop_entries: CollectionProperty(type=DK64RomEntry)
    stage_entries: CollectionProperty(type=DK64RomEntry)
    loaded_rom: StringProperty(name="Loaded ROM")
    error: StringProperty(name="Error")

    def entries(self, table: str):
        return getattr(self, f"{table}_entries")

    def load(self, path: str):
        for table in TABLES:
            self.entries(table).clear()
        self.loaded_rom, self.error = "", ""
        if not path:
            return
        try:
            for table in TABLES:
                entries = self.entries(table)
                for model in read_table(path, table):
                    entry = entries.add()
                    entry.name = f"{model.index:04X}  {model.name}"
                    entry.index = model.index
        except Exception as exception:
            for table in TABLES:
                self.entries(table).clear()
            self.error = str(exception) or type(exception).__name__
            return
        self.loaded_rom = path

        print(f"Fast64: unpacking DK64 textures into {get_assets_root(path)}")
        try:
            counts = write_textures(path)
        except Exception as exception:
            self.error = f"Textures were not written: {str(exception) or type(exception).__name__}"
            return
        print(
            f"Fast64: unpacked textures for {counts['written']} models. Skipped {counts['skipped']} "
            f"that were already unpacked and {counts['failed']} with no readable textures."
        )

    def find(self, table: str, text: str):
        text = text.strip().lower()
        if not text:
            return None
        entries = self.entries(table)
        for entry in entries:
            if text == entry.name.lower():
                return entry
        for entry in entries:
            if text == entry.name.split("  ", 1)[-1].lower():
                return entry
        try:
            index = int(text, 16)
        except ValueError:
            return None
        for entry in entries:
            if entry.index == index:
                return entry
        return None

    def require_loaded(self) -> str:
        if not self.loaded_rom:
            raise PluginError("Set Import ROM first.")
        return self.loaded_rom

    def require_index(self, table: str, text: str) -> int:
        label = TABLE_LABELS[table].lower()
        self.require_loaded()

        name = text.strip()
        if not name:
            raise PluginError(f"Name the {label} this model replaces in the four hex digit format.")
        if len(name) != 4 or any(character not in HEX_DIGITS for character in name):
            raise PluginError(
                f'"{name}" is not a model number. Name the {label} this model replaces in '
                "the four hex digit format."
            )

        index = int(name, 16)
        if not any(entry.index == index for entry in self.entries(table)):
            raise PluginError(f"The ROM has no {label} {index:04X}.")
        return index

    def draw_search(self, layout: UILayout, data, field: str, table: str, label: str):
        split = layout.split(factor=0.5)
        split.label(text=label)
        row = split.row()
        row.alert = bool(getattr(data, field).strip()) and self.find(table, getattr(data, field)) is None
        row.prop(data, field, text="", icon="VIEWZOOM")
