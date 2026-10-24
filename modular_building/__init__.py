bl_info = {
    "name": "Modular Building Generator",
    "author": "bgoldbeck",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Modular",
    "description": "Generate a modular medieval building kit and assemble buildings from it",
    "category": "Add Mesh",
}

import bpy

from . import assemble, kit, textures


class MBG_OT_generate(bpy.types.Operator):
    bl_idname = "mbg.generate_test_building"
    bl_label = "Generate Kit + Test Building"
    bl_options = {"REGISTER", "UNDO"}

    width: bpy.props.IntProperty(name="Width", default=10, min=2, step=2)
    depth: bpy.props.IntProperty(name="Depth", default=15, min=1)

    def execute(self, context):
        if self.width % 2:
            self.report({"ERROR"}, "Width must be even (roof ridge sits on the grid)")
            return {"CANCELLED"}
        textures.clear_cache()
        pieces = kit.generate_kit()
        assemble.build_test_building(pieces, self.width, self.depth)
        return {"FINISHED"}


class MBG_OT_reload_textures(bpy.types.Operator):
    bl_idname = "mbg.reload_textures"
    bl_label = "Reload Textures"
    bl_description = "Rebuild kit materials from the texture library"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = kit.refresh_materials()
        self.report({"INFO"}, f"{n} of {len(kit.MATERIALS)} materials textured from "
                              f"{textures.library_dir()}")
        return {"FINISHED"}


class MBG_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    texture_dir: bpy.props.StringProperty(
        name="Texture Library",
        description="Folder of Quixel Mixer exports (MB_TEXTURE_DIR overrides this)",
        subtype="DIR_PATH",
        default=textures.DEFAULT_DIR,
    )

    def draw(self, context):
        self.layout.prop(self, "texture_dir")


class MBG_PT_panel(bpy.types.Panel):
    bl_label = "Modular Building"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Modular"

    def draw(self, context):
        self.layout.operator(MBG_OT_generate.bl_idname)
        self.layout.operator(MBG_OT_reload_textures.bl_idname)


classes = (MBG_OT_generate, MBG_OT_reload_textures, MBG_Preferences, MBG_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
