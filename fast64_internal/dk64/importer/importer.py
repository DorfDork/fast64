from pathlib import Path

import bpy

from mathutils import Matrix, Vector

from ...f3d.f3d_gbi import get_F3D_GBI
from ...f3d.f3d_material import createF3DMat, F3DMaterial_UpdateLock, update_node_values_of_material
from ...f3d.f3d_parser import renderModeMask
from ...utility import PluginError, yUpToZUp, deselectAllObjects, gammaInverseValue, int_from_s16
from ..contrib import install_contrib_path
from ..bone import get_animated_name, get_switch_name
from ..dk64_constants import DK64_SCALE_BONE

install_contrib_path()

from dk64_lib.f3dex2.display_list import CYCLE_FIELDS  # noqa: E402  vendored

TEXTURE_FORMATS = {0: "RGBA", 2: "CI", 3: "IA", 4: "I"}
TEXTURE_SIZES = {0: "4", 1: "8", 2: "16", 3: "32"}

ALPHA_COMPARE = ("G_AC_NONE", "G_AC_THRESHOLD", "G_AC_THRESHOLD", "G_AC_DITHER")


def get_extent(points) -> float:
    return max(
        (max(point[axis] for point in points) - min(point[axis] for point in points) for axis in range(3)),
        default=0.0,
    )


def create_skeleton(
    context: bpy.types.Context, name: str, bones, transform: Matrix, model_extent: float, switches: dict
):
    armature = bpy.data.armatures.new(f"{name}_skeleton")
    armature_obj = bpy.data.objects.new(name, armature)
    context.collection.objects.link(armature_obj)
    armature_obj.show_in_front = True

    deselectAllObjects()
    context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    heads = [transform @ Vector(bone.world) for bone in bones]
    children = {index: [child.index for child in bones if child.parent == index] for index in range(len(bones))}
    min_length = 0.02 * (get_extent(heads) or model_extent or 1.0)

    scale_bone = armature.edit_bones.new(DK64_SCALE_BONE)
    scale_bone.tail = Vector((0.0, 0.0, min_length))
    scale_bone.use_deform = False

    edit_bones = [armature.edit_bones.new(get_animated_name(bone.index)) for bone in bones]
    for bone, edit_bone in zip(bones, edit_bones):
        head = heads[bone.index]
        tail = head + Vector((0.0, 0.0, min_length))
        if children[bone.index]:
            child_center = sum((heads[child] for child in children[bone.index]), Vector()) / len(children[bone.index])
            if (child_center - head).length > min_length:
                tail = child_center
        edit_bone.head = head
        edit_bone.tail = tail
        if bone.parent < len(bones):
            edit_bone.parent = edit_bones[bone.parent]
        else:
            edit_bone.parent = scale_bone

    for segment, (center, parent) in sorted(switches.items()):
        edit_bone = armature.edit_bones.new(get_switch_name(segment))
        edit_bone.head = center
        edit_bone.tail = center + Vector((0.0, 0.0, min_length))
        edit_bone.parent = edit_bones[parent]
        edit_bone.use_deform = False

    bpy.ops.object.mode_set(mode="OBJECT")
    armature.bones[DK64_SCALE_BONE].fast64.dk64.bone_type = "Scale"
    for bone in bones:
        armature.bones[get_animated_name(bone.index)].fast64.dk64.channel = bone.channel
    for segment in switches:
        props = armature.bones[get_switch_name(segment)].fast64.dk64
        props.bone_type = "Switch"
        props.segment = segment
    return armature_obj


def get_switches(mesh_obj: bpy.types.Object, vertex_bones: list[int], optional_vertices: dict) -> dict:
    switches = {}
    for segment, vertex_indices in optional_vertices.items():
        center = sum((mesh_obj.data.vertices[index].co for index in vertex_indices), Vector()) / len(vertex_indices)
        carriers = [vertex_bones[index] for index in vertex_indices]
        switches[segment] = (center, max(set(carriers), key=carriers.count))
    return switches


