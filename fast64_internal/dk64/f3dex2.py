from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from ..f3d.f3d_gbi import (
    DLFormat,
    DPPipeSync,
    DPSetRenderMode,
    FImageKey,
    FMesh,
    FPaletteKey,
    FModel,
    GbiMacro,
    GfxFormatter,
    GfxMatWriteMethod,
    ScrollMethod,
    SPLoadGeometryMode,
    SPMatrix,
    SPSetOtherMode,
    TextureExportSettings,
    Vtx,
)
from ..f3d.f3d_writer import (
    TriangleConverterInfo,
    VertexGroupInfo,
    checkForF3dMaterialInFaces,
    getInfoDict,
    revertMatAndEndDraw,
    saveGeoModeCommon,
    saveMeshByFaces,
    saveMeshWithLargeTexturesByFaces,
    saveOrGetF3DMaterial,
)
from ..utility import CData, PluginError, create_or_get_world, transform_mtx_blender_to_n64, writeFile
from .dk64_constants import DK64_HILITE_SEGMENT
from .hd_textures import save_full_size

POSITION_RANGE = (-0x8000, 0x7FFF)

BONE_MATRIX_SEGMENT = 0x04000000
MATRIX_SIZE = 0x40

FIXED_POINT_ONE = 0x10000

CULL_VERTEX_COUNT = 8
PROP_VERTEX_SEGMENT = 0x08000000

PROP_MATRIX = 0x09000080

CULL_PADDING = 0.10
MINIMUM_CULL_PADDING = 8

DEFAULT_RENDER_MODE = ("G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2")

TEXTURE_ARRAY_BITS = 64


@dataclass(unsafe_hash=True)
class DK64Command(GbiMacro):
    text: str

    def to_c(self, static=True):
        return self.text


class DK64Model(FModel):
    def __init__(self, name: str, save_png: bool):
        super().__init__(name, DLFormat.Static, GfxMatWriteMethod.WriteDifferingAndRevert)
        self.save_png = save_png
        self.convertible_ci = set()
        self.scale_matrices: dict[float, str] = {}
        self.full_size: dict[bpy.types.Image, bpy.types.Image] = {}

    def onMaterialCommandsBuilt(self, fMaterial, material, drawLayer):
        super().onMaterialCommandsBuilt(fMaterial, material, drawLayer)
        if material.dk64.hilite:
            fMaterial.material.commands.append(DK64Command(f"gsSPDisplayList(0x{DK64_HILITE_SEGMENT:02X}000000)"))
        if material.f3d_mat.rdp_settings.set_rendermode and fMaterial.revert is not None:
            fMaterial.revert.commands.append(DPSetRenderMode(DEFAULT_RENDER_MODE, None))

    def scale_matrices_to_c(self) -> CData:
        data = CData()
        for scale, name in self.scale_matrices.items():
            words = [
                f"(s32)0x{word:08X}" if word & 0x80000000 else f"0x{word:08X}" for word in get_scale_matrix_words(scale)
            ]
            rows = ",\n".join(f"    {{ {', '.join(words[row : row + 4])} }}" for row in range(0, 16, 4))
            data.header += f"extern Mtx {name};\n"
            data.source += f"Mtx {name} = {{{{\n{rows},\n}}}};\n\n"
        return data

    def to_c_textures(self, texCSeparate, savePNG, texDir, texArrayBitSize):
        self.name_ci_files()
        return super().to_c_textures(texCSeparate, savePNG, texDir, texArrayBitSize)

    def name_ci_files(self) -> None:
        palettes = {
            key.imagesSharingPalette: image for key, image in self.textures.items() if isinstance(key, FPaletteKey)
        }
        users = {}
        for key, image in self.textures.items():
            if isinstance(key, FImageKey) and image.fmt == "G_IM_FMT_CI":
                users.setdefault(key.imagesSharingPalette, []).append((key, image))

        for images, textures in users.items():
            palette = palettes.get(images)
            for key, image in textures:
                base = image.filename.removesuffix(".inc.c").rsplit(".", 1)[0]
                ci_format = "ci4" if image.bitSize == "G_IM_SIZ_4b" else "ci8"
                image.filename = f"{base}.{ci_format}.inc.c"
                if palette is not None and len(textures) == 1:
                    palette.filename = f"{base}.{ci_format}.pal.inc.c"
                    if palette.fmt == "G_IM_FMT_RGBA":
                        self.convertible_ci.update((id(image), id(palette)))
            if palette is not None and not palette.filename.endswith(".inc.c"):
                palette.filename += ".inc.c"

    def save_textures(self, exportPath):
        folder = Path(exportPath)
        for key, image in self.textures.items():
            converted = folder / image.filename
            png = folder / (image.filename.removesuffix(".inc.c") + ".png")
            is_palette = isinstance(key, FPaletteKey)
            full_size = None if is_palette else self.full_size.get(key.image)
            convertible = (image.fmt != "G_IM_FMT_CI" and not is_palette) or id(image) in self.convertible_ci
            if full_size is not None:
                save_full_size(full_size, png)
                converted.unlink(missing_ok=True)
            elif self.save_png and convertible:
                if not is_palette:
                    save_image(key.image, png)
                converted.unlink(missing_ok=True)
            else:
                writeFile(str(converted), image.to_c_data(TEXTURE_ARRAY_BITS) + "\n")
                if not is_palette:
                    png.unlink(missing_ok=True)
        return len(self.textures)


