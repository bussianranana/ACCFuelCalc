"""Dress the A-384 tunnel pieces (end/portal piece and repeating centre piece).

    python3 build2.py end    tunnel.fbx        tunnel_end_a384.fbx    atlas.json
    python3 build2.py center tunnel_center.fbx tunnel_center_a384.fbx atlas.json

Source geometry is read with Assimp with all node transforms baked in, so the
output is flat: one root-level object per part, identity transforms, same
units (inches, UnitScaleFactor 2.54) and axes as the 3ds Max export
(X across, Y up, Z along the tunnel).

Seamless layout
---------------
The centre piece runs Z = -726.99 .. 0.83 (length L). The end piece barrel
starts at Z = 0 and the portal is at +Z. Everything is placed by its distance
d from the seam the piece shares with the next centre piece:
    centre:  z = 0.83 - d          (d = 0 .. L)
    end:     z = d
Concrete UV v = d / L, so v is a whole number on every seam. Lights,
delineators and cable hooks use spacings that divide L, so the rhythm carries
across centre/centre and centre/end joints, including an end piece turned 180 deg.
"""
import sys, json, numpy as np, assimp_py as A

PIECE, SRC, DST, ATLAS = sys.argv[1:5]
assert PIECE in ("end", "center")
atlas = json.load(open(ATLAS))

R_IN = 137.48                 # inner lining radius (arch centre at x=0, y=0)
C_HI, C_LO = 0.83, -726.99    # centre piece seam planes
L = C_HI - C_LO               # 727.82" = 18.49 m


def z_of(d):
    return C_HI - d if PIECE == "center" else d


def d_of(z):
    return C_HI - z if PIECE == "center" else z


# ------------------------------------------------------------------ mesh helper
class Mesh:
    def __init__(self, name, mat):
        self.name, self.mat = name, mat
        self.v, self.tris, self.uv, self.n = [], [], [], []

    def tri(self, p, uv, hint=None, normals=None):
        p = [np.asarray(q, float) for q in p]
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        flip = hint is not None and np.dot(nrm, hint) < 0
        if flip:
            p, uv = [p[0], p[2], p[1]], [uv[0], uv[2], uv[1]]
            nrm = -nrm
            if normals is not None:
                normals = [normals[0], normals[2], normals[1]]
        nrm = nrm / (np.linalg.norm(nrm) + 1e-12)
        b = len(self.v)
        self.v += p
        self.tris.append((b, b + 1, b + 2))
        self.uv += list(uv)
        self.n += list(normals) if normals is not None else [nrm] * 3

    def quad(self, p, uv, hint=None, normals=None):
        self.tri([p[0], p[1], p[2]], [uv[0], uv[1], uv[2]], hint,
                 None if normals is None else [normals[0], normals[1], normals[2]])
        self.tri([p[0], p[2], p[3]], [uv[0], uv[2], uv[3]], hint,
                 None if normals is None else [normals[0], normals[2], normals[3]])

    def weld(self):
        key, newv, remap = {}, [], []
        for p in self.v:
            k = tuple(np.round(p, 4))
            if k not in key:
                key[k] = len(newv)
                newv.append(p)
            remap.append(key[k])
        self.v = newv
        self.tris = [tuple(remap[i] for i in t) for t in self.tris]


def region_uv(name, flip_u=False):
    x0, y0, x1, y1 = atlas["regions"][name]
    S = atlas["size"]
    u0, u1, v0, v1 = x0 / S, x1 / S, 1 - y1 / S, 1 - y0 / S
    if flip_u:
        u0, u1 = u1, u0
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def solid(name):
    q = region_uv(name)
    c = ((q[0][0] + q[1][0]) / 2, (q[0][1] + q[2][1]) / 2)
    return [c] * 4


def box(m, c, ax, ay, az, h, front=None, front_uv=None, other_uv=None, tile=None):
    """Oriented box; `front`=(axis, sign) face gets front_uv (u along next axis, v the one after)."""
    c = np.asarray(c, float)
    axes = [np.asarray(a, float) for a in (ax, ay, az)]
    for i in range(3):
        for s in (-1, 1):
            j, k = (i + 1) % 3, (i + 2) % 3
            fc = c + s * h[i] * axes[i]
            a, b = axes[j] * h[j], axes[k] * h[k]
            pts = [fc - a - b, fc + a - b, fc + a + b, fc - a + b]
            if front is not None and (i, s) == front:
                uv = front_uv
            elif tile is not None:
                uv = tile(h[j], h[k])
            else:
                uv = other_uv
            if np.dot(np.cross(axes[j], axes[k]), s * axes[i]) < 0:
                pts = [pts[1], pts[0], pts[3], pts[2]]
                uv = [uv[1], uv[0], uv[3], uv[2]]
            m.quad(pts, uv, hint=s * axes[i])


