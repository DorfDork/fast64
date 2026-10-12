from bpy.types import Context

from ...operators import OperatorBase
from ..mesh import get_export_mesh
from ..rom import catalog
from .exporter import export_prop


class DK64_ExportProp(OperatorBase):
    bl_idname = "object.fast64_dk64_export_prop"
    bl_label = "Export Prop"
    bl_description = (
        "Write the selected mesh as a prop."
    )
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "EXPORT"

    def execute_operator(self, context: Context):
        dk64_props = context.scene.fast64.dk64
        settings = dk64_props.prop_export_settings
        obj = get_export_mesh(context)
        folder = settings.get_folder()
        index = dk64_props.rom_catalog.require_index(catalog.PROP, settings.name)

        prop = catalog.read_model(dk64_props.rom_catalog.loaded_rom, catalog.PROP, index)
        result = export_prop(obj, dk64_props.scale, context.scene.saveTextures, index, prop.name, folder)
        self.report(
            {"INFO"},
            f"Exported {result.vertices} vertices, {result.triangles} triangles and {result.textures} "
            f"textures to {result.model_folder.name}/.",
        )
