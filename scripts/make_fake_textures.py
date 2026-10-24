"""Write a stand-in texture library laid out like Quixel Mixer exports, for
testing the texture hookup without the real library.

python scripts/make_fake_textures.py [out_dir] [--size 512]

Each set lands in <out_dir>/Fake_<Name>/Fake_<Name>_{Albedo,Normal,Roughness,AO,
Displacement}.png. All maps tile seamlessly. Point the addon at out_dir, or run
the test scene with MB_TEXTURE_DIR=<out_dir>. Needs only numpy.
"""
import argparse
import os
import struct
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_png(path, img):
    """img: HxW or HxWx3 floats in 0..1."""
    a = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    if a.ndim == 2:
        a = a[..., None].repeat(3, axis=2)
    h, w, _ = a.shape
    raw = b"".join(b"\0" + a[y].tobytes() for y in range(h))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))


class Gen:
    def __init__(self, size, seed):
        self.n = size
        self.rng = np.random.default_rng(seed)
        y, x = np.mgrid[0:size, 0:size] / size
        self.u, self.v = x, 1 - y  # v up, like UVs

    def noise(self, scale, sx=1.0, sy=1.0):
        """Tileable noise, features roughly 1/scale of the tile. sx/sy stretch it."""
        f = np.fft.fftfreq(self.n) * self.n
        fx, fy = np.meshgrid(f * sx, f * sy)
        spectrum = np.exp(-(fx ** 2 + fy ** 2) / (2 * scale ** 2))
        white = np.fft.fft2(self.rng.standard_normal((self.n, self.n)))
        out = np.real(np.fft.ifft2(white * spectrum))
        return (out - out.min()) / (out.max() - out.min())

    def cells(self, rows, cols, stagger=0.5):
        """Running-bond grid. Returns (cell id, distance to nearest joint in cell units)."""
        r = self.v * rows
        c = self.u * cols + stagger * np.floor(r)
        ri, ci = np.floor(r), np.floor(c) % cols
        dist = np.minimum.reduce([r - ri, ri + 1 - r, (c - np.floor(c)) * rows / cols,
                                  (np.floor(c) + 1 - c) * rows / cols])
        return (ri * cols + ci).astype(int), dist

    def per_cell(self, ids):
        return self.rng.random(ids.max() + 1)[ids]


def tint(base, amount, *layers):
    base = np.array(base)
    shade = sum(layers) / len(layers)
    return base * (1 - amount / 2 + amount * shade)[..., None]


def plaster(g):
    h = 0.6 * g.noise(6) + 0.4 * g.noise(60)
    albedo = tint((0.86, 0.81, 0.70), 0.25, g.noise(3), h)
    return albedo, h, 0.75 + 0.2 * g.noise(40)


def wood_grain(g, lines):
    """Grain lines running along U, warped and streaked so they don't look ruled."""
    warp = g.noise(3) * 2 + g.noise(10) * 0.5
    rings = 0.5 + 0.5 * np.sin(2 * np.pi * (g.v * lines + warp))
    return 0.75 * rings + 0.25 * g.noise(80, sx=10)


def timber(g):
    rings = wood_grain(g, 12)
    h = 0.7 * rings + 0.3 * g.noise(80)
    albedo = tint((0.26, 0.15, 0.08), 0.6, rings, g.noise(4))
    return albedo, h, 0.6 + 0.3 * rings


def stone(g):
    ids, dist = g.cells(rows=6, cols=4)
    mortar = np.clip(dist / 0.08, 0, 1)
    block = g.per_cell(ids)
    h = mortar * (0.7 + 0.3 * g.noise(30))
    color = tint((0.48, 0.47, 0.44), 0.5, block, g.noise(25))
    albedo = color * mortar[..., None] + np.array((0.35, 0.33, 0.30)) * (1 - mortar[..., None])
    return albedo, h, 0.85 + 0.1 * (1 - mortar)


def floorwood(g):
    # 4 planks per metre run along U, matching the floor tile mesh
    ids, dist = g.cells(rows=4, cols=1, stagger=0.37)
    seam = np.clip(dist / 0.03, 0, 1)
    grain = wood_grain(g, 24)
    plank = g.per_cell(ids)
    h = seam * (0.6 + 0.4 * grain)
    albedo = tint((0.47, 0.31, 0.18), 0.5, plank, grain) * (0.4 + 0.6 * seam)[..., None]
    return albedo, h, 0.55 + 0.3 * grain


def shingle(g):
    # 2 m tile: 10 rows of 0.2 m, 8 shingles of 0.25 m per row
    ids, dist = g.cells(rows=10, cols=8)
    gap = np.clip(dist / 0.06, 0, 1)
    row_t = (g.v * 10) % 1  # 0 at bottom edge of a row, which overlaps the row below
    h = gap * (0.4 + 0.6 * row_t) * (0.8 + 0.2 * g.noise(40))
    albedo = tint((0.27, 0.24, 0.22), 0.6, g.per_cell(ids), g.noise(20)) * (0.5 + 0.5 * gap)[..., None]
    return albedo, h, 0.8 + 0.15 * g.noise(30)


SETS = {"Plaster": plaster, "Timber": timber, "Stone": stone,
        "FloorWood": floorwood, "Shingle": shingle}


def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * strength  # +Y up (OpenGL)
    n = np.dstack([-dx, -dy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def ambient_occlusion(h):
    blur = h.copy()
    for _ in range(6):
        blur = (blur + np.roll(blur, 1, 0) + np.roll(blur, -1, 0)
                + np.roll(blur, 1, 1) + np.roll(blur, -1, 1)) / 5
    return np.clip(1 - 2 * (blur - h), 0.3, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default=os.path.join(ROOT, "test_textures"))
    ap.add_argument("--size", type=int, default=512)
    args = ap.parse_args()

    for i, (name, make) in enumerate(SETS.items()):
        g = Gen(args.size, seed=i)
        albedo, height, rough = make(g)
        set_name = f"Fake_{name}"
        d = os.path.join(args.out_dir, set_name)
        os.makedirs(d, exist_ok=True)
        maps = {
            "Albedo": albedo,
            "Normal": normal_from_height(height, args.size / 64),
            "Roughness": rough,
            "AO": ambient_occlusion(height),
            "Displacement": height,
        }
        for kind, img in maps.items():
            write_png(os.path.join(d, f"{set_name}_{kind}.png"), img)
        print(f"wrote {d}")


if __name__ == "__main__":
    main()