def get_color(rgba) -> list[float]:
    return [gammaInverseValue(channel / 0xFF) for channel in rgba[:3]] + [rgba[3] / 0xFF]


def create_image(texture, texture_folder: Path) -> bpy.types.Image:
    path = texture_folder / f"{texture.name}.png"
    if path.is_file():
        image = bpy.data.images.load(str(path), check_existing=True)
        image.name = texture.name
        return image

    image = bpy.data.images.new(texture.name, texture.width, texture.height, alpha=True)
    row_length = texture.width * 4
    pixels = []
    for row in reversed(range(texture.height)):
        start = row * row_length
        pixels.extend(value / 0xFF for value in texture.rgba[start : start + row_length])
    image.pixels[:] = pixels
    image.pack()
    return image


def set_other_mode_l(rdp_settings, other_mode_l: int) -> None:
    f3d = get_F3D_GBI()
    rdp_settings.g_mdsft_alpha_compare = ALPHA_COMPARE[other_mode_l & 0x3]
    rdp_settings.g_mdsft_zsrcsel = "G_ZS_PRIM" if other_mode_l & 0x4 else "G_ZS_PIXEL"

    rdp_settings.set_rendermode = True
    rdp_settings.rendermode_advanced_enabled = True
    render_mode_1 = renderModeMask(other_mode_l, 1, False)
    render_mode_2 = renderModeMask(other_mode_l, 2, False)
    rdp_settings.aa_en = render_mode_1 & f3d.AA_EN != 0
    rdp_settings.z_cmp = render_mode_1 & f3d.Z_CMP != 0
    rdp_settings.z_upd = render_mode_1 & f3d.Z_UPD != 0
    rdp_settings.im_rd = render_mode_1 & f3d.IM_RD != 0
    rdp_settings.clr_on_cvg = render_mode_1 & f3d.CLR_ON_CVG != 0
    rdp_settings.cvg_dst = f3d.cvgDstDict[render_mode_1 & f3d.CVG_DST_SAVE]
    rdp_settings.zmode = f3d.zmodeDict[render_mode_1 & f3d.ZMODE_DEC]
    rdp_settings.cvg_x_alpha = render_mode_1 & f3d.CVG_X_ALPHA != 0
    rdp_settings.alpha_cvg_sel = render_mode_1 & f3d.ALPHA_CVG_SEL != 0
    rdp_settings.force_bl = render_mode_1 & f3d.FORCE_BL != 0

    rdp_settings.blend_p1 = f3d.blendColorDict[render_mode_1 >> 30 & 3]
    rdp_settings.blend_a1 = f3d.blendAlphaDict[render_mode_1 >> 26 & 3]
    rdp_settings.blend_m1 = f3d.blendColorDict[render_mode_1 >> 22 & 3]
    rdp_settings.blend_b1 = f3d.blendMixDict[render_mode_1 >> 18 & 3]
    rdp_settings.blend_p2 = f3d.blendColorDict[render_mode_2 >> 28 & 3]
    rdp_settings.blend_a2 = f3d.blendAlphaDict[render_mode_2 >> 24 & 3]
    rdp_settings.blend_m2 = f3d.blendColorDict[render_mode_2 >> 20 & 3]
    rdp_settings.blend_b2 = f3d.blendMixDict[render_mode_2 >> 16 & 3]


