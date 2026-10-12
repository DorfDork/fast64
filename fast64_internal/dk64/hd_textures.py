import shutil
from pathlib import Path

import bpy

from ..f3d.f3d_material import all_combiner_uses, getTmemMax, getTmemWordUsage
from ..utility import PluginError

TMEM_WORD_BYTES = 8


def get_used_textures(material: bpy.types.Material) -> list:
    f3d_mat = material.f3d_mat
    uses = all_combiner_uses(f3d_mat)
    textures = []
    for index, texture in enumerate((f3d_mat.tex0, f3d_mat.tex1)):
        if uses[f"Texture {index}"] and texture.tex_set and texture.tex is not None and not texture.use_tex_reference:
            textures.append(texture)
    return textures


def get_fitting_sizes(textures: list) -> list[tuple[int, int]]:
    sizes = [tuple(texture.tex.size) for texture in textures]
    limit = getTmemMax(textures[0].tex_format) // TMEM_WORD_BYTES

    def usage(index: int) -> int:
        return getTmemWordUsage(textures[index].tex_format, *sizes[index])

    while sum(usage(index) for index in range(len(sizes))) > limit:
        largest = max(range(len(sizes)), key=usage)
        width, height = sizes[largest]
        if width == 1 and height == 1:
            raise PluginError(f"Image {textures[largest].tex.name} cannot be made small enough for texture memory.")
        sizes[largest] = (max(width // 2, 1), max(height // 2, 1))
    return sizes


def save_full_size(image: bpy.types.Image, path: Path) -> None:
    source = Path(bpy.path.abspath(image.filepath)) if image.filepath else None
    if source is not None and source.suffix.lower() == ".png" and source.is_file() and not image.is_dirty:
        shutil.copyfile(source, path)
        return

    copy = image.copy()
    try:
        copy.filepath_raw = str(path)
        copy.file_format = "PNG"
        copy.save()
    finally:
        bpy.data.images.remove(copy)


TILE_FIELDS = ("low", "high", "mask", "shift")


def fit_tile_field(field, texture, original_size: int, size: int) -> None:
    if texture.autoprop:
        high = size * 2 if field.clamp and field.mirror else size
        values = (0.0, float(high - 1), max(size - 1, 0).bit_length(), 0)
    else:
        ratio = size / original_size
        halvings = (original_size // size).bit_length() - 1
        values = (field.low * ratio, (field.high + 1) * ratio - 1, max(field.mask - halvings, 0), field.shift)
    for name, value in zip(TILE_FIELDS, values):
        field[name] = value


class HDTextures:
    def __init__(self, obj: bpy.types.Object):
        self.obj = obj
        self.full_size: dict[bpy.types.Image, bpy.types.Image] = {}
        self.copies: dict[tuple, bpy.types.Image] = {}
        self.swapped: list[tuple] = []
        self.renamed: list[tuple] = []

    def __enter__(self) -> "HDTextures":
        if not bpy.context.scene.ignoreTextureRestrictions:
            return self
        try:
            for slot in self.obj.material_slots:
                material = slot.material
                if material is None or not material.is_f3d:
                    continue
                if material.mat_ver > 3 and material.f3d_mat.use_large_textures:
                    continue
                textures = get_used_textures(material)
                if not textures:
                    continue
                for texture, size in zip(textures, get_fitting_sizes(textures)):
                    if size == tuple(texture.tex.size):
                        continue
                    if texture.tex_format.startswith("CI"):
                        raise PluginError(
                            f'Material "{material.name}": {texture.tex.name} is bigger than texture memory. RT64 '
                            "draws at full size only in non-CI format."
                        )
                    self.swap(texture, size)
        except Exception:
            self.restore()
            raise
        return self

    def __exit__(self, *_exc):
        self.restore()

    def swap(self, texture, size: tuple[int, int]) -> None:
        image = texture.tex
        key = (image.name, size)
        copy = self.copies.get(key)
        if copy is None:
            copy = image.copy()
            copy.scale(*size)
            if not image.filepath:
                name = image.name
                image.name = f"{name}_full_size"
                copy.name = name
                self.renamed.append((image, name))
            self.copies[key] = copy
            self.full_size[copy] = image

        fields = (texture.S, texture.T)
        saved = [[getattr(field, name) for name in TILE_FIELDS] for field in fields]
        self.swapped.append((texture, image, saved))
        texture["tex"] = copy
        for field, original_size, new_size in zip(fields, image.size, size):
            fit_tile_field(field, texture, original_size, new_size)

    def restore(self) -> None:
        for texture, image, saved in reversed(self.swapped):
            texture["tex"] = image
            for field, values in zip((texture.S, texture.T), saved):
                for name, value in zip(TILE_FIELDS, values):
                    field[name] = value
        self.swapped.clear()
        for copy in self.copies.values():
            bpy.data.images.remove(copy)
        self.copies.clear()
        for image, name in self.renamed:
            image.name = name
        self.renamed.clear()
