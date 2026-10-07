"""Procedural textures for the A-384 style tunnel string object."""
import sys, os, numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(384)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def fnoise(h, w, beta=2.0, seed=0, aniso=(1.0, 1.0)):
    """Seamless (periodic) fractal noise via FFT filtering, normalised to 0..1."""
    r = np.random.default_rng(seed)
    g = r.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None] * aniso[0]
    fx = np.fft.fftfreq(w)[None, :] * aniso[1]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1.0
    spec = np.fft.fft2(g) / f ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    n -= n.min()
    return n / n.max()


def save(arr, name):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name))


# ---------------------------------------------------------------- concrete
# u (image x) runs around the arch: 0 = left floor, 0.5 = crown, 1 = right floor.
# v (image y) runs along the tunnel and tiles seamlessly.
W = H = 2048
base = np.array([128, 118, 102], float)                     # warm grey/brown lining
n1 = fnoise(H, W, 2.2, 1)
n2 = fnoise(H, W, 1.2, 2)
img = base[None, None, :] * (0.78 + 0.32 * n1[..., None]) * (0.92 + 0.16 * n2[..., None])

# shotcrete speckle
speck = rng.random((H, W))
img *= (0.93 + 0.07 * speck)[..., None]

u = np.linspace(0, 1, W)[None, :]
# traffic grime: darker towards the road on both sides
floor = np.clip(1 - np.minimum(u, 1 - u) / 0.13, 0, 1) ** 1.5
img *= (1 - 0.45 * floor)[..., None]
# soot band near the crown
crown = np.exp(-((u - 0.5) / 0.18) ** 2)
img *= (1 - 0.18 * crown)[..., None]


def streak_mask(count, width_px, seed, white):
    """Seepage streaks starting near the crown and running down the arch (along u).
    Most start at lining joints, where water actually gets through."""
    r = np.random.default_rng(seed)
    m = Image.new("L", (W, H * 3), 0)
    d = ImageDraw.Draw(m)
    for _ in range(count):
        side = r.choice([-1, 1])
        x0 = 0.5 + side * abs(r.normal(0, 0.09))
        length = r.uniform(0.12, 0.46) * (0.7 if white else 1.0)
        if r.random() < 0.65:
            y = (r.integers(0, 4) * H / 4 + r.normal(0, 22)) % H
        else:
            y = r.uniform(0, H)
        steps = 40
        drift = r.normal(0, 18)
        freq, ph = r.uniform(1, 3), r.uniform(0, 6)
        pts = []
        for s in range(steps + 1):
            t = s / steps
            pts.append(((x0 + side * length * t) * W, y + drift * t + 4 * np.sin(t * freq * 6.28 + ph)))
        wpx = r.uniform(0.4, 1.6) * width_px
        val = int(r.uniform(90, 255))
        for off in (0, H, 2 * H):                 # draw in 3 tiles -> wraps in v
            for s in range(steps):
                t = s / steps
                w_ = max(1, int(wpx * (1 - 0.7 * t)))
                v_ = int(val * (1 - 0.6 * t))
                (ax, ay), (bx, by) = pts[s], pts[s + 1]
                d.line([(ax, ay + off), (bx, by + off)], fill=v_, width=w_)
    m = m.filter(ImageFilter.GaussianBlur(width_px * 0.4))
    a = np.asarray(m, float)[H:2 * H] / 255.0
    return a


dark = streak_mask(200, 22, 10, False) * (0.4 + 0.6 * n2)
whit = streak_mask(170, 15, 11, True) * (0.4 + 0.6 * fnoise(H, W, 1.6, 3))
img = img * (1 - 0.7 * np.clip(dark, 0, 1)[..., None])
img = img + (np.array([235, 232, 222])[None, None, :] - img) * (0.92 * np.clip(whit * 1.3, 0, 1))[..., None]

# lining construction joints across the tunnel every quarter tile (~2.5 m)
for k in range(4):
    yj = int(k * H / 4)
    for dy in range(-3, 4):
        img[(yj + dy) % H] *= 0.78 + 0.06 * abs(dy)
# subtle formwork board lines along the arch
for k in range(0, H, 64):
    img[k % H] *= 0.97

save(img, "tunnel_concrete.png")

# ---------------------------------------------------------------- green railing paint
S = 256
nn = fnoise(S, S, 1.8, 20)
rail = np.array([22, 128, 108], float)[None, None, :] * (0.85 + 0.25 * nn[..., None])
dirt = fnoise(S, S, 2.5, 21)
rail = rail * (1 - 0.35 * np.clip((dirt - 0.6) * 3, 0, 1))[..., None]
save(rail, "tunnel_rail_green.png")