def set_material_props(f3d_mat, group, images: dict[str, bpy.types.Image]) -> None:
    render = group.render
    rdp_settings = f3d_mat.rdp_settings
    rdp_settings.g_lighting = render.lighting
    f3d_mat.set_lights = False
    rdp_settings.g_fog = render.fog
    rdp_settings.g_tex_gen = render.texture_gen
    rdp_settings.g_tex_gen_linear = render.texture_gen_linear
    rdp_settings.g_mdsft_cycletype = "G_CYC_2CYCLE" if render.two_cycle else "G_CYC_1CYCLE"
    rdp_settings.g_cull_front = render.cull_front
    rdp_settings.g_cull_back = render.cull_back
    set_other_mode_l(rdp_settings, render.other_mode_l)

    f3d_mat.set_combiner = True
    for combiner, cycle in zip((f3d_mat.combiner1, f3d_mat.combiner2), render.combiner):
        for field, value in zip(CYCLE_FIELDS, cycle):
            setattr(combiner, field, value)
    f3d_mat.set_prim = True
    f3d_mat.prim_color = get_color(render.prim_color)
    f3d_mat.set_env = True
    f3d_mat.env_color = get_color(render.env_color)

    texture = group.texture
    if texture is None:
        return

    set_texture_props(f3d_mat.tex0, texture, render, images)
    if any(value.startswith("TEXEL1") for cycle in render.combiner for value in cycle):
        set_texture_props(f3d_mat.tex1, texture, render, images)


def set_texture_props(tex_props, texture, render, images: dict[str, bpy.types.Image]) -> None:
    tex_props.tex = images[texture.material_name]
    tex_props.tex_format = f"{TEXTURE_FORMATS.get(texture.fmt, 'RGBA')}{TEXTURE_SIZES.get(texture.size, '16')}"
    tex_props.autoprop = False
    for field, clamp, mirror, mask, shift, size in (
        (tex_props.S, texture.clamp_s, render.mirror_s, render.mask_s, render.shift_s, texture.width),
        (tex_props.T, texture.clamp_t, render.mirror_t, render.mask_t, render.shift_t, texture.height),
    ):
        field.clamp = clamp
        field.mirror = mirror
        field.mask = mask
        field.shift = shift
        field.low = 0
        field.high = size - 1


def material_key(group):
    return (group.texture, group.render, group.translucent, group.double_sided)


def create_materials(obj: bpy.types.Object, groups, images) -> dict:
    indices = {}
    for group in groups:
        key = material_key(group)
        if key in indices:
            continue
        indices[key] = len(indices)
        if group.texture:
            preset = "shaded_texture" if group.render.lighting else "vertex_colored_texture"
        else:
            preset = "shaded_solid"
        f3d_material = createF3DMat(obj, preset=preset)
        label = group.texture.material_name if group.texture else "vertex_color"
        f3d_material.name = f"{label}_{indices[key]}"

        f3d_material.f3d_update_flag = True
        set_material_props(f3d_material.f3d_mat, group, images)
        f3d_material.dk64.hilite = group.render.hilite and group.texture is not None
        f3d_material.f3d_update_flag = False
        with F3DMaterial_UpdateLock(f3d_material) as locked_material:
            update_node_values_of_material(locked_material, bpy.context)
    return indices


def create_mesh(context: bpy.types.Context, name: str, groups, images, transform: Matrix):
    positions, colors, vertex_bones, triangles, triangle_materials, uvs = ([], [], [], [], [], [])
    optional_vertices: dict[int, list[int]] = {}
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj = bpy.data.objects.new(f"{name}_mesh", mesh)
    context.collection.objects.link(obj)
    indices = create_materials(obj, groups, images)

    for group in groups:
        base = len(positions)
        material_index = indices[material_key(group)]
        for vertex in group.vertices:
            positions.append(transform @ Vector((vertex.x, vertex.y, vertex.z)))
            colors.append((vertex.xr, vertex.yg, vertex.zb, vertex.alpha))
        vertex_bones.extend(group.vertex_bones or [0] * len(group.vertices))
        if group.optional_segment is not None:
            optional_vertices.setdefault(group.optional_segment, []).extend(range(base, len(positions)))
        for triangle in group.triangles:
            corners = (triangle.v1, triangle.v2, triangle.v3)
            triangles.append([base + corner for corner in corners])
            triangle_materials.append(material_index)
            for corner in corners:
                uvs.extend(uv_for_vertex(group, group.vertices[corner]))

    mesh.from_pydata(positions, [], triangles)
    mesh.update()
    if len(mesh.polygons) != len(triangles):
        raise PluginError(f"Expected {len(triangles)} triangles, Blender made {len(mesh.polygons)}.")

    mesh.polygons.foreach_set("material_index", triangle_materials)
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.uv_layers.new(name="UVMap").data.foreach_set("uv", uvs)
    set_vertex_colors(mesh, colors)
    set_normals(mesh, groups, transform)
    return obj, vertex_bones, optional_vertices


