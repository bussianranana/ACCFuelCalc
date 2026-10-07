"""Dress the tunnel string object like the A-384 tunnels (Algodonales).

Reads the original ASCII FBX, re-UVs the concrete shell for a stained-lining
texture, and appends lights, cable trays, cables, delineators, SOS plate,
portal chevron boards and the green tunnel plate as separate objects.
Units stay as in the source (inches, UnitScaleFactor 2.54); X = across,
Y = up, Z = along the tunnel (portal at +Z).
"""
import re, sys, json, numpy as np

SRC, DST, ATLAS = sys.argv[1], sys.argv[2], sys.argv[3]
txt = open(SRC, newline="").read()
atlas = json.load(open(ATLAS))
R_IN = 137.8          # inner lining radius, arch centre at (0, 0)
SHELL_GEOM = "2624041706128"

_id = [3000000000000]


def new_id():
    _id[0] += 1
    return _id[0]


def num(x):
    s = "%.6f" % x
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def arr_text(vals, ints=False):
    return ",".join(str(int(v)) for v in vals) if ints else ",".join(num(v) for v in vals)


def get_arr(block, key):
    m = re.search(key + r": \*(\d+) \{\s*a: ([^}]*)\}", block)
    return np.array([float(x) for x in m.group(2).replace("\n", "").split(",")])


# ------------------------------------------------------------------ mesh builder
class Mesh:
    def __init__(self, name, mat):
        self.name, self.mat = name, mat
        self.v, self.tris, self.uv, self.n = [], [], [], []

    def tri(self, p, uv, hint=None):
        p = [np.asarray(q, float) for q in p]
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        if hint is not None and np.dot(nrm, hint) < 0:
            p, uv, nrm = [p[0], p[2], p[1]], [uv[0], uv[2], uv[1]], -nrm
        nrm = nrm / (np.linalg.norm(nrm) + 1e-12)
        base = len(self.v)
        self.v += p
        self.tris.append((base, base + 1, base + 2))
        self.uv += list(uv)
        self.n += [nrm] * 3

    def quad(self, p, uv, hint=None, normals=None):
        self.tri([p[0], p[1], p[2]], [uv[0], uv[1], uv[2]], hint)
        self.tri([p[0], p[2], p[3]], [uv[0], uv[2], uv[3]], hint)
        if normals is not None:          # smooth normals for tubes
            k = len(self.n)
            self.n[k - 6:k - 3] = [normals[0], normals[1], normals[2]]
            self.n[k - 3:k] = [normals[0], normals[2], normals[3]]

    def weld(self):
        """Merge identical vertices so the vertex list stays compact."""
        key = {}
        newv, remap = [], []
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
    u0, u1 = x0 / S, x1 / S
    v0, v1 = 1 - y1 / S, 1 - y0 / S
    if flip_u:
        u0, u1 = u1, u0
    # inset half a texel to avoid bleeding
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def solid(name):
    q = region_uv(name)
    cu = (q[0][0] + q[1][0]) / 2
    cv = (q[0][1] + q[2][1]) / 2
    return [(cu, cv)] * 4


def box(m, c, ax, ay, az, h, front=None, front_uv=None, other_uv=None, tile=None):
    """Oriented box. ax/ay/az unit axes, h half sizes. `front` = (axis_index, sign)
    gets front_uv mapped with u along the next axis and v along the one after."""
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
                uv = tile(i, h[j], h[k])
            else:
                uv = other_uv
            # make sure u runs left->right when looking at the face from outside
            if np.dot(np.cross(axes[j], axes[k]), s * axes[i]) < 0:
                pts = [pts[1], pts[0], pts[3], pts[2]]
                uv = [uv[1], uv[0], uv[3], uv[2]]
            m.quad(pts, uv, hint=s * axes[i])


def frame(theta_deg, side):
    """Wall frame at angle theta from the crown. Returns radial-out, up-tangent."""
    t = np.radians(theta_deg)
    rad = np.array([side * np.sin(t), np.cos(t), 0.0])
    up = np.array([-side * np.cos(t), np.sin(t), 0.0])
    return rad, up


Z = np.array([0.0, 0.0, 1.0])

