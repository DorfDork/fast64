from bpy.props import EnumProperty, FloatProperty, IntProperty
from bpy.types import Bone, Context, Panel, PropertyGroup, UILayout

from ..utility import prop_split
from .dk64_constants import (
    DK64_ANIMATED_PREFIX,
    DK64_FIRST_SWITCH_SEGMENT,
    DK64_LAST_SWITCH_SEGMENT,
    DK64_SWITCH_PREFIX,
)

enum_bone_type = [
    ("Animated", "Animated", "Bones which hold the verticies of the mesh."),
    ("Scale", "Scale", "Shrinks the vertices of every animated bone."),
    ("Switch", "Switch", "An optional mesh part which the game uses to switch over to."),
]


def get_animated_name(index: int) -> str:
    return f"{DK64_ANIMATED_PREFIX}{index:02d}"


def get_animated_index(name: str) -> int | None:
    suffix = name[len(DK64_ANIMATED_PREFIX) :]
    if not name.startswith(DK64_ANIMATED_PREFIX) or not suffix.isdigit():
        return None
    return int(suffix)


def get_switch_name(segment: int) -> str:
    return f"{DK64_SWITCH_PREFIX}{segment - DK64_FIRST_SWITCH_SEGMENT + 1}"


class DK64_BoneProperties(PropertyGroup):
    """Properties in bone.fast64.dk64"""

    bone_type: EnumProperty(name="Bone Type", items=enum_bone_type, default="Animated")
    scale: FloatProperty(
        name="Scale",
        description=(
            "Scales the vertices of every animated bone."
        ),
        min=2 ** (-16),
        max=2**15 - 1,
        default=1,
    )
    channel: IntProperty(name="Animation Channel", min=0, max=0xFF)
    segment: IntProperty(
        name="Segment",
        description="The segment the game shows or hides this part with.",
        min=DK64_FIRST_SWITCH_SEGMENT,
        max=DK64_LAST_SWITCH_SEGMENT,
        default=DK64_FIRST_SWITCH_SEGMENT,
    )

    def draw_props(self, layout: UILayout, name: str):
        prop_split(layout, self, "bone_type", "Bone Type")
        if self.bone_type == "Switch":
            prop_split(layout, self, "segment", "Segment")
            info = layout.box().column()
            info.label(text=f"Drawn while bit {self.segment - DK64_FIRST_SWITCH_SEGMENT} of the hand state is set.")
            info.label(text=f'The "{name}" vertex group holds the part.')
        elif self.bone_type == "Scale":
            prop_split(layout, self, "scale", "Scale")
            info = layout.box().column()
            info.label(text="Scales the vertices of every animated bone under it.")
            if self.scale != 1:
                info.label(text=f"Blender To DK64 Scale x{1 / self.scale:g} keeps the model's size.")
        else:
            layout.label(text=f"Animation channel {self.channel}")


def get_bone_scale(bone: Bone) -> float:
    scale = 1.0
    while bone is not None:
        props = bone.fast64.dk64
        if props.bone_type == "Scale":
            scale *= props.scale
        bone = bone.parent
    return scale


class DK64_BonePanel(Panel):
    bl_label = "DK64 Bone Inspector"
    bl_idname = "BONE_PT_DK64_Bone_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.gameEditorMode == "DK64"

    def draw(self, context: Context):
        col = self.layout.column().box()
        col.box().label(text="DK64 Bone Inspector")
        bone = context.bone
        if bone is None:
            col.label(text="Edit DK64 bone properties in Pose mode.")
            return
        bone.fast64.dk64.draw_props(col, bone.name)