def frame(theta_deg, side):
    """Radial-out and up-the-wall unit vectors at angle theta from the crown."""
    t = np.radians(theta_deg)
    return (np.array([side * np.sin(t), np.cos(t), 0.0]),
            np.array([-side * np.cos(t), np.sin(t), 0.0]))


X, Y, Z = np.eye(3)

# ------------------------------------------------------------------ source geometry
scene = A.import_file(SRC, A.Process_Triangulate | A.Process_PreTransformVertices)
meshes = {}
shell_pts = []
for sm in scene.meshes:
    mname = scene.materials[sm.material_index]["NAME"]
    V = np.asarray(sm.vertices, float).reshape(-1, 3)
    N = np.asarray(sm.normals, float).reshape(-1, 3)
    UVs = np.asarray(sm.texcoords[0], float).reshape(len(V), -1)[:, :2] if sm.texcoords else np.zeros((len(V), 2))
    F = np.asarray(sm.indices).reshape(-1, 3)
    if mname == "Material #25":
        m = meshes.setdefault("tunnel_shell", Mesh("tunnel_shell", "tunnel_concrete"))
        shell_pts.append(V)
        for f in F:
            P = V[f]
            n = np.cross(P[1] - P[0], P[2] - P[0]); n /= np.linalg.norm(n) + 1e-12
            cxy = P[:, :2].mean(0); rh = np.array([*cxy / (np.linalg.norm(cxy) + 1e-9), 0])
            uv = []
            for q in P:
                if abs(np.dot(n, rh)) > 0.55:           # lining surfaces: cylindrical
                    uv.append((0.5 + np.arctan2(q[0], q[1]) / np.pi, d_of(q[2]) / L))
                else:                                    # caps / portal cut: planar
                    ax = np.argmax(np.abs(n))
                    if ax == 2:
                        uv.append((0.5 + q[0] / (np.pi * R_IN), q[1] / L))
                    elif ax == 0:
                        uv.append((d_of(q[2]) / (np.pi * R_IN), q[1] / L))
                    else:
                        uv.append((0.5 + q[0] / (np.pi * R_IN), d_of(q[2]) / L))
            m.tri(list(P), uv, normals=list(N[f]))
    elif mname == "Material #27":
        m = meshes.setdefault("tunnel_handrail", Mesh("tunnel_handrail", "tunnel_rail_green"))
        for f in F:
            m.tri(list(V[f]), list(UVs[f]), normals=list(N[f]))
    else:
        print("dropping source part with", mname, "(old light fixtures)")

SV = np.vstack(shell_pts)
SR = np.hypot(SV[:, 0], SV[:, 1])
STH = np.degrees(np.arctan2(np.abs(SV[:, 0]), SV[:, 1]))


def max_d(theta, tol=3.0):
    """How far into this piece the inner lining exists at this wall angle."""
    if PIECE == "center":
        return L + 100.0          # full length; dressing is clipped by its own step count
    m = (np.abs(STH - theta) < tol) & (SR < R_IN + 2)
    return d_of(SV[m, 2]).max()


def M(name, mat):
    return meshes.setdefault(name, Mesh(name, mat))


full = [(0, 0), (1, 0), (1, 1), (0, 1)]

# ------------------------------------------------------------------ luminaires
LIGHT_THETA, LIGHT_R = 48.06, 133.35        # from the author's light nulls
LIGHT_STEP = L / 3                           # 3 per wall per centre piece, ~6.2 m
HL, HW = 6.0, 5.5                            # half length (along tunnel) / half width (up the wall)
light_ds = [LIGHT_STEP / 2 + k * LIGHT_STEP for k in range(3)]
light_ds = [d for d in light_ds if d + HL + 8 < max_d(LIGHT_THETA)]
body = M("tunnel_light_body", "tunnel_lamp_body")
for side in (1, -1):
    rad, up = frame(LIGHT_THETA, side)
    for i, d in enumerate(light_ds):
        z = z_of(d)
        lens = M("tunnel_light_lens_%s%02d" % ("R" if side > 0 else "L", i + 1), "tunnel_lamp_lens")
        back_r, front_r = R_IN + 1.0, LIGHT_R + 0.6
        box(body, rad * (back_r + front_r) / 2 + Z * z, -rad, up, Z,
            ((back_r - front_r) / 2, HW, HL), other_uv=full)
        lc = rad * (front_r - 0.1) + Z * z
        a, b = Z * (HL - 1.0), up * (HW - 1.0)
        lens.quad([lc - a - b, lc + a - b, lc + a + b, lc - a + b], full, hint=-rad)

