import bpy
from bpy.types import Context

from ...operators import OperatorBase
from ...utility import PluginError
from ..bone import get_animated_index, get_bone_scale
from ..dk64_constants import DK64_ANIMATED_PREFIX
from ..f3dex2 import get_transform
from ..mesh import DK64VertexWeightError, get_export_mesh, get_vertex_bones, get_vertex_optional
from ..rom import catalog
from .exporter import export_actor


def select_vertices(obj: bpy.types.Object, indices: list[int]):
    mesh: bpy.types.Mesh = obj.data
    mesh.polygons.foreach_set("select", [False] * len(mesh.polygons))
    mesh.edges.foreach_set("select", [False] * len(mesh.edges))
    selected = set(indices)
    mesh.vertices.foreach_set("select", [index in selected for index in range(len(mesh.vertices))])
    mesh.update()


def get_skeleton_bones(armature: bpy.types.Object) -> dict[int, bpy.types.Bone]:
    bones = {}
    for bone in armature.data.bones:
        index = get_animated_index(bone.name)
        if index is not None and bone.fast64.dk64.bone_type == "Animated":
            bones[index] = bone
    if not bones:
        raise PluginError(
            f'"{armature.name}" has no {DK64_ANIMATED_PREFIX}<index> bones.'
        )
    return bones


class DK64_ExportActor(OperatorBase):
    bl_idname = "object.fast64_dk64_export_actor"
    bl_label = "Export Actor"
    bl_description = (
        "Exports the selected mesh and writes the actor's display lists."
        "Vertices with missing or multiple bone weights are automatically selected."
    )
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "EXPORT"

    def execute_operator(self, context: Context):
        dk64_props = context.scene.fast64.dk64
        settings = dk64_props.actor_export_settings
        obj = get_export_mesh(context)
        folder = settings.get_folder()
        index = dk64_props.rom_catalog.require_index(catalog.ACTOR, settings.name)

        armature = obj.find_armature()
        if armature is None:
            raise PluginError(f'"{obj.name}" has no armature.')
        bones = get_skeleton_bones(armature)
        transform = get_transform(armature, dk64_props.scale)
        bind_pose = {bone_index: tuple(transform @ bone.head_local) for bone_index, bone in bones.items()}
        bone_scales = {bone_index: get_bone_scale(bone) for bone_index, bone in bones.items()}
        actor = catalog.read_model(dk64_props.rom_catalog.loaded_rom, catalog.ACTOR, index)
        if len(bind_pose) != actor.bone_count:
            raise PluginError(
                f"Actor {index:04X} has {actor.bone_count} bones but the armature has "
                f"{len(bind_pose)}, so it is skinned to a different actor."
            )

        switch_segments = {
            bone.name: bone.fast64.dk64.segment
            for bone in armature.data.bones
            if bone.fast64.dk64.bone_type == "Switch"
        }
        try:
            vertex_bones = get_vertex_bones(obj, set(bind_pose))
            vertex_optional = get_vertex_optional(obj, switch_segments)
            result = export_actor(
                obj,
                dk64_props.scale,
                context.scene.saveTextures,
                bind_pose,
                bone_scales,
                vertex_bones,
                vertex_optional,
                index,
                actor.name,
                folder,
            )
        except DK64VertexWeightError as exception:
            select_vertices(obj, exception.invalid_vertices)
            raise PluginError(f"{exception} They are now selected, enter edit mode to fix them.") from exception

        self.report(
            {"INFO"},
            f"Exported {result.vertices} vertices, {result.triangles} triangles and "
            f"{result.textures} textures over {result.bones} bones to {result.model_folder.name}/.",
        )