# ------------------------------------------------------------------ read source geometry
geo_start = txt.index("\tGeometry: " + SHELL_GEOM)
geo_end = txt.index("\n\t}", geo_start)
shell_block = txt[geo_start:geo_end]
sv = get_arr(shell_block, "Vertices").reshape(-1, 3)
spvi = get_arr(shell_block, "PolygonVertexIndex").astype(int)

# light nulls placed by the author
nulls = [(m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4)))
         for m in re.finditer(r'Model::(light\d*)", "Null" \{.*?Lcl Translation", "", "A",([-\d.e]+),([-\d.e]+),([-\d.e]+)',
                              txt, re.S)]
assert len(nulls) == 8, nulls
LIGHT_Z = sorted(n[3] for n in nulls)
LX, LY = nulls[0][1], nulls[0][2]
LIGHT_THETA = np.degrees(np.arctan2(LX, LY))
LIGHT_R = np.hypot(LX, LY)

sr = np.hypot(sv[:, 0], sv[:, 1])
sth = np.degrees(np.arctan2(np.abs(sv[:, 0]), sv[:, 1]))


def rim_z(theta, tol=2.5):
    """Last Z where the inner lining still exists at this angle (portal cut)."""
    m = (np.abs(sth - theta) < tol) & (sr < R_IN + 2)
    return sv[m, 2].max()


# ------------------------------------------------------------------ 1. re-UV the shell
polys, cur = [], []
for i in spvi:
    if i < 0:
        cur.append(~i); polys.append(cur); cur = []
    else:
        cur.append(i)
U_LEN = np.pi * R_IN          # inches covered by u 0..1 (floor to floor)
V_LEN = 400.0                 # inches per v tile along the tunnel
uvs = []
for p in polys:
    P = sv[p]
    n = np.cross(P[1] - P[0], P[2] - P[0]); n /= np.linalg.norm(n) + 1e-12
    cxy = P[:, :2].mean(0); rhat = np.array([*cxy / (np.linalg.norm(cxy) + 1e-9), 0])
    if abs(np.dot(n, rhat)) > 0.55:
        for q in P:
            th = np.arctan2(q[0], q[1])
            uvs.append((0.5 + th / np.pi, q[2] / V_LEN))
    else:
        ax = np.argmax(np.abs(n))
        for q in P:
            if ax == 2:
                uvs.append((0.5 + q[0] / U_LEN, q[1] / V_LEN))
            elif ax == 0:
                uvs.append((q[2] / U_LEN, q[1] / V_LEN))
            else:
                uvs.append((0.5 + q[0] / U_LEN, q[2] / V_LEN))
uvs = np.array(uvs)
new_uv_layer = (
    '\t\tLayerElementUV: 0 {\n\t\t\tVersion: 101\n\t\t\tName: "UVChannel_1"\n'
    '\t\t\tMappingInformationType: "ByPolygonVertex"\n\t\t\tReferenceInformationType: "IndexToDirect"\n'
    "\t\t\tUV: *%d {\n\t\t\t\ta: %s\n\t\t\t} \n\t\t\tUVIndex: *%d {\n\t\t\t\ta: %s\n\t\t\t} \n\t\t}"
    % (uvs.size, arr_text(uvs.ravel()), len(uvs), arr_text(range(len(uvs)), True)))
uv_s = shell_block.index("\t\tLayerElementUV: 0 {")
uv_e = shell_block.index("\n\t\t}", shell_block.index("UVIndex:", uv_s)) + len("\n\t\t}")
shell_block = shell_block[:uv_s] + new_uv_layer + shell_block[uv_e:]
txt = txt[:geo_start] + shell_block + txt[geo_end:]

# ------------------------------------------------------------------ 2. new dressing
meshes = {}


def M(name, mat):
    if name not in meshes:
        meshes[name] = Mesh(name, mat)
    return meshes[name]


full = [(0, 0), (1, 0), (1, 1), (0, 1)]