# ------------------------------------------------------------------ cable tray + cables
tray = M("tunnel_cable_tray", "tunnel_lamp_body")
cable = M("tunnel_cables", "tunnel_signs")
black = solid("black")
TRAY_THETA, CABLE_THETA = 40.5, 60.0
HOOK = L / 8                                  # hook spacing, ~2.3 m
for side in (1, -1):
    rad, up = frame(TRAY_THETA, side)
    d1 = L if PIECE == "center" else max_d(TRAY_THETA) - 6
    za, zb = z_of(0), z_of(d1)
    back_r, front_r = R_IN + 1.0, R_IN - 2.6
    box(tray, rad * (back_r + front_r) / 2 + Z * (za + zb) / 2, -rad, up, Z,
        ((back_r - front_r) / 2, 3.2, abs(zb - za) / 2),
        tile=lambda hj, hk: [(0, 0), (hj / 24, 0), (hj / 24, hk / 24), (0, hk / 24)])

    rad_c, up_c = frame(CABLE_THETA, side)
    d_end = L if PIECE == "center" else (np.floor((max_d(CABLE_THETA) - 6) / HOOK) * HOOK)
    ds = np.linspace(0, d_end, int(round(d_end / HOOK)) * 12 + 1)
    pts = []
    for d in ds:
        t = (d % HOOK) / HOOK
        sag = 2.5 * 4 * t * (1 - t)
        pts.append(rad_c * (R_IN - 1.2) - up_c * sag + Z * z_of(d))
    # hooks; the hook on the shared seam belongs to the centre piece only
    for d in np.arange(0 if PIECE == "center" else HOOK, d_end - 1e-6, HOOK):
        box(cable, rad_c * (R_IN - 0.7) + Z * z_of(d), -rad_c, up_c, Z, (0.7, 0.4, 0.4), other_uv=black)
    rc, ring = 0.5, 6
    for a_, b_ in zip(pts[:-1], pts[1:]):
        dv = b_ - a_; dv /= np.linalg.norm(dv)
        e1 = np.cross(dv, X); e1 /= np.linalg.norm(e1); e2 = np.cross(dv, e1)
        for k in range(ring):
            t0, t1 = 2 * np.pi * k / ring, 2 * np.pi * (k + 1) / ring
            n0 = np.cos(t0) * e1 + np.sin(t0) * e2
            n1 = np.cos(t1) * e1 + np.sin(t1) * e2
            cable.quad([a_ + rc * n0, a_ + rc * n1, b_ + rc * n1, b_ + rc * n0], black,
                       hint=n0 + n1, normals=[n0, n1, n1, n0])

# ------------------------------------------------------------------ delineators (photo 4)
deli = M("tunnel_delineators", "tunnel_signs")
DELI_Y = 40.0                                  # centre ~1.0 m above the road
th_d = np.degrees(np.arccos(DELI_Y / R_IN))
DELI_STEP = L / 4                              # ~4.6 m
deli_ds = [DELI_STEP / 2 + k * DELI_STEP for k in range(4)]
deli_ds = [d for d in deli_ds if d + 12 < max_d(th_d)]
for side in (1, -1):
    rad, up = frame(th_d, side)
    for d in deli_ds:
        box(deli, rad * (R_IN - 0.5) + Z * z_of(d), -rad, Z, up, (0.5, 3.0, 7.0), front=(0, 1),
            front_uv=region_uv("delineator", flip_u=side > 0), other_uv=solid("black"))

# ------------------------------------------------------------------ SOS plate (centre only)
if PIECE == "center":
    sos = M("tunnel_sos", "tunnel_signs")
    rad, up = frame(np.degrees(np.arccos(46 / R_IN)), 1)
    box(sos, rad * (R_IN - 1.0) + Z * z_of(L / 2), -rad, Z, up, (1.0, 5.0, 6.7), front=(0, 1),
        front_uv=region_uv("sos"), other_uv=solid("grey"))

