from pathlib import Path

import bpy

from ..c_writer import ExportResult, get_symbol, write_c_files
from ..f3dex2 import DK64Model, TemporaryCopy, build_prop, model_stats, write_model
from ..hd_textures import HDTextures


def export_prop(
    obj: bpy.types.Object, scale: float, save_png: bool, index: int, name: str, folder: str
) -> ExportResult:
    symbol = get_symbol("prop", index)
    model_folder = Path(folder) / f"{index:04X}"
    fModel = DK64Model(symbol, save_png)

    with TemporaryCopy(obj) as copy, HDTextures(copy) as hd_textures:
        fModel.full_size = hd_textures.full_size
        mesh, second_mesh = build_prop(fModel, copy, scale)
        triangles = len(copy.data.loop_triangles)
        externs = write_model(fModel, model_folder, f"{index:04X}/")

    defines = [(f"{symbol.upper()}_TYPE", f"0x{index:03X}")]
    display_list = mesh.draw.name
    second_display_list = second_mesh.draw.name
    cull_vertices = mesh.cullVertexList.name
    asset = [
        f"static const CustomModelAsset {symbol}_asset = {{",
        f"    {symbol.upper()}_TYPE,",
        f"    {display_list},",
        f"    sizeof({display_list}),",
        f"    {second_display_list},",
        f"    sizeof({second_display_list}),",
        f"    {cull_vertices},",
        f"    sizeof({cull_vertices}),",
        "};",
        "",
    ]
    write_c_files(model_folder, "prop", index, name, defines, asset, externs)

    vertices, textures = model_stats(fModel)
    return ExportResult(
        model_folder=model_folder,
        vertices=vertices + len(mesh.cullVertexList.vertices),
        triangles=triangles,
        textures=textures,
    )
