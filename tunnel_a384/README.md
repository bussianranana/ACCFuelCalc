# A-384 tunnel string object (Assetto Corsa / Race Track Builder)

This is `tunnel.fbx` dressed to look like the A-384 tunnels near Algodonales:
stained shotcrete lining, wall lights, cable tray and cables, delineators, an
SOS plate, green handrails, chevron edge boards at the portal, and a green
tunnel plate on the crown.

![inside](preview/inside.png)
![portal](preview/portal.png)

The previews come from a simple software renderer with flat shading and a
stand-in road. They show placement and texturing, not what AC will look like.

## Files

| File | What it is |
|---|---|
| `tunnel_a384.fbx` | The dressed model (ASCII FBX 7.7, same units/axes as the original) |
| `tunnel_concrete.png` | Lining texture, 2048², tiles along the tunnel every 400 in (~10 m) |
| `tunnel_rail_green.png` | Green paint for the existing handrail material (`Material #27`) |
| `tunnel_lamp_body.png` | Aluminium for lamp housings and cable tray |
| `tunnel_lamp_lens.png` | Lamp lens (use with an emissive shader) |
| `tunnel_signs.png` | Atlas: chevron board, delineator, SOS, green plate, solid black/grey |
| `ext_config_tunnel.ini` | CSP snippet: emissive lenses plus one light per lamp |
| `tools/` | Scripts that produce all of the above from the original FBX |

Keep the PNGs in the same folder as the FBX. The texture paths are relative.

## What changed

Original objects (`Cylinder001` shell, `Cylinder002`/`Object003` rails, `light*` nulls) are kept.

* **Shell**: new UVs. Cylindrical mapping goes around the arch, so u runs from floor to crown to floor and v runs along the tunnel. That makes the seepage streaks run down from the crown the way they do in the photos. Box mapping is used on the end caps and portal cut faces. The `Map #1` and `Map #2` textures now point at real files and are also wired to the standard DiffuseColor slot. The Max export had them only on `3dsMax|parameters|diffuse_tex`, which most importers ignore.
* **New objects** (each one can be deleted on its own):
  * `tunnel_light_body` and `tunnel_light_lens_L01…L08 / R01…R08`: luminaires at your 8 `light` null positions (right wall), mirrored onto the left wall.
  * `tunnel_cable_tray`: tray above the light line on both walls. It stops just short of the portal cut.
  * `tunnel_cables`: cables sagging between hooks every ~2.4 m.
  * `tunnel_delineators`: white/black/amber wall markers above the handrail, every ~2.5 m and staggered left/right.
  * `tunnel_sos`: red SOS plate on the right wall.
  * `tunnel_portal_signs`: black/white chevron edge boards on posts at both sides of the mouth (+Z end). Stripes slope down toward the road.
  * `tunnel_name_plate`: green "TÚNEL / A-384" plate on the portal crown.

## Materials in RTB / ksEditor

| Material | Suggested AC shader |
|---|---|
| `Material #25` (concrete) | ksPerPixel, low specular |
| `Material #27` (rail) | ksPerPixel |
| `tunnel_lamp_body` | ksPerPixel |
| `tunnel_lamp_lens` | ksPerPixel with `ksEmissive` around 30,26,18 (or let the CSP snippet set it) |
| `tunnel_signs` | ksPerPixel. Raise ksAmbient/ksDiffuse a bit if you want the boards to read as reflective |

## Notes / limits

* Lane markings and kerbs belong to your RTB road, so the tunnel does not include them.
* The portal boards and the name plate sit at the portal end (+Z). If the string repeats the full segment, delete `tunnel_portal_signs` and `tunnel_name_plate` from the repeating piece and use them only on the end piece.
* If RTB merges the lens meshes on export, CSP will create fewer lights. In that case place the lights with CSP's Objects Inspector or a `[LIGHT_...]` per position.

## Regenerating

```
python3 tools/gen_textures.py .                         # textures + tools/atlas.json
python3 tools/build.py tools/tunnel_original.fbx tunnel_a384.fbx tools/atlas.json
```

Requires numpy and Pillow. You can edit positions, spacing and sizes at the top of each section in `build.py`.
