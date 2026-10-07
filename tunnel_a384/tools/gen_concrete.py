"""Tunnel lining texture: stained shotcrete with simulated seepage.

Layout: x (u) runs around the arch, 0 = left floor, 0.5 = crown, 1 = right floor.
y (v) runs along the tunnel and tiles seamlessly; one tile = one centre section.
Lining joints sit at every quarter tile, with one exactly on the tile seam. The rows
near the seam are made left/right symmetric so an end piece turned 180 deg still
lines up with the centre section.
Writes tunnel_concrete.png (albedo) and tunnel_concrete_nm.png (normal map).
"""
import os, sys, numpy as np
from PIL import Image

OUT = sys.argv[1]
W, H = 2048, 4096
rng = np.random.default_rng(7)


def fnoise(h, w, beta, seed, aniso=(1.0, 1.0), fmin=0.0):
    """Periodic fractal noise (FFT), zero mean / unit std."""
    r = np.random.default_rng(seed)
    g = r.standard_normal((h, w)).astype(np.float32)
    fy = (np.fft.fftfreq(h) * aniso[0])[:, None].astype(np.float32)
    fx = (np.fft.rfftfreq(w) * aniso[1])[None, :].astype(np.float32)
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1
    amp = 1 / f ** (beta / 2)
    if fmin:
        amp *= 1 - np.exp(-(f / fmin) ** 2)
    amp[0, 0] = 0
    n = np.fft.irfft2(np.fft.rfft2(g) * amp, s=(h, w)).astype(np.float32)
    return (n - n.mean()) / n.std()


