from bpy.props import StringProperty
from bpy.types import PropertyGroup

from ..rom.catalog import ACTOR, PROP, STAGE


def search_table(table: str):
    def search(_self, context, _edit_text):
        entries = context.scene.fast64.dk64.rom_catalog.entries(table)
        return [entry.name for entry in sorted(entries, key=lambda entry: entry.index)]

    return search


class DK64ImportSettings(PropertyGroup):
    actor_name: StringProperty(
        name="Actor", description="The actor to import", search=search_table(ACTOR)
    )
    prop_name: StringProperty(
        name="Prop", description="The prop to import", search=search_table(PROP)
    )
    stage_name: StringProperty(
        name="Stage", description="The stage to import", search=search_table(STAGE)
    )
