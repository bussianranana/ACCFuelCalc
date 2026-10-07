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

# wall delineator (photo 4): white plate, black diagonal band, yellow retro-reflector
x0, y0, x1, y1 = 336, 0, 432, 224
REG["delineator"] = (x0, y0, x1, y1)
pl = Image.new("RGB", (x1 - x0, y1 - y0), (238, 238, 232))
pd = ImageDraw.Draw(pl)
w_, h_ = pl.size
pd.polygon([(0, h_ * 0.22), (w_, h_ * 0.50), (w_, h_ * 0.80), (0, h_ * 0.52)], fill=(18, 18, 18))
pd.rectangle([w_ * 0.22, h_ * 0.36, w_ * 0.78, h_ * 0.66], fill=(255, 196, 0), outline=(120, 90, 0), width=2)
pd.rectangle([0, 0, w_ - 1, h_ - 1], outline=(150, 150, 150), width=3)
atlas.paste(pl, (x0, y0))

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
json.dump({"size": A, "regions": REG}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.json"), "w"))
print("ok")