def blur(a, sig_y, sig_x):
    """Gaussian blur, periodic in y and x (via FFT)."""
    fy = np.fft.fftfreq(a.shape[0])[:, None]
    fx = np.fft.rfftfreq(a.shape[1])[None, :]
    k = np.exp(-2 * (np.pi ** 2) * ((fy * sig_y) ** 2 + (fx * sig_x) ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * k, s=a.shape).astype(np.float32)


def warp(a, du, dv):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    y2 = (yy + dv).astype(int) % H
    x2 = np.clip(xx + du, 0, W - 1).astype(int)
    return a[y2, x2]


u = (np.arange(W, dtype=np.float32) + 0.5) / W
U = np.broadcast_to(u[None, :], (H, W))
JOINTS = [int(k * H / 4) for k in range(4)]

# ------------------------------------------------------------ height / micro detail
print("noise...")
wu, wv = fnoise(H, W, 2.6, 1) * 18, fnoise(H, W, 2.6, 2) * 18
blot = warp(fnoise(H, W, 2.4, 3), wu, wv)                 # big tonal blotches
mid = warp(fnoise(H, W, 1.7, 4), wu * 0.4, wv * 0.4)
fine = fnoise(H, W, 0.6, 5)                                # shotcrete grain
bumps = fnoise(H, W, 2.0, 6, fmin=0.01)                    # sprayed concrete lumps

# aggregate speckles
spk = np.zeros((H, W), np.float32)
n_spk = 220000
ys, xs = rng.integers(0, H, n_spk), rng.integers(0, W, n_spk)
np.add.at(spk, (ys, xs), rng.normal(0, 1, n_spk).astype(np.float32))
spk = blur(spk, 0.7, 0.7)

# lining panels: each quarter-tile ring gets its own tone, joints are grooves
panel = np.zeros(H, np.float32)
tones = rng.normal(0, 0.035, 4)
for k in range(4):
    panel[JOINTS[k]:JOINTS[k] + H // 4] = tones[k]
groove = np.zeros(H, np.float32)
for j in JOINTS + [H]:
    d = np.minimum(np.abs(np.arange(H) - j), H - np.abs(np.arange(H) - j))
    groove = np.maximum(groove, np.exp(-(d / 3.0) ** 2))
# a few horizontal pour / spray layers following the arch

# ------------------------------------------------------------ seepage simulation
print("seepage...")


def streams(n, start_u, from_joint, sig_classes, length, seed, meander=0.5):
    """Water streams crawl from their source toward the nearer floor.
    Each stream is drawn as a centre line, then blurred with its own width so
    streaks have soft edges; amplitude is width-normalised."""
    r = np.random.default_rng(seed)
    layers = {sg: np.zeros((H, W), np.float32) for sg in sig_classes}
    thin = np.zeros((H, W), np.float32)
    ends = np.zeros((H, W), np.float32)
    for _ in range(n):
        u0 = start_u(r) * W
        v0 = (r.choice(JOINTS) + r.normal(0, 10)) if r.random() < from_joint else r.uniform(0, H)
        side = 1 if (u0 > W / 2 or (abs(u0 - W / 2) < 6 and r.random() < 0.5)) else -1
        L = int(r.uniform(*length) * W)
        sg = sig_classes[r.integers(0, len(sig_classes))]
        amp = r.uniform(0.35, 1.0)
        x = u0 + side * np.arange(L)
        x = x[(x >= 0) & (x < W)]
        if len(x) < 4:
            continue
        t = np.arange(len(x)) / len(x)
        rw = np.cumsum(r.normal(0, 1, len(x)))
        k = np.hanning(min(301, len(x) - 1 - (len(x) % 2 == 0))); rw = np.convolve(rw, k / k.sum(), mode="same")
        rw = (rw - rw[0]) / (rw.std() + 1e-6)
        y = v0 + rw * r.uniform(3, 14) * meander * 2 + 2.0 * np.sin(t * r.uniform(8, 20) + r.uniform(0, 6))
        ramp = np.clip(t / r.uniform(0.04, 0.15), 0, 1) ** 2
        fade = amp * ramp * (1 - t ** r.uniform(1.5, 4)) * (0.6 + 0.4 * r.random(len(x)))
        yi, xi = y.astype(int) % H, x.astype(int)
        np.add.at(layers[sg], (yi, xi), fade * sg * 2.5)
        # fine rivulets inside the streak
        for k in range(r.integers(1, 4)):
            off = r.normal(0, sg * 0.6) + np.cumsum(r.normal(0, 0.06, len(x)))
            np.add.at(thin, ((yi + off.astype(int)) % H, xi), fade * 0.6)
        ends[yi[-1], xi[-1]] += amp
    out = np.zeros((H, W), np.float32)
    for sg, a in layers.items():
        out += blur(a, sg, 1.2)
    return out, blur(thin, 0.8, 1.0), ends


crown_start = lambda r: 0.5 + r.choice([-1, 1]) * (0.01 + abs(r.normal(0, 0.09)))
any_start = lambda r: r.uniform(0.18, 0.82)
w_a, t_a, e_a = streams(420, crown_start, 0.6, (2.5, 5, 9, 16, 26), (0.12, 0.48), 11)
w_b, t_b, e_b = streams(160, any_start, 0.25, (2, 4, 8), (0.05, 0.3), 12)
wet_raw = w_a + w_b
wet = 1 - np.exp(-wet_raw * 0.9 * (0.75 + 0.25 * np.clip(mid * 0.5 + 0.5, 0, 1)))
wet = np.clip(wet * (0.85 + 0.3 * np.clip(t_a + t_b, 0, 1)), 0, 1)
halo = 1 - np.exp(-blur(wet_raw, 30, 50) * 1.2)            # damp area around streak bundles

w_e, t_e, e_e = streams(110, crown_start, 0.5, (2, 3.5, 6), (0.04, 0.25), 21, meander=0.3)
efflo = 1 - np.exp(-(w_e * 0.9 + t_e * 0.2))
crust = 1 - np.exp(-blur(e_e + 0.5 * e_a, 5, 6) * 8)
# patchy mineral crust along joints near the crown
jpatch = np.clip((fnoise(H, W, 2.0, 40) - 0.6) * 1.5, 0, 1)
jcrust = groove[:, None] * np.exp(-((U - 0.5) / 0.22) ** 2) * jpatch
efflo = np.clip(efflo + 0.6 * crust + 0.8 * blur(jcrust.astype(np.float32), 4, 5), 0, 1)

# ------------------------------------------------------------ colour
print("colour...")
base = np.array([0.60, 0.58, 0.54], np.float32)
tone = 1 + 0.09 * blot + 0.045 * mid + 0.035 * fine + 0.03 * spk + panel[:, None]
img = base[None, None, :] * tone[..., None]
# slight hue drift: warmer and cooler patches
img[..., 0] *= 1 + 0.025 * mid
img[..., 2] *= 1 - 0.03 * mid

floor_d = np.minimum(U, 1 - U)                               # 0 at the road
grime = np.clip(1 - floor_d / 0.12, 0, 1) ** 1.3
splash = np.clip(0.5 + 0.5 * blur(fnoise(H, W, 1.0, 30), 3, 0.8), 0, 1)
img *= (1 - grime * (0.35 + 0.25 * splash))[..., None]
soot = np.exp(-((U - 0.5) / 0.16) ** 2) * (0.75 + 0.25 * blot)
img *= (1 - 0.16 * soot)[..., None]

img *= (1 - 0.22 * halo)[..., None]
seep_col = np.array([0.16, 0.17, 0.14], np.float32)
img = img + (seep_col - img) * (0.78 * wet)[..., None]
eff_col = np.array([0.86, 0.85, 0.81], np.float32)
img = img + (eff_col - img) * (0.85 * efflo * (0.7 + 0.3 * np.clip(fine * 0.5 + 0.5, 0, 1)))[..., None]
img *= (1 - 0.35 * groove)[:, None, None]

# ------------------------------------------------------------ seam symmetry band
def symmetrise(a, rows=48):
    out = a.copy()
    for dy in range(-rows, rows + 1):
        y = dy % H
        w = 0.5 * (1 - abs(dy) / rows) ** 2 * 2         # 1 at the seam -> 0 at the band edge
        w = min(1.0, w)
        mir = (a[y] + a[y, ::-1]) / 2
        out[y] = a[y] * (1 - w) + mir * w
    return out


img = symmetrise(img)
save = lambda a, n: Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, n), optimize=True)
save(img, "tunnel_concrete.png")

# ------------------------------------------------------------ normal map
print("normal...")
hgt = 0.6 * bumps + 0.25 * fine + 0.3 * spk - 3.0 * groove[:, None] + 0.5 * efflo
hgt = symmetrise(hgt[..., None])[..., 0]
dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
strength = 1.6
n = np.stack([-dx * strength, dy * strength, np.ones_like(hgt)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
save(n * 0.5 + 0.5, "tunnel_concrete_nm.png")
print("done")
