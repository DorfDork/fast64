from bpy.path import abspath
from bpy.props import FloatProperty, PointerProperty, StringProperty
from bpy.types import Material, PropertyGroup
from bpy.utils import register_class, unregister_class
from .rom.catalog import close_roms
from .rom.properties import DK64RomCatalog, DK64RomEntry
from .importer.properties import DK64ImportSettings
from .importer.operators import DK64_ImportRomModel
from .export_settings import DK64ExportSettings
from .bone import DK64_BonePanel, DK64_BoneProperties
from .material import DK64_MaterialPanel, DK64_MaterialProperties
from .actor.operators import DK64_ExportActor
from .prop.operators import DK64_ExportProp
from .panels import DK64_CombinedExporterPanel, DK64_CombinedImporterPanel, DK64_GeneralSettingsPanel
from ..render_settings import on_update_render_settings


def on_update_import_rom(self, context):
    self.rom_catalog.load(abspath(self.import_rom))


class DK64_Properties(PropertyGroup):
    scale: FloatProperty(name="Blender To DK64 Scale", default=100, update=on_update_render_settings)
    import_rom: StringProperty(
        name="Import ROM",
        subtype="FILE_PATH",
        description="A Donkey Kong 64 ROM.",
        update=on_update_import_rom,
    )
    rom_catalog: PointerProperty(type=DK64RomCatalog)
    import_settings: PointerProperty(type=DK64ImportSettings)
    actor_export_settings: PointerProperty(type=DK64ExportSettings)
    prop_export_settings: PointerProperty(type=DK64ExportSettings)

    @staticmethod
    def upgrade_changed_props():
        pass


dk64_classes = (
    DK64RomEntry,
    DK64RomCatalog,
    DK64ImportSettings,
    DK64ExportSettings,
    DK64_BoneProperties,
    DK64_MaterialProperties,
    DK64_Properties,
)

dk64_panel_classes = (
    DK64_ImportRomModel,
    DK64_ExportActor,
    DK64_ExportProp,
    DK64_GeneralSettingsPanel,
    DK64_CombinedImporterPanel,
    DK64_CombinedExporterPanel,
    DK64_BonePanel,
    DK64_MaterialPanel,
)


def dk64_panel_register():
    for cls in dk64_panel_classes:
        register_class(cls)


def dk64_panel_unregister():
    for cls in dk64_panel_classes:
        unregister_class(cls)


def dk64_register(registerPanels):
    for cls in dk64_classes:
        register_class(cls)
    Material.dk64 = PointerProperty(type=DK64_MaterialProperties, name="DK64 Material Properties")
    if registerPanels:
        dk64_panel_register()


def dk64_unregister(registerPanel):
    close_roms()
    del Material.dk64
    for cls in reversed(dk64_classes):
        unregister_class(cls)
    if registerPanel:
        dk64_panel_unregister()
