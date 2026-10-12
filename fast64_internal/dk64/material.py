from bpy.props import BoolProperty
from bpy.types import Context, Panel, PropertyGroup

from .dk64_constants import DK64_HILITE_SEGMENT


class DK64_MaterialProperties(PropertyGroup):
    """Properties in material.dk64"""

    hilite: BoolProperty(
        name="Highlight",
        description=(
            f"Call the highlight display list, segment {DK64_HILITE_SEGMENT}."
            "Creates the shine on environment-mapped materials."
        ),
    )


class DK64_MaterialPanel(Panel):
    bl_label = "DK64 Material"
    bl_idname = "MATERIAL_PT_DK64_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context: Context):
        return context.material is not None and context.material.is_f3d and context.scene.gameEditorMode == "DK64"

    def draw(self, context: Context):
        col = self.layout.column().box()
        col.box().label(text="DK64 Material Inspector")
        col.prop(context.material.dk64, "hilite")
