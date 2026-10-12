from bpy.path import abspath
from bpy.props import StringProperty
from bpy.types import PropertyGroup, UILayout

from ..utility import prop_split, directory_path_checks, directory_ui_warnings


class DK64ExportSettings(PropertyGroup):
    name: StringProperty(
        name="Name",
        description="The model number this model overwrites. Written to a <number> folder.",
    )
    path: StringProperty(
        name="Path",
        subtype="DIR_PATH",
        description="The folder the model's <number> folder is written.",
    )

    def get_folder(self) -> str:
        folder = abspath(self.path)
        directory_path_checks(folder)
        return folder

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "name", "Name")
        prop_split(layout, self, "path", "Path")
        directory_ui_warnings(layout, abspath(self.path))
