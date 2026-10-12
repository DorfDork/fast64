from bpy.props import StringProperty
from bpy.types import Context

from ...operators import OperatorBase
from ...utility import PluginError
from ..rom import catalog, textures
from .importer import import_model


class DK64_ImportRomModel(OperatorBase):
    bl_idname = "scene.fast64_dk64_import_rom_model"
    bl_label = "Import"
    bl_description = "Import the named model"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "IMPORT"

    table: StringProperty(name="Table", default=catalog.ACTOR)

    def execute_operator(self, context: Context):
        dk64_props = context.scene.fast64.dk64
        rom_catalog = dk64_props.rom_catalog
        rom_path = rom_catalog.require_loaded()

        label = catalog.TABLE_LABELS[self.table]
        search_text = getattr(dk64_props.import_settings, f"{self.table}_name")
        entry = rom_catalog.find(self.table, search_text)
        if entry is None:
            raise PluginError(
                f'No {label.lower()} called "{search_text}".' if search_text else f"Name a {label.lower()}."
            )

        model = catalog.read_model(rom_path, self.table, entry.index)
        name = f"{self.table}_{catalog.get_folder_name(entry.index, model.name)}"
        texture_folder = textures.get_texture_folder(rom_path, self.table, entry.index, model.name)
        _, groups = import_model(context, model, name, dk64_props.scale, texture_folder)
        triangles = sum(len(group.triangles) for group in groups)
        skeleton = f"{len(model.bones)} bones, " if model.bones else ""
        self.report({"INFO"}, f"Imported {name}: {skeleton}{triangles} triangles.")