def save_image(image: bpy.types.Image, path: Path) -> None:
    was_packed = image.packed_file is not None
    if not was_packed:
        image.pack()
    old_path = image.filepath
    try:
        image.filepath = str(path)
        image.save()
    finally:
        image.filepath = old_path
        if not was_packed:
            image.unpack()


def get_scale_matrix_words(scale: float) -> list[int]:
    diagonal = round(scale * FIXED_POINT_ONE)
    values = [0] * 16
    values[0] = values[5] = values[10] = diagonal
    values[15] = FIXED_POINT_ONE
    integers = [value >> 16 & 0xFFFF for value in values]
    fractions = [value & 0xFFFF for value in values]
    halves = integers + fractions
    return [halves[index] << 16 | halves[index + 1] for index in range(0, 32, 2)]


class DK64TriangleConverterInfo(TriangleConverterInfo):
    def __init__(self, obj, f3d, transform: Matrix, info, bind_pose: dict, bone_scales: dict):
        super().__init__(obj, None, f3d, transform, info)
        self.bind_pose = bind_pose
        self.bone_scales = bone_scales
        self.matrix_bones = {}

    def getMatrixAddrFromGroup(self, bone):
        address = f"0x{BONE_MATRIX_SEGMENT + bone * MATRIX_SIZE:08X}"
        self.matrix_bones[address] = bone
        return address

    def getTransformMatrix(self, bone) -> Matrix:
        if bone is None:
            return self.transformMatrix
        return Matrix.Translation(-Vector(self.bind_pose[bone])) @ self.transformMatrix


def add_bone_scales(fModel: DK64Model, fMesh: FMesh, converter_info: DK64TriangleConverterInfo) -> None:
    for group in fMesh.triangleGroups:
        commands = []
        for command in group.triList.commands:
            commands.append(command)
            bone = converter_info.matrix_bones.get(command.matrix) if isinstance(command, SPMatrix) else None
            if bone is not None and converter_info.bone_scales[bone] != 1:
                matrix = fModel.scale_matrices.setdefault(
                    converter_info.bone_scales[bone], f"{fModel.name}_scale_{len(fModel.scale_matrices)}"
                )
                commands.append(DK64Command(f"gsSPMatrix(&{matrix}, G_MTX_MODELVIEW | G_MTX_MUL | G_MTX_NOPUSH)"))
        group.triList.commands = commands


def get_transform(obj: bpy.types.Object, scale: float) -> Matrix:
    return Matrix.Scale(scale, 4) @ transform_mtx_blender_to_n64() @ obj.matrix_world