# ------------------------------------------------------------------ portal dressing (end only)
if PIECE == "end":
    signs = M("tunnel_portal_signs", "tunnel_signs")
    for side in (-1, 1):
        x, z = side * 178.0, 770.0
        box(signs, (x, 25.0, z - 1.6), X, Y, Z, (1.2, 35.0, 1.2), other_uv=solid("grey"))
        box(signs, (x, 66.0, z), Z, X, Y, (0.4, 10.0, 26.0), front=(0, 1),
            front_uv=region_uv("chevron", flip_u=side > 0), other_uv=solid("grey"))
    crown_z = SV[(STH < 6) & (SR > 160), 2].max()
    gp = M("tunnel_name_plate", "tunnel_signs")
    box(gp, (0, 172.5, crown_z + 1.5), Z, X, Y, (0.6, 20.0, 7.0), front=(0, 1),
        front_uv=region_uv("green"), other_uv=solid("grey"))
    for sx in (-14, 14):
        box(gp, (sx, 163.5, crown_z - 0.5), X, Y, Z, (0.8, 2.5, 1.5), other_uv=solid("grey"))

for m in meshes.values():
    m.weld()

# ------------------------------------------------------------------ write FBX
src_txt = open(SRC, newline="").read()
header = src_txt[:src_txt.index("; Object definitions")]

MATS = {
    # name: (diffuse map, normal map, diffuse, emissive)
    "tunnel_concrete": ("tunnel_concrete.png", "tunnel_concrete_nm.png", (0.7, 0.7, 0.7), (0, 0, 0)),
    "tunnel_rail_green": ("tunnel_rail_green.png", None, (0.086, 0.5, 0.42), (0, 0, 0)),
    "tunnel_lamp_body": ("tunnel_lamp_body.png", None, (0.6, 0.6, 0.6), (0, 0, 0)),
    "tunnel_lamp_lens": ("tunnel_lamp_lens.png", None, (1.0, 0.9, 0.7), (1.0, 0.87, 0.62)),
    "tunnel_signs": ("tunnel_signs.png", None, (0.8, 0.8, 0.8), (0, 0, 0)),
}
used = {m.mat for m in meshes.values()}
MATS = {k: v for k, v in MATS.items() if k in used}

_id = [4000000000000]


def nid():
    _id[0] += 1
    return _id[0]


