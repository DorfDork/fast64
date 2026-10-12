from pathlib import Path

import bpy

from ..c_writer import ExportResult, get_symbol, write_c_files
from ..f3dex2 import DK64Model, TemporaryCopy, build_actor, model_stats, write_model
from ..hd_textures import HDTextures
from ..mesh import get_triangle_optional


def export_actor(
    obj: bpy.types.Object,
    scale: float,
    save_png: bool,
    bind_pose: dict,
    bone_scales: dict,
    vertex_bones: dict,
    vertex_optional: dict,
    index: int,
    name: str,
    folder: str,
) -> ExportResult:
    symbol = get_symbol("actor", index)
    model_folder = Path(folder) / f"{index:04X}"
    fModel = DK64Model(symbol, save_png)

    with TemporaryCopy(obj) as copy, HDTextures(copy) as hd_textures:
        fModel.full_size = hd_textures.full_size
        mesh = copy.data
        mesh.calc_loop_triangles()
        triangle_segments = {
            triangle.index: get_triangle_optional(triangle, mesh, vertex_optional) for triangle in mesh.loop_triangles
        }
        fMesh = build_actor(fModel, copy, scale, bind_pose, bone_scales, vertex_bones, triangle_segments)
        triangles = len(mesh.loop_triangles)
        externs = write_model(fModel, model_folder, f"{index:04X}/")

    defines = [
        (f"{symbol.upper()}_MODEL_ID", str(index + 1)),
        (f"{symbol.upper()}_BONE_COUNT", str(len(bind_pose))),
    ]
    display_list = fMesh.draw.name
    asset = [
        f"static const CustomActorAsset {symbol}_asset = {{",
        f"    {symbol.upper()}_MODEL_ID,",
        f"    {symbol.upper()}_BONE_COUNT,",
        f"    {display_list},",
        f"    sizeof({display_list}),",
        "};",
        "",
    ]
    write_c_files(model_folder, "actor", index, name, defines, asset, externs)

    vertices, textures = model_stats(fModel)
    return ExportResult(
        model_folder=model_folder,
        vertices=vertices,
        triangles=triangles,
        textures=textures,
        bones=len(set(vertex_bones.values())),
    )