# 2a. luminaires on both upper walls at the author's null positions
body = M("tunnel_light_body", "tunnel_lamp_body")
H_LEN, H_W, DEPTH = 12.0, 4.5, 5.6
for side in (1, -1):
    rad, up = frame(LIGHT_THETA, side)
    for li, z in enumerate(LIGHT_Z):
        # one mesh per lens so CSP can spawn one light per lamp
        lens = M("tunnel_light_lens_%s%02d" % ("R" if side > 0 else "L", li + 1), "tunnel_lamp_lens")
        back_r, front_r = R_IN + 1.5, LIGHT_R + 0.15
        c = rad * (back_r + front_r) / 2 + Z * z
        box(body, c, -rad, up, Z, ((back_r - front_r) / 2, H_W, H_LEN), other_uv=full)
        # lens slightly proud of the housing face, facing the carriageway
        lc = rad * (front_r - 0.12) + Z * z
        a, b = Z * (H_LEN - 1.0), up * (H_W - 0.9)
        lens.quad([lc - a - b, lc + a - b, lc + a + b, lc - a + b], full, hint=-rad)

# 2b. cable tray just above the light line, and a sagging cable lower down
tray = M("tunnel_cable_tray", "tunnel_lamp_body")
cable = M("tunnel_cables", "tunnel_signs")
black = solid("black")
for side in (1, -1):
    th = LIGHT_THETA - 7.5
    rad, up = frame(th, side)
    z1 = rim_z(th) - 6
    back_r, front_r = R_IN + 1.0, R_IN - 2.6
    c = rad * (back_r + front_r) / 2 + Z * (z1 / 2)
    box(tray, c, -rad, up, Z, ((back_r - front_r) / 2, 3.2, z1 / 2),
        tile=lambda i, hj, hk: [(0, 0), (hj / 24, 0), (hj / 24, hk / 24), (0, hk / 24)])

    th_c = 62 if side < 0 else 58
    z_end = rim_z(th_c) - 4
    span = 96.0
    nseg_per_span, ring = 12, 6
    zs = np.linspace(0, z_end, int(np.ceil(z_end / span * nseg_per_span)) + 1)
    pts = []
    for z in zs:
        t = (z % span) / span
        sag = 3.0 * 4 * t * (1 - t)            # parabolic sag between hooks
        rad_c, up_c = frame(th_c, side)
        pts.append(rad_c * (R_IN - 1.2) - up_c * sag + Z * z)
    rc = 0.55
    for a_, b_ in zip(pts[:-1], pts[1:]):
        d = b_ - a_; d /= np.linalg.norm(d)
        e1 = np.cross(d, [1, 0, 0]) if abs(d[0]) < 0.9 else np.cross(d, [0, 1, 0])
        e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
        for k in range(ring):
            t0, t1 = 2 * np.pi * k / ring, 2 * np.pi * (k + 1) / ring
            n0 = np.cos(t0) * e1 + np.sin(t0) * e2
            n1 = np.cos(t1) * e1 + np.sin(t1) * e2
            cable.quad([a_ + rc * n0, a_ + rc * n1, b_ + rc * n1, b_ + rc * n0], black,
                       hint=(n0 + n1), normals=[n0, n1, n1, n0])

# 2c. wall delineators above the green handrail, staggered left/right
deli = M("tunnel_delineators", "tunnel_signs")
DELI_Y = 31.0
th_d = np.degrees(np.arccos(DELI_Y / R_IN))
for side, zlist in ((1, (24, 124, 224, 324)), (-1, (74, 174, 274, 374))):
    rad, up = frame(th_d, side)
    for z in zlist:
        c = rad * (R_IN - 0.4) + Z * z
        # axes: (-rad, Z, up) -> front face (axis0,+1) faces the road, u along Z, v up
        box(deli, c, -rad, Z, up, (0.4, 2.0, 7.0), front=(0, 1),
            front_uv=region_uv("delineator", flip_u=side > 0), other_uv=solid("black"))

# 2d. SOS cabinet plate on the right wall (red box in the reference photo)
sos = M("tunnel_sos", "tunnel_signs")
rad, up = frame(np.degrees(np.arccos(44 / R_IN)), 1)
box(sos, rad * (R_IN - 1.0) + Z * 160, -rad, Z, up, (1.0, 5.0, 6.7), front=(0, 1),
    front_uv=region_uv("sos"), other_uv=solid("grey"))