# ---------------------------------------------------------------- lamp housing (aluminium)
alu = np.array([150, 152, 150], float)[None, None, :] * (0.85 + 0.2 * fnoise(S, S, 1.0, 30, (0.1, 1))[..., None])
alu = alu * (1 - 0.3 * fnoise(S, S, 2.2, 31))[..., None]
save(alu, "tunnel_lamp_body.png")

# ---------------------------------------------------------------- lamp lens (emissive)
lens = Image.new("RGB", (S, S), (255, 226, 170))
d = ImageDraw.Draw(lens)
d.rectangle([0, 0, S - 1, S - 1], outline=(120, 110, 90), width=10)
for i in range(1, 4):                               # prismatic lens ribs
    x = i * S // 4
    d.line([(x, 0), (x, S)], fill=(235, 205, 150), width=4)
lens = lens.filter(ImageFilter.GaussianBlur(1.2))
lens.save(os.path.join(OUT, "tunnel_lamp_lens.png"))

# ---------------------------------------------------------------- signs atlas
A = 1024
atlas = Image.new("RGB", (A, A), (128, 130, 128))
d = ImageDraw.Draw(atlas)
REG = {}

# chevron / edge-marker panel (black-white diagonal stripes)
x0, y0, x1, y1 = 0, 0, 320, 1024
REG["chevron"] = (x0, y0, x1, y1)
panel = Image.new("RGB", (x1 - x0, y1 - y0), (245, 245, 240))
pd = ImageDraw.Draw(panel)
pw, ph = panel.size
step = 150
for k in range(-12, 20):
    c = k * step
    poly = [(0, c), (pw, c + pw * 0.75), (pw, c + pw * 0.75 + step / 2), (0, c + step / 2)]
    pd.polygon(poly, fill=(18, 18, 18))
pd.rectangle([0, 0, pw - 1, ph - 1], outline=(70, 70, 70), width=8)
atlas.paste(panel, (x0, y0))

# wall delineator (white with black band + amber retro-reflector)
x0, y0, x1, y1 = 336, 0, 432, 336
REG["delineator"] = (x0, y0, x1, y1)
d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(240, 240, 235))
d.rectangle([x0, y0 + 130, x1 - 1, y0 + 220], fill=(20, 20, 20))
d.rectangle([x0 + 18, y0 + 26, x1 - 19, y0 + 96], fill=(255, 170, 30))
d.rectangle([x0 + 18, y0 + 250, x1 - 19, y0 + 310], fill=(235, 235, 235), outline=(160, 160, 160), width=4)

# red SOS / extinguisher plate
x0, y0, x1, y1 = 448, 0, 640, 256
REG["sos"] = (x0, y0, x1, y1)
d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(200, 20, 20))
d.rectangle([x0 + 8, y0 + 8, x1 - 9, y1 - 9], outline=(240, 240, 240), width=6)
f = ImageFont.truetype(FONT, 64)
d.text(((x0 + x1) / 2, (y0 + y1) / 2), "SOS", font=f, fill=(250, 250, 250), anchor="mm")

# green tunnel identification plate
x0, y0, x1, y1 = 656, 0, 1024, 184
REG["green"] = (x0, y0, x1, y1)
d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, 120, 70))
d.rectangle([x0 + 8, y0 + 8, x1 - 9, y1 - 9], outline=(245, 245, 245), width=6)
d.text(((x0 + x1) / 2, y0 + 62), "TÚNEL", font=ImageFont.truetype(FONT, 66), fill=(250, 250, 250), anchor="mm")
d.text(((x0 + x1) / 2, y0 + 136), "A-384", font=ImageFont.truetype(FONT, 50), fill=(250, 250, 250), anchor="mm")

# solid helpers
REG["grey"] = (336, 352, 640, 512)
d.rectangle(REG["grey"], fill=(140, 142, 140))
REG["black"] = (656, 200, 1024, 360)
d.rectangle(REG["black"], fill=(22, 22, 22))
REG["white"] = (656, 380, 1024, 520)
d.rectangle(REG["white"], fill=(235, 235, 230))
atlas.save(os.path.join(OUT, "tunnel_signs.png"))

import json
json.dump({"size": A, "regions": REG}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.json"), "w"), indent=1)
print("ok")
