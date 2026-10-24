"""Headless: regenerate blender/modular_kit.blend from the addon code.

blender --background --factory-startup --python scripts/build_test_scene.py [-- preview.png]
"""
import math
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from modular_building import assemble, kit  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"

pieces = kit.generate_kit()
assemble.build_test_building(pieces, 10, 15)

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.rotation_euler = (math.radians(50), 0, math.radians(35))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.location = (-16, -24, 18)
scene.collection.objects.link(cam)
target = bpy.data.objects.new("CameraTarget", None)
target.location = (5, 7.5, 3)
scene.collection.objects.link(target)
track = cam.constraints.new("TRACK_TO")
track.target = target
scene.camera = cam

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.light = "STUDIO"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000

out_dir = os.path.join(ROOT, "blender")
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "modular_kit.blend"))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if argv:
    scene.render.filepath = argv[0]
    bpy.ops.render.render(write_still=True)
    # second shot: back corner, shows roof eaves, ridge and north gable
    cam.location = (26, 36, 18)
    scene.render.filepath = argv[0].replace(".png", "_back.png")
    bpy.ops.render.render(write_still=True)