# 2e. portal chevron edge boards on posts, both sides of the carriageway
signs = M("tunnel_portal_signs", "tunnel_signs")
X = np.array([1.0, 0, 0]); Y = np.array([0, 1.0, 0])
for side in (-1, 1):
    x, z = side * 178.0, 770.0
    box(signs, (x, 25.0, z - 1.6), X, Y, Z, (1.2, 35.0, 1.2), other_uv=solid("grey"))   # post
    # board 20" x 52", bottom at 40": axes (Z, X, Y) -> front (0,+1) faces +Z, u along X, v up
    box(signs, (x, 66.0, z), Z, X, Y, (0.4, 10.0, 26.0), front=(0, 1),
        front_uv=region_uv("chevron", flip_u=side > 0), other_uv=solid("grey"))

# 2f. green tunnel plate sitting on the portal crown
crown_z = sv[(sth < 6) & (sr > 160), 2].max()
gp = M("tunnel_name_plate", "tunnel_signs")
box(gp, (0, 165.0 + 7.5, crown_z + 1.5), Z, X, Y, (0.6, 20.0, 7.0), front=(0, 1),
    front_uv=region_uv("green"), other_uv=solid("grey"))
for sx in (-14, 14):        # two little brackets
    box(gp, (sx, 163.5, crown_z - 0.5), X, Y, Z, (0.8, 2.5, 1.5), other_uv=solid("grey"))

for m in meshes.values():
    m.weld()

# ------------------------------------------------------------------ 3. materials / textures
MATS = {
    # name: (texture file, diffuse, emissive)
    "tunnel_lamp_body": ("tunnel_lamp_body.png", (0.6, 0.6, 0.6), (0, 0, 0)),
    "tunnel_lamp_lens": ("tunnel_lamp_lens.png", (1.0, 0.9, 0.7), (1.0, 0.87, 0.62)),
    "tunnel_signs": ("tunnel_signs.png", (0.8, 0.8, 0.8), (0, 0, 0)),
}


def c3(c):
    return ",".join(num(x) for x in c)


objs, conns = [], []
mat_ids = {}
for name, (tex, dif, emi) in MATS.items():
    mid, tid, vid = new_id(), new_id(), new_id()
    mat_ids[name] = mid
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
    objs.append(texture_block := f'''	Texture: {tid}, "Texture::{name}_map", "" {{
		Type: "TextureVideoClip"
		Version: 202
		TextureName: "Texture::{name}_map"
		Properties70:  {{
			P: "UseMaterial", "bool", "", "",1
		}}
		Media: "Video::{name}_map"
		FileName: "{tex}"
		RelativeFilename: "{tex}"
		ModelUVTranslation: 0,0
		ModelUVScaling: 1,1
		Texture_Alpha_Source: "None"
		Cropping: 0,0,0,0
	}}''')
    objs.append(f'''	Video: {vid}, "Video::{name}_map", "Clip" {{
		Type: "Clip"
		Properties70:  {{
			P: "Path", "KString", "XRefUrl", "", "{tex}"
		}}
		UseMipMap: 0
		Filename: "{tex}"
		RelativeFilename: "{tex}"
	}}''')
    conns.append(f'\t;Texture::{name}_map, Material::{name}\n\tC: "OP",{tid},{mid}, "DiffuseColor"\n')
    conns.append(f'\t;Video::{name}_map, Texture::{name}_map\n\tC: "OO",{vid},{tid}\n')
    if any(emi):
        conns.append(f'\t;Texture::{name}_map, Material::{name}\n\tC: "OP",{tid},{mid}, "EmissiveColor"\n')

