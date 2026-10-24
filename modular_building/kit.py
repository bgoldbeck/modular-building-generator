"""Kit piece definitions. Everything snaps to a 1 m grid.

Pivot convention (all pieces): origin is the bottom-left corner as seen from
outside the building, on the outer face. Local +X runs along the piece,
+Y points into the building, +Z is up. Floor tiles pivot on their top
surface so they land on the same Z as the walls standing on them.
"""
import bmesh
import bpy

GRID = 1.0
WALL_H = 3.0
WALL_T = 0.2
FOUND_H = 1.0
FOUND_FLARE = 0.08  # stone plinth sticks out past the wall face by this much
FLOOR_T = 0.1
TIMBER = 0.16       # full post width; each wall end carries half of it
BEAM_H = 0.18
INSET = 0.03        # plaster sits this far behind the timber faces
ROOF_T = 0.12
ROOF_D = ROOF_T * 2 ** 0.5  # vertical thickness of a 45 degree roof slab
EAVE = 0.4          # how far eave pieces overhang past the wall face

MATERIALS = {
    "MB_Plaster": (0.85, 0.80, 0.68),
    "MB_Timber": (0.22, 0.13, 0.07),
    "MB_Stone": (0.45, 0.44, 0.42),
    "MB_FloorWood": (0.45, 0.30, 0.17),
    "MB_Shingle": (0.25, 0.22, 0.20),
}


