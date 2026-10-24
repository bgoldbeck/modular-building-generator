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

from . import assemble, kit


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
        pieces = kit.generate_kit()
        assemble.build_test_building(pieces, self.width, self.depth)
        return {"FINISHED"}


class MBG_PT_panel(bpy.types.Panel):
    bl_label = "Modular Building"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Modular"

    def draw(self, context):
        self.layout.operator(MBG_OT_generate.bl_idname)


classes = (MBG_OT_generate, MBG_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
