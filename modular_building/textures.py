"""Hook Quixel Mixer texture exports up to the kit materials.

Mixer exports one image per map, named like `<Name>_Albedo.png`,
`<Name>_Normal.png`, `<Name>_Roughness.png`. We look through the texture
library (and up to two folder levels below it) for files whose path mentions
one of a material's keywords, then sort them by map suffix. Anything missing
just falls back to the flat colour from kit.MATERIALS.

Library location, first hit wins: the MB_TEXTURE_DIR environment variable,
the addon preference, DEFAULT_DIR.
"""
import os

import bpy

DEFAULT_DIR = r"\\RANDO_NEWPC\6TB Drive\quixel mixer"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr"}
SCAN_DEPTH = 2

# material -> (path keywords, metres covered by one texture tile)
TEXTURE_SETS = {
    "MB_Plaster": (("plaster",), 2.0),
    "MB_Timber": (("timber", "beam"), 1.0),
    "MB_Stone": (("stone", "cobble", "rock"), 2.0),
    "MB_FloorWood": (("floorwood", "floor", "plank"), 1.0),
    "MB_Shingle": (("shingle", "roof"), 2.0),
}

# map -> filename suffixes Mixer (and friends) use for it
MAP_SUFFIXES = {
    "albedo": ("albedo", "basecolor", "base_color", "diffuse", "color", "col"),
    "normal": ("normal", "nrm", "nor"),
    "roughness": ("roughness", "rough"),
    "ao": ("ao", "ambientocclusion", "occlusion"),
    "metalness": ("metalness", "metallic", "metal"),
    "displacement": ("displacement", "height", "disp"),
}


def library_dir():
    env = os.environ.get("MB_TEXTURE_DIR")
    if env:
        return env
    addon = bpy.context.preferences.addons.get(__package__)
    if addon and addon.preferences.texture_dir:
        return bpy.path.abspath(addon.preferences.texture_dir)
    return DEFAULT_DIR


def _scan(root):
    """Image files under root (as paths relative to it), at most SCAN_DEPTH folders down."""
    if not os.path.isdir(root):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        if (0 if rel == "." else rel.count(os.sep) + 1) >= SCAN_DEPTH:
            dirnames[:] = []
        found += [os.path.normpath(os.path.join(rel, f)) for f in filenames
                  if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
    return sorted(found)


def _map_type(path):
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    tail = stem.replace("-", "_").replace(" ", "_").rsplit("_", 1)[-1]
    for kind, suffixes in MAP_SUFFIXES.items():
        if tail in suffixes:
            return kind
    return None


def find_maps(mat_name, files):
    """{map type: path} for the first keyword that has an albedo."""
    keywords, _ = TEXTURE_SETS[mat_name]
    for kw in keywords:
        maps = {}
        for f in files:
            if kw in f.lower().replace(" ", ""):
                kind = _map_type(f)
                if kind and kind not in maps:
                    maps[kind] = f
        if "albedo" in maps:
            return maps
    return {}


def _image(path, color):
    img = bpy.data.images.load(path, check_existing=True)
    if not color:
        img.colorspace_settings.is_data = True
    return img


def apply(mat, maps, tile):
    """Wire image maps into mat's Principled BSDF. Kit meshes carry metre-scale
    box-projected UVs, so a Mapping node scales them to the tile size."""
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1 / tile, 1 / tile, 1 / tile)
    nt.links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    uv.location, mapping.location = (-1100, 0), (-900, 0)

    def tex(kind, y):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = _image(maps[kind], kind == "albedo")
        node.location = (-650, y)
        nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    albedo = tex("albedo", 300)
    color_out = albedo.outputs["Color"]
    if "ao" in maps:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.location = (-350, 300)
        nt.links.new(color_out, mix.inputs["A"])
        nt.links.new(tex("ao", 600).outputs["Color"], mix.inputs["B"])
        color_out = mix.outputs["Result"]
    nt.links.new(color_out, bsdf.inputs["Base Color"])
    # workbench "Texture" colouring shows the active image node
    nt.nodes.active = albedo

    if "roughness" in maps:
        nt.links.new(tex("roughness", 0).outputs["Color"], bsdf.inputs["Roughness"])
    if "metalness" in maps:
        nt.links.new(tex("metalness", -300).outputs["Color"], bsdf.inputs["Metallic"])
    if "normal" in maps:
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.location = (-350, -600)
        nt.links.new(tex("normal", -600).outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])


_files_cache = {}


def texture_material(mat, name):
    """Apply library textures to mat if any match. Returns True if it did."""
    if name not in TEXTURE_SETS:
        return False
    root = library_dir()
    if root not in _files_cache:
        _files_cache[root] = _scan(root)
    maps = find_maps(name, _files_cache[root])
    if not maps:
        return False
    apply(mat, {k: os.path.join(root, p) for k, p in maps.items()}, TEXTURE_SETS[name][1])
    return True


def clear_cache():
    _files_cache.clear()