def get_material(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        color = (*MATERIALS[name], 1.0)
        mat.diffuse_color = color
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    return mat


class MeshBuilder:
    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mat(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def prism(self, poly, d0, d1, mat, plane="XZ"):
        """Extrude a 2D polygon. plane XZ extrudes along Y, YZ along X."""
        def co(u, v, d):
            return (u, d, v) if plane == "XZ" else (d, u, v)

        front = [self.bm.verts.new(co(u, v, d0)) for u, v in poly]
        back = [self.bm.verts.new(co(u, v, d1)) for u, v in poly]
        faces = [self.bm.faces.new(front), self.bm.faces.new(list(reversed(back)))]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            faces.append(self.bm.faces.new((front[i], front[j], back[j], back[i])))
        idx = self._mat(mat)
        for f in faces:
            f.material_index = idx

    def box(self, x0, y0, z0, x1, y1, z1, mat):
        self.prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, mat)

    def finish(self, name):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(get_material(m))
        return me


def _subtract(rects, hole):
    """Cut an axis-aligned hole out of a list of (x0, z0, x1, z1) rects."""
    hx0, hz0, hx1, hz1 = hole
    out = []
    for x0, z0, x1, z1 in rects:
        if hx1 <= x0 or hx0 >= x1 or hz1 <= z0 or hz0 >= z1:
            out.append((x0, z0, x1, z1))
            continue
        if hx0 > x0:
            out.append((x0, z0, hx0, z1))
        if hx1 < x1:
            out.append((hx1, z0, x1, z1))
        cx0, cx1 = max(x0, hx0), min(x1, hx1)
        if hz0 > z0:
            out.append((cx0, z0, cx1, hz0))
        if hz1 < z1:
            out.append((cx0, hz1, cx1, z1))
    return out


def _timber_wall(name, width, height, opening=None, brace=False, sill=True, mid_post=False,
                 end_posts=True):
    """Half-timbered panel: timber frame flush with both faces, plaster recessed.

    opening: (kind, x0, z0, x1, z1) with kind 'window' or 'door'.
    """
    mb = MeshBuilder()
    h = TIMBER / 2
    top = height - BEAM_H
    bottom = BEAM_H if sill else 0.0
    timbers = [(0, top, width, height)]
    if end_posts:
        timbers += [(0, 0, h, height), (width - h, 0, width, height)]
    else:
        h = 0.0
    holes = []

    if mid_post:
        timbers.append((width / 2 - h, bottom, width / 2 + h, top))

    if opening:
        kind, ox0, oz0, ox1, oz1 = opening
        f = 0.1
        holes.append((ox0, oz0, ox1, oz1))
        timbers += [(ox0 - f, oz0, ox0, oz1), (ox1, oz0, ox1 + f, oz1)]
        if oz1 < top:
            timbers.append((ox0 - f, oz1, ox1 + f, min(oz1 + f, top)))
        if kind == "window":
            timbers.append((ox0 - f, oz0 - f, ox1 + f, oz0))
            # window board sticks out a little on the outside
            mb.box(ox0 - f - 0.04, -0.05, oz0 - 0.06, ox1 + f + 0.04, 0, oz0, "MB_Timber")
            # muntin cross
            mx, mz = (ox0 + ox1) / 2, (oz0 + oz1) / 2
            mb.box(mx - 0.02, 0.08, oz0, mx + 0.02, 0.12, oz1, "MB_Timber")
            mb.box(ox0, 0.08, mz - 0.02, ox1, 0.12, mz + 0.02, "MB_Timber")

    if sill:
        sills = [(0, 0, width, BEAM_H)]
        if opening and opening[0] == "door":
            sills = _subtract(sills, holes[0])
        timbers += sills

    plaster = [(h, bottom, width - h, top)]
    for t in timbers + holes:
        plaster = _subtract(plaster, t)

    for x0, z0, x1, z1 in timbers:
        mb.box(x0, 0, z0, x1, WALL_T, z1, "MB_Timber")
    for x0, z0, x1, z1 in plaster:
        mb.box(x0, INSET, z0, x1, WALL_T - INSET, z1, "MB_Plaster")

    if brace:
        bw = 0.18
        mb.prism([(h, bottom), (h + bw, bottom), (width - h, top), (width - h - bw, top)],
                 0, WALL_T, "MB_Timber")
    return mb.finish(name)


def wall_plain(width):
    return _timber_wall(f"MB_Wall_{width}x3", width, WALL_H, mid_post=width >= 2)


def wall_brace(width):
    return _timber_wall(f"MB_Wall_{width}x3_Brace", width, WALL_H, brace=True)


def wall_window(width):
    c = width / 2
    return _timber_wall(f"MB_Wall_{width}x3_Window", width, WALL_H,
                        opening=("window", c - 0.4, 1.1, c + 0.4, 2.2))


def wall_door(width):
    c = width / 2
    return _timber_wall(f"MB_Wall_{width}x3_Door", width, WALL_H,
                        opening=("door", c - 0.5, 0.0, c + 0.5, 2.3))


def wall_corner():
    mb = MeshBuilder()
    o = 0.03
    mb.box(-o, -o, 0, WALL_T + o, WALL_T + o, WALL_H, "MB_Timber")
    return mb.finish("MB_Wall_Corner")


def foundation_wall(width):
    mb = MeshBuilder()
    mb.box(0, -FOUND_FLARE, 0, width, WALL_T, FOUND_H, "MB_Stone")
    # wider base course
    mb.box(0, -FOUND_FLARE - 0.06, 0, width, WALL_T, 0.25, "MB_Stone")
    return mb.finish(f"MB_Found_{width}x1")


def foundation_corner():
    mb = MeshBuilder()
    o = FOUND_FLARE + 0.04
    mb.box(-o, -o, 0, WALL_T + 0.1, WALL_T + 0.1, FOUND_H + 0.02, "MB_Stone")
    return mb.finish("MB_Found_Corner")


def floor_tile():
    mb = MeshBuilder()
    planks, gap = 4, 0.004
    w = GRID / planks
    for i in range(planks):
        mb.box(0, i * w + gap, -FLOOR_T, GRID, (i + 1) * w - gap, 0, "MB_FloorWood")
    return mb.finish("MB_Floor_1x1")


def gable_fill(width):
    return _timber_wall(f"MB_Gable_Fill_{width}x1", width, 1.0, sill=False, end_posts=False)


def gable_tri(side):
    """1x1 gable corner. 'L' rises left to right (left end of a gable), 'R' mirrors it."""
    mb = MeshBuilder()
    b = BEAM_H
    # top beam continues the gable fill beams; plaster fills the rest
    beam = [(1 - b, 1 - b), (1, 1 - b), (1, 1)]
    plaster = [(0, 0), (1, 0), (1, 1 - b), (1 - b, 1 - b)]
    if side == "R":
        beam = [(1 - x, z) for x, z in reversed(beam)]
        plaster = [(1 - x, z) for x, z in reversed(plaster)]
    mb.prism(beam, 0, WALL_T, "MB_Timber")
    mb.prism(plaster, INSET, WALL_T - INSET, "MB_Plaster")
    return mb.finish(f"MB_Gable_Tri_{side}")


def roof_slope(length, eave=False):
    """45 degree slab. Local X runs along the ridge, it rises 1 m over 1 m of +Y.
    Pivot sits on the slab underside at the wall's outer top edge."""
    mb = MeshBuilder()
    s = -EAVE if eave else 0.0
    mb.prism([(s, s), (1, 1), (1, 1 + ROOF_D), (s, s + ROOF_D)], 0, length, "MB_Shingle", plane="YZ")
    return mb.finish(f"MB_Roof_{'Eave' if eave else 'Slope'}_{length}")


def roof_ridge(length):
    """Chevron cap. Pivot on the ridge line where the two slab undersides meet."""
    mb = MeshBuilder()
    a, w, t = ROOF_D + 0.01, 0.3, 0.1
    mb.prism([(-w, a - w), (0, a), (w, a - w), (w, a - w + t), (0, a + t), (-w, a - w + t)],
             0, length, "MB_Timber", plane="YZ")
    return mb.finish(f"MB_Roof_Ridge_{length}")


PIECES = [
    lambda: wall_plain(1), lambda: wall_plain(2), lambda: wall_brace(2),
    lambda: wall_window(2), lambda: wall_door(2), wall_corner,
    lambda: foundation_wall(1), lambda: foundation_wall(2), foundation_corner,
    floor_tile,
    lambda: gable_fill(1), lambda: gable_fill(2), lambda: gable_tri("L"), lambda: gable_tri("R"),
    lambda: roof_slope(1), lambda: roof_slope(2),
    lambda: roof_slope(1, eave=True), lambda: roof_slope(2, eave=True),
    lambda: roof_ridge(1), lambda: roof_ridge(2),
]


def generate_kit(collection_name="MB_Kit", spacing=3.0, row_y=-10.0):
    """Build every kit piece once and lay them out in a row for browsing.
    Returns {mesh name: object}."""
    coll = bpy.data.collections.get(collection_name)
    if coll is None:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)
    kit = {}
    for i, build in enumerate(PIECES):
        me = build()
        obj = bpy.data.objects.new(me.name, me)
        obj.location = (i * spacing, row_y, 0)
        coll.objects.link(obj)
        kit[me.name] = obj
    return kit