def uv_for_vertex(group, vertex) -> tuple[float, float]:
    if group.texture is None:
        return (0.0, 0.0)
    u = int_from_s16(vertex.texture_cord_u) / 32 / group.texture.width
    v = int_from_s16(vertex.texture_cord_v) / 32 / group.texture.height
    return (u, 1.0 - v)


def set_vertex_colors(mesh: bpy.types.Mesh, colors) -> None:
    loop_colors = [colors[loop.vertex_index] for loop in mesh.loops]
    mesh.color_attributes["Col"].data.foreach_set(
        "color",
        [
            channel
            for red, green, blue, _alpha in loop_colors
            for channel in (red / 0xFF, green / 0xFF, blue / 0xFF, 1.0)
        ],
    )
    mesh.color_attributes["Alpha"].data.foreach_set(
        "color",
        [channel for *_rgb, alpha in loop_colors for channel in (alpha / 0xFF, alpha / 0xFF, alpha / 0xFF, 1.0)],
    )


def set_normals(mesh: bpy.types.Mesh, groups, transform: Matrix) -> None:
    rotation = transform.to_3x3().normalized()
    per_vertex = []
    for group in groups:
        if group.vertex_normals:
            per_vertex.extend((rotation @ Vector(normal)).normalized() for normal in group.vertex_normals)
        else:
            per_vertex.extend(Vector() for _ in group.vertices)
    # Changed in Blender 4.1: "Meshes now always use custom normals if they exist."
    if bpy.app.version < (4, 1, 0):
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set([per_vertex[loop.vertex_index] for loop in mesh.loops])


def import_model(context: bpy.types.Context, model, name: str, scale: float, texture_folder: Path):
    decoded, textures = model.decode()
    groups = [group for group in decoded if group.vertices and group.triangles]
    if not groups:
        raise PluginError("This model's display lists draw no triangles.")

    images = {texture.name: create_image(texture, texture_folder) for texture in textures}

    transform = yUpToZUp @ Matrix.Scale(1 / scale, 4)
    mesh_obj, vertex_bones, optional_vertices = create_mesh(context, name, groups, images, transform)

    if model.bones:
        model_extent = get_extent([vertex.co for vertex in mesh_obj.data.vertices])
        switches = get_switches(mesh_obj, vertex_bones, optional_vertices)
        armature_obj = create_skeleton(context, name, model.bones, transform, model_extent, switches)
        vertices_by_bone: dict[int, list[int]] = {}
        for index, bone in enumerate(vertex_bones):
            vertices_by_bone.setdefault(bone, []).append(index)
        for bone, vertex_indices in sorted(vertices_by_bone.items()):
            mesh_obj.vertex_groups.new(name=get_animated_name(bone)).add(vertex_indices, 1.0, "REPLACE")
        for segment, vertex_indices in sorted(optional_vertices.items()):
            mesh_obj.vertex_groups.new(name=get_switch_name(segment)).add(vertex_indices, 1.0, "REPLACE")
        mesh_obj.parent = armature_obj
        modifier = mesh_obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature_obj

    deselectAllObjects()
    context.view_layer.objects.active = mesh_obj
    mesh_obj.select_set(True)
    return mesh_obj, groups