# ------------------------------------------------------------------ 4. geometry / models
for m in meshes.values():
    gid, mid = new_id(), new_id()
    V = np.array(m.v)
    pvi = []
    for a, b, c in m.tris:
        pvi += [a, b, ~c]
    N = np.array(m.n); UV = np.array(m.uv)
    objs.append(f'''	Geometry: {gid}, "Geometry::{m.name}", "Mesh" {{
		Vertices: *{V.size} {{
			a: {arr_text(V.ravel())}
		}}
		PolygonVertexIndex: *{len(pvi)} {{
			a: {arr_text(pvi, True)}
		}}
		GeometryVersion: 124
		LayerElementNormal: 0 {{
			Version: 102
			Name: ""
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "Direct"
			Normals: *{N.size} {{
				a: {arr_text(N.ravel())}
			}}
		}}
		LayerElementUV: 0 {{
			Version: 101
			Name: "UVChannel_1"
			MappingInformationType: "ByPolygonVertex"
			ReferenceInformationType: "IndexToDirect"
			UV: *{UV.size} {{
				a: {arr_text(UV.ravel())}
			}}
			UVIndex: *{len(UV)} {{
				a: {arr_text(range(len(UV)), True)}
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
    print("%-22s %5d verts %5d tris  mat=%s" % (m.name, len(V), len(m.tris), m.mat))

# ------------------------------------------------------------------ 5. original materials -> textures
EXIST = {"Map #1": "tunnel_concrete.png", "Map #2": "tunnel_rail_green.png"}
for tname, file in EXIST.items():
    s = txt.index(f'"Texture::{tname}", "" {{')
    e = txt.index("\n\t}", s)
    blk = txt[s:e]
    blk = re.sub(r'FileName: ""', f'FileName: "{file}"', blk)
    blk = re.sub(r'RelativeFilename: ""', f'RelativeFilename: "{file}"', blk)
    txt = txt[:s] + blk + txt[e:]
# Max exports the maps on "3dsMax|parameters|diffuse_tex" only; also wire them to the
# standard DiffuseColor slot so RTB / Assimp / ksEditor pick the textures up.
for tex_id, mat_id, label in (("2622854352896", "2625693353136", "Map #1, Material::Material #25"),
                              ("2622854354816", "2625693355536", "Map #2, Material::Material #27")):
    conns.append(f'\t;Texture::{label}\n\tC: "OP",{tex_id},{mat_id}, "DiffuseColor"\n')
# green paint colour on the railing material for viewers that ignore the map
s = txt.index('"Material::Material #27"')
e = txt.index("\n\t}", s)
blk = txt[s:e].replace('P: "DiffuseColor", "ColorRGB", "Color", "",0.660000026226044,0.660000026226044,0.660000026226044',
                       'P: "DiffuseColor", "ColorRGB", "Color", "",0.086,0.5,0.42')
txt = txt[:s] + blk + txt[e:]

# ------------------------------------------------------------------ 6. splice into the document
obj_end = txt.index("\n}", txt.index("\nObjects:  {"))
txt = txt[:obj_end] + "\n" + "\n".join(objs) + txt[obj_end:]
con_end = txt.index("\n}", txt.index("\nConnections:  {"))
txt = txt[:con_end] + "\n" + "\t\n".join(conns).rstrip("\n") + txt[con_end:]


def bump(t, otype, by):
    pat = f'ObjectType: "{otype}" {{\n\t\tCount: '
    i = txt.index(pat) + len(pat)
    j = txt.index("\n", i)
    return t[:i] + str(int(t[i:j]) + by) + t[j:]


nm, nmat = len(meshes), len(MATS)
txt = bump(txt, "Model", nm)
txt = bump(txt, "Geometry", nm)
txt = bump(txt, "Material", nmat)
txt = bump(txt, "Texture", nmat)
defs = txt.index("Definitions:  {")
cnt = txt.index("\tCount: ", defs) + len("\tCount: ")
cnt_e = txt.index("\n", cnt)
txt = txt[:cnt] + str(int(txt[cnt:cnt_e]) + 2 * nm + 3 * nmat) + txt[cnt_e:]
nodeattr = txt.index('\tObjectType: "NodeAttribute" {')
txt = txt[:nodeattr] + f'\tObjectType: "Video" {{\n\t\tCount: {nmat}\n\t}}\n' + txt[nodeattr:]

open(DST, "w", newline="").write(txt)
print("light theta %.2f deg, r %.2f, z %s" % (LIGHT_THETA, LIGHT_R, LIGHT_Z))
print("crown z %.1f" % crown_z)
