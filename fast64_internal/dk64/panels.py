from bpy.path import abspath
from bpy.types import Context

from ..panels import DK64_Panel
from ..utility import prop_split, filepath_ui_warnings
from .actor.operators import DK64_ExportActor
from .importer.operators import DK64_ImportRomModel
from .prop.operators import DK64_ExportProp
from .rom.catalog import ACTOR, PROP, STAGE, TABLE_LABELS


class DK64_GeneralSettingsPanel(DK64_Panel):
    bl_idname = "DK64_PT_general_settings"
    bl_label = "DK64 General Settings"
    bl_options = set()  # default to open
    bl_order = 0

    # called every frame
    def draw(self, context: Context):
        col = self.layout.column()
        dk64_props = context.scene.fast64.dk64

        prop_split(col, dk64_props, "scale", "Blender To DK64 Scale")
        prop_split(col, dk64_props, "import_rom", "Import ROM")
        filepath_ui_warnings(col, abspath(dk64_props.import_rom))
        if dk64_props.rom_catalog.error:
            col.box().label(text=f"Cannot read the ROM: {dk64_props.rom_catalog.error}", icon="ERROR")


class DK64_CombinedImporterPanel(DK64_Panel):
    bl_idname = "DK64_PT_combined_importer"
    bl_label = "DK64 Combined Importer"
    bl_order = 1

    # called every frame
    def draw(self, context: Context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        dk64_props = context.scene.fast64.dk64

        if not dk64_props.rom_catalog.loaded_rom:
            col.box().label(text="Set Import ROM in DK64 General Settings.", icon="INFO")
            return

        for table in (ACTOR, PROP, STAGE):
            box = col.box().column()
            label = TABLE_LABELS[table]
            box.label(text=f"Import {label}")
            dk64_props.rom_catalog.draw_search(box, dk64_props.import_settings, f"{table}_name", table, label)
            DK64_ImportRomModel.draw_props(box, text=f"Import {label}", table=table)


class DK64_CombinedExporterPanel(DK64_Panel):
    bl_idname = "DK64_PT_combined_exporter"
    bl_label = "DK64 Combined Exporter"
    bl_order = 2

    # called every frame
    def draw(self, context: Context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding
        dk64_props = context.scene.fast64.dk64

        obj = context.object
        if obj is None or obj.type != "MESH":
            col.box().label(text="Select the mesh to export.", icon="ERROR")
        else:
            col.label(text=f"Mesh: {obj.name}", icon="MESH_DATA")

        box = col.box().column()
        box.label(text="Export Actor")
        dk64_props.actor_export_settings.draw_props(box)
        DK64_ExportActor.draw_props(box)

        box = col.box().column()
        box.label(text="Export Prop")
        dk64_props.prop_export_settings.draw_props(box)
        DK64_ExportProp.draw_props(box)
