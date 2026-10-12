from typing import Optional

import bpy

from ..utility import PluginError, VertexWeightError
from .bone import get_animated_index
from .dk64_constants import DK64_ANIMATED_PREFIX, DK64_SWITCH_PREFIX


class DK64VertexWeightError(VertexWeightError):
    def __init__(self, message: str, invalid_vertices: list[int]):
        super().__init__(message)
        self.invalid_vertices = invalid_vertices


def get_vertex_bones(obj: bpy.types.Object, bones) -> dict[int, int]:
    animated_groups = {}
    for group in obj.vertex_groups:
        if not group.name.startswith(DK64_ANIMATED_PREFIX):
            continue
        bone = get_animated_index(group.name)
        if bone is None:
            raise PluginError(
                f'Vertex group "{group.name}" is not a valid animated group, expected "{DK64_ANIMATED_PREFIX}<index>".'
            )
        animated_groups[group.index] = bone

    vertex_bones = {}
    invalid_vertices = []
    for vertex in obj.data.vertices:
        weights = [
            (animated_groups[element.group], element.weight)
            for element in vertex.groups
            if element.group in animated_groups and element.weight > 0
        ]
        if len(weights) != 1 or abs(weights[0][1] - 1) > 1e-6:
            invalid_vertices.append(vertex.index)
            continue
        vertex_bones[vertex.index] = weights[0][0]

    if invalid_vertices:
        raise DK64VertexWeightError(
            f"{len(invalid_vertices)} vertices need exactly one animated group with a weight of 1.0 "
            f"(first: vertex {invalid_vertices[0]}).",
            invalid_vertices,
        )

    missing = sorted(index for index, bone in vertex_bones.items() if bone not in bones)
    if missing:
        absent = sorted({vertex_bones[index] for index in missing})
        raise DK64VertexWeightError(
            f"{len(missing)} vertices are weighted to "
            f"{', '.join(f'{DK64_ANIMATED_PREFIX}{bone:02d}' for bone in absent)}, "
            "which doesn't exist on the armature.",
            missing,
        )
    return vertex_bones


def get_vertex_optional(obj: bpy.types.Object, switch_segments: dict[str, int]) -> dict[int, int]:
    groups = {}
    for group in obj.vertex_groups:
        if group.name in switch_segments:
            groups[group.index] = switch_segments[group.name]
        elif group.name.startswith(DK64_SWITCH_PREFIX):
            raise PluginError(
                f'Vertex group "{group.name}" has no switch bone of the same name'
            )

    vertex_optional = {}
    invalid_vertices = []
    for vertex in obj.data.vertices:
        segments = {
            groups[element.group] for element in vertex.groups if element.group in groups and element.weight > 0
        }
        if len(segments) > 1:
            invalid_vertices.append(vertex.index)
        elif segments:
            vertex_optional[vertex.index] = segments.pop()

    if invalid_vertices:
        raise DK64VertexWeightError(
            f"{len(invalid_vertices)} vertices are in more than one optional group",
            invalid_vertices,
        )
    return vertex_optional


def get_triangle_optional(triangle, mesh: bpy.types.Mesh, vertex_optional: dict[int, int]) -> Optional[int]:
    segments = [vertex_optional.get(mesh.loops[loop_index].vertex_index) for loop_index in triangle.loops]
    if len(set(segments)) > 1:
        raise DK64VertexWeightError(
            "A triangle is only partly in an optional group. Put all three of its vertices in the "
            "group, or none of them.",
            [mesh.loops[loop_index].vertex_index for loop_index in triangle.loops],
        )
    return segments[0]


def get_export_mesh(context: bpy.types.Context) -> bpy.types.Object:
    obj = context.object
    if obj is None or obj.type != "MESH":
        raise PluginError("Select the mesh to export.")
    return obj