def num(x):
    s = ("%.6f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def arr(vals, ints=False):
    return ",".join(str(int(v)) for v in vals) if ints else ",".join(num(v) for v in vals)


objs, conns = [], []
n_tex = 0
mat_ids = {}
for name, (dif_map, nm_map, dif, emi) in MATS.items():
    mid = nid(); mat_ids[name] = mid
    c3 = lambda c: ",".join(num(x) for x in c)
    objs.append(f'''	Material: {mid}, "Material::{name}", "" {{
		Version: 102
		ShadingModel: "phong"
		MultiLayer: 0
		Properties70:  {{
			P: "ShadingModel", "KString", "", "", "phong"
			P: "AmbientColor", "Color", "", "A",0,0,0
			P: "DiffuseColor", "Color", "", "A",{c3(dif)}
			P: "DiffuseFactor", "Number", "", "A",1
			P: "EmissiveColor", "Color", "", "A",{c3(emi)}
			P: "EmissiveFactor", "Number", "", "A",{1 if any(emi) else 0}
			P: "SpecularColor", "Color", "", "A",0.2,0.2,0.2
			P: "SpecularFactor", "Number", "", "A",1
			P: "ShininessExponent", "Number", "", "A",20
			P: "Opacity", "double", "Number", "",1
		}}
	}}''')
    slots = [(dif_map, "DiffuseColor")] + ([(dif_map, "EmissiveColor")] if any(emi) else []) + \
            ([(nm_map, "NormalMap")] if nm_map else [])
    made = {}
    for fname, slot in slots:
        if fname not in made:
            tid, vid = nid(), nid()
            tname = fname.rsplit(".", 1)[0]
            made[fname] = tid
            n_tex += 1
            objs.append(f'''	Texture: {tid}, "Texture::{tname}", "" {{
		Type: "TextureVideoClip"
		Version: 202
		TextureName: "Texture::{tname}"
		Properties70:  {{
			P: "UseMaterial", "bool", "", "",1
		}}
		Media: "Video::{tname}"
		FileName: "{fname}"
		RelativeFilename: "{fname}"
		ModelUVTranslation: 0,0
		ModelUVScaling: 1,1
		Texture_Alpha_Source: "None"
		Cropping: 0,0,0,0
	}}''')
            objs.append(f'''	Video: {vid}, "Video::{tname}", "Clip" {{
		Type: "Clip"
		Properties70:  {{
			P: "Path", "KString", "XRefUrl", "", "{fname}"
		}}
		UseMipMap: 0
		Filename: "{fname}"
		RelativeFilename: "{fname}"
	}}''')
            conns.append(f'\t;Video::{tname}, Texture::{tname}\n\tC: "OO",{vid},{tid}\n')
        conns.append(f'\t;Texture, Material::{name}\n\tC: "OP",{made[fname]},{mid}, "{slot}"\n')

for m in meshes.values():
    gid, mid = nid(), nid()
    V = np.array(m.v)
    pvi = []
    for a, b, c in m.tris:
        pvi += [a, b, ~c]
    N = np.array(m.n); UV = np.array(m.uv)
    objs.append(f'''	Geometry: {gid}, "Geometry::{m.name}", "Mesh" {{
		Vertices: *{V.size} {{
			a: {arr(V.ravel())}
		}}
		PolygonVertexIndex: *{len(pvi)} {{
			a: {arr(pvi, True)}
		}}
		GeometryVersion: 124
		LayerElementNormal: 0 {{
			Version: 102
			Name: ""
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "Direct"
			Normals: *{N.size} {{
				a: {arr(N.ravel())}
			}}
		}}
		LayerElementUV: 0 {{
			Version: 101
			Name: "UVChannel_1"
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "IndexToDirect"
			UV: *{UV.size} {{
				a: {arr(UV.ravel())}
			}}
			UVIndex: *{len(UV)} {{
				a: {arr(range(len(UV)), True)}
			}}
		}}
		LayerElementMaterial: 0 {{
			Version: 101
			Name: ""
			MappingInformationType: "AllSame"
			ReferenceInformationType: "IndexToDirect"
			Materials: *1 {{
				a: 0
			}}
		}}
		Layer: 0 {{
			Version: 100
			LayerElement:  {{
				Type: "LayerElementNormal"
				TypedIndex: 0
			}}
			LayerElement:  {{
				Type: "LayerElementMaterial"
				TypedIndex: 0
			}}
			LayerElement:  {{
				Type: "LayerElementUV"
				TypedIndex: 0
			}}
		}}
	}}''')
    objs.append(f'''	Model: {mid}, "Model::{m.name}", "Mesh" {{
		Version: 232
		Properties70:  {{
			P: "DefaultAttributeIndex", "int", "Integer", "",0
			P: "Lcl Translation", "Lcl Translation", "", "A",0,0,0
			P: "Lcl Rotation", "Lcl Rotation", "", "A",0,0,0
			P: "Lcl Scaling", "Lcl Scaling", "", "A",1,1,1
		}}
		Shading: T
		Culling: "CullingOff"
	}}''')
    conns.append(f'\t;Model::{m.name}, Model::RootNode\n\tC: "OO",{mid},0\n')
    conns.append(f'\t;Geometry::{m.name}, Model::{m.name}\n\tC: "OO",{gid},{mid}\n')
    conns.append(f'\t;Material::{m.mat}, Model::{m.name}\n\tC: "OO",{mat_ids[m.mat]},{mid}\n')
    print("%-24s %6d verts %6d tris  %s" % (m.name, len(V), len(m.tris), m.mat))

nm, nmat = len(meshes), len(MATS)
defs = f'''; Object definitions
;------------------------------------------------------------------

Definitions:  {{
	Version: 100
	Count: {1 + 2 * nm + nmat + 2 * n_tex}
	ObjectType: "GlobalSettings" {{
		Count: 1
	}}
	ObjectType: "Model" {{
		Count: {nm}
	}}
	ObjectType: "Geometry" {{
		Count: {nm}
	}}
	ObjectType: "Material" {{
		Count: {nmat}
	}}
	ObjectType: "Texture" {{
		Count: {n_tex}
	}}
	ObjectType: "Video" {{
		Count: {n_tex}
	}}
}}

; Object properties
;------------------------------------------------------------------

Objects:  {{
''' + "\n".join(objs) + '''
}

; Object connections
;------------------------------------------------------------------

Connections:  {

''' + "\t\n".join(conns) + "}\n"
open(DST, "w", newline="\n").write(header + defs)
print("%s: L=%.2f lights at d=%s delineators at d=%s" % (PIECE, L, np.round(light_ds, 1), np.round(deli_ds, 1)))