def default_state() -> list:
    defaults = create_or_get_world(bpy.context.scene).rdp_defaults
    geometry = []
    saveGeoModeCommon(lambda value, _default, flag: value and geometry.append(flag), defaults, defaults, ())
    other_mode_h = (
        defaults.g_mdsft_alpha_dither,
        defaults.g_mdsft_rgb_dither,
        defaults.g_mdsft_combkey,
        defaults.g_mdsft_textconv,
        defaults.g_mdsft_text_filt,
        defaults.g_mdsft_textlut,
        defaults.g_mdsft_textlod,
        defaults.g_mdsft_textdetail,
        defaults.g_mdsft_textpersp,
        defaults.g_mdsft_cycletype,
        defaults.g_mdsft_pipeline,
    )
    other_mode_l = (defaults.g_mdsft_alpha_compare, defaults.g_mdsft_zsrcsel, *DEFAULT_RENDER_MODE)
    return [
        DPPipeSync(),
        SPLoadGeometryMode((*geometry, "G_CLIPPING")),
        SPSetOtherMode("G_SETOTHERMODE_H", 4, 20, other_mode_h),
        SPSetOtherMode("G_SETOTHERMODE_L", 0, 32, other_mode_l),
    ]


def is_translucent(material: bpy.types.Material) -> bool:
    rdp_settings = material.f3d_mat.rdp_settings
    if not rdp_settings.set_rendermode:
        return False
    if rdp_settings.rendermode_advanced_enabled:
        return rdp_settings.force_bl or rdp_settings.zmode == "ZMODE_XLU"
    if rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
        return "XLU" in rdp_settings.rendermode_preset_cycle_2
    return "XLU" in rdp_settings.rendermode_preset_cycle_1


def draw_faces(fModel: FModel, fMesh: FMesh, obj: bpy.types.Object, converter_info, faces) -> None:
    by_material = {}
    for face in faces:
        by_material.setdefault(face.material_index, []).append(face)
    order = sorted(by_material, key=lambda index: (is_translucent(obj.material_slots[index].material), index))

    fMesh.currentFMaterial = None
    for index in order:
        material = obj.material_slots[index].material
        checkForF3dMaterialInFaces(obj, material)
        fMaterial, _ = saveOrGetF3DMaterial(material, fModel, obj, None, True)
        large = fMaterial.isTexLarge[0] or fMaterial.isTexLarge[1]
        save_mesh = saveMeshWithLargeTexturesByFaces if large else saveMeshByFaces
        save_mesh(material, by_material[index], fModel, fMesh, obj, None, True, None, converter_info, None, None, None)


def add_mesh(fModel: FModel, name: str) -> FMesh:
    fMesh = FMesh(name, DLFormat.Static)
    fModel.meshes[name] = fMesh
    return fMesh


def all_vertices(fMesh: FMesh) -> list[Vtx]:
    return [vertex for group in fMesh.triangleGroups for vertex in group.vertexList.vertices]


def check_positions(vertices: list[Vtx]) -> None:
    for vertex in vertices:
        for value in vertex.position:
            if not POSITION_RANGE[0] <= value <= POSITION_RANGE[1]:
                raise PluginError(
                    f"A vertex ends up {value} units out over the 16 bit range."
                    "Please scale the mesh closer to the origin."
                )


def build_actor(
    fModel: DK64Model,
    obj: bpy.types.Object,
    scale: float,
    bind_pose: dict,
    bone_scales: dict,
    vertex_bones: dict,
    triangle_segments: dict,
) -> FMesh:
    vertex_group_info = VertexGroupInfo()
    vertex_group_info.vertexGroups = vertex_bones
    info = getInfoDict(obj, vertex_group_info)
    transform = get_transform(obj, scale)
    converter_info = DK64TriangleConverterInfo(obj, fModel.f3d, transform, info, bind_pose, bone_scales)

    blocks = {}
    for face in obj.data.loop_triangles:
        blocks.setdefault(triangle_segments[face.index], []).append(face)

    fMesh = add_mesh(fModel, f"{fModel.name}_mesh")
    fMesh.draw.commands.extend(default_state())
    for segment in sorted(blocks, key=lambda segment: (segment is not None, segment or 0)):
        if segment is not None:
            fMesh.draw.commands.append(DK64Command(f"gsSPBranchList(0x{segment:02X}000000)"))
        draw_faces(fModel, fMesh, obj, converter_info, blocks[segment])
        if segment is not None:
            fMesh.draw.commands.append(DK64Command(f"gsDPNoOpTag({segment})"))
    revertMatAndEndDraw(fMesh.draw, [])
    add_bone_scales(fModel, fMesh, converter_info)
    check_positions(all_vertices(fMesh))
    return fMesh


