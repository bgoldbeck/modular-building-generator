"""Assemble buildings from kit pieces as linked duplicates (shared mesh data)."""
from math import radians

import bpy

from . import kit as K

# rotation -> unit vector of local +X in world
_DIRS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}


def _segments(length):
    """Split an edge into 2 m pieces, with a 1 m piece for any odd remainder."""
    return [2] * (length // 2) + [1] * (length % 2)


def _sub_collection(parent, name):
    coll = bpy.data.collections.new(name)
    parent.children.link(coll)
    return coll


def build_test_building(kit, width=10, depth=15, origin=(0.0, 0.0, 0.0), name="TestBuilding"):
    """Rectangular one-storey house: foundation, floor, walls, gables, gable roof.

    width runs along X (gable ends), depth along Y (ridge). width must be even.
    """
    root = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(root)
    colls = {n: _sub_collection(root, f"{name}_{n}")
             for n in ("Foundation", "Floor", "Walls", "Roof")}
    ox, oy, oz = origin

    def place(piece, coll, x, y, z, rot):
        src = kit[piece]
        obj = bpy.data.objects.new(piece, src.data)
        obj.location = (ox + x, oy + y, oz + z)
        obj.rotation_euler.z = radians(rot)
        coll.objects.link(obj)

    wall_z = K.FOUND_H
    top_z = K.FOUND_H + K.WALL_H
    # counter-clockwise seen from above, so every piece's +Y points inside
    edges = [("S", (0, 0), 0, width), ("E", (width, 0), 90, depth),
             ("N", (width, depth), 180, width), ("W", (0, depth), 270, depth)]

    for side, (sx, sy), rot, length in edges:
        dx, dy = _DIRS[rot]
        place("MB_Found_Corner", colls["Foundation"], sx, sy, 0, rot)
        place("MB_Wall_Corner", colls["Walls"], sx, sy, wall_z, rot)

        segs = _segments(length)
        door_at = len(segs) // 2 if side == "S" else -1
        s = 0
        for i, w in enumerate(segs):
            x, y = sx + dx * s, sy + dy * s
            place(f"MB_Found_{w}x1", colls["Foundation"], x, y, 0, rot)
            if i == door_at:
                wall = "MB_Wall_2x3_Door"
            elif w == 1:
                wall = "MB_Wall_1x3"
            elif i % 2 == 0:
                wall = "MB_Wall_2x3_Window"
            else:
                wall = "MB_Wall_2x3_Brace" if side in ("S", "W") else "MB_Wall_2x3"
            place(wall, colls["Walls"], x, y, wall_z, rot)
            s += w

        if side in ("S", "N"):
            # gable: one row per metre of rise, 1x1 triangles at each end
            for k in range(width // 2):
                place("MB_Gable_Tri_L", colls["Walls"], sx + dx * k, sy, top_z + k, rot)
                s = k + 1
                for w in _segments(width - 2 * (k + 1)):
                    place(f"MB_Gable_Fill_{w}x1", colls["Walls"], sx + dx * s, sy, top_z + k, rot)
                    s += w
                place("MB_Gable_Tri_R", colls["Walls"], sx + dx * s, sy, top_z + k, rot)

    floor_z = K.FOUND_H
    for i in range(width):
        for j in range(depth):
            place("MB_Floor_1x1", colls["Floor"], i, j, floor_z, 0)

    run = width // 2
    y = 0
    for w in _segments(depth):
        for k in range(run):
            piece = f"MB_Roof_{'Eave' if k == 0 else 'Slope'}_{w}"
            place(piece, colls["Roof"], k, y + w, top_z + k, 270)          # west slope
            place(piece, colls["Roof"], width - k, y, top_z + k, 90)       # east slope
        place(f"MB_Roof_Ridge_{w}", colls["Roof"], run, y, top_z + run, 90)
        y += w
    return root