def prop_begin() -> list:
    return [
        DK64Command(f"gsSPVertex(0x{PROP_VERTEX_SEGMENT:08X}U, {CULL_VERTEX_COUNT}, 0)"),
        DK64Command(f"gsSPCullDisplayList(0, {CULL_VERTEX_COUNT - 1})"),
        DK64Command(f"gsSPMatrix(0x{PROP_MATRIX:08X}, G_MTX_MODELVIEW | G_MTX_MUL | G_MTX_PUSH)"),
    ]


def get_cull_vertices(vertices: list[Vtx]) -> list[Vtx]:
    axes = [[vertex.position[axis] for vertex in vertices] for axis in range(3)]
    padding = max(MINIMUM_CULL_PADDING, int(max(max(axis) - min(axis) for axis in axes) * CULL_PADDING))
    low = [min(axis) - padding for axis in axes]
    high = [max(axis) + padding for axis in axes]
    return [
        Vtx([high[axis] if corner & (1 << axis) else low[axis] for axis in range(3)], [0, 0], [0xFF, 0xFF, 0xFF, 0xFF])
        for corner in range(CULL_VERTEX_COUNT)
    ]


def build_prop(fModel: FModel, obj: bpy.types.Object, scale: float) -> tuple[FMesh, FMesh]:
    info = getInfoDict(obj)
    converter_info = TriangleConverterInfo(obj, None, fModel.f3d, get_transform(obj, scale), info)

    fMesh = add_mesh(fModel, f"{fModel.name}_mesh")
    draw_faces(fModel, fMesh, obj, converter_info, list(obj.data.loop_triangles))
    vertices = all_vertices(fMesh)
    check_positions(vertices)

    fMesh.add_cull_vtx()
    fMesh.cullVertexList.vertices = get_cull_vertices(vertices)
    check_positions(fMesh.cullVertexList.vertices)
    fMesh.draw.commands[:0] = prop_begin() + default_state()
    revertMatAndEndDraw(fMesh.draw, [DK64Command("gsSPPopMatrix(G_MTX_MODELVIEW)")])

    second = add_mesh(fModel, f"{fModel.name}_mesh_2")
    second.draw.commands = prop_begin()
    revertMatAndEndDraw(second.draw, [DK64Command("gsSPPopMatrix(G_MTX_MODELVIEW)")])
    return fMesh, second


def write_model(fModel: FModel, model_folder: Path, include_folder: str) -> str:
    model_folder.mkdir(parents=True, exist_ok=True)
    formatter = GfxFormatter(ScrollMethod.Vertex, TEXTURE_ARRAY_BITS, None)
    settings = TextureExportSettings(False, True, include_folder, str(model_folder))
    data = fModel.to_c(settings, formatter)
    c_data = fModel.scale_matrices_to_c()
    c_data.append(data.staticData)
    c_data.append(data.dynamicData)
    writeFile(str(model_folder / "model.inc.c"), c_data.source)
    return c_data.header


def model_stats(fModel: FModel) -> tuple[int, int]:
    vertices = sum(len(all_vertices(fMesh)) for fMesh in fModel.meshes.values())
    return vertices, len(fModel.textures)


class TemporaryCopy:
    def __init__(self, obj: bpy.types.Object):
        self.obj = obj.copy()
        self.obj.data = obj.data.copy()

    def __enter__(self) -> bpy.types.Object:
        return self.obj

    def __exit__(self, *_exc):
        mesh = self.obj.data
        bpy.data.objects.remove(self.obj)
        bpy.data.meshes.remove(mesh)
