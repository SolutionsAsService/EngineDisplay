"""Minimal glTF 2.0 binary (GLB) writer for FreeCAD shapes.

Each part becomes one node with one mesh and one material. Faces are tessellated
one at a time so normals stay sharp across B-rep edges and smooth within a face.
FreeCAD works in millimetres with Z up; glTF is metres with Y up, so every point,
direction and rotation goes through `to_gltf`.
"""
import json
import math
import struct

SCALE = 0.001  # mm -> m


def to_gltf(v):
    x, y, z = v
    return [x * SCALE, z * SCALE, -y * SCALE]


def dir_to_gltf(v):
    x, y, z = v
    return [x, z, -y]


def quat_axis_angle(axis, angle_rad):
    ax = dir_to_gltf(axis)
    n = math.sqrt(sum(c * c for c in ax)) or 1.0
    s = math.sin(angle_rad / 2)
    return [ax[0] / n * s, ax[1] / n * s, ax[2] / n * s, math.cos(angle_rad / 2)]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def tessellate(shape, tol):
    """Return (positions, normals, indices) in FreeCAD mm, outward-wound."""
    pos, nor, idx = [], [], []
    for face in shape.Faces:
        try:
            import MeshPart
            m = MeshPart.meshFromShape(Shape=face, LinearDeflection=tol, AngularDeflection=0.25)
            pts, tris = m.Topology
        except Exception:
            try:
                pts, tris = face.tessellate(tol)
            except Exception:
                continue
        if not tris:
            continue
        pts = [(p.x, p.y, p.z) for p in pts]
        # Orientation check against the analytic normal at the first triangle.
        a, b, c = (pts[i] for i in tris[0])
        tn = _cross(_sub(b, a), _sub(c, a))
        flip = False
        try:
            cen = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)
            import FreeCAD
            u, v = face.Surface.parameter(FreeCAD.Vector(*cen))
            fn = face.normalAt(u, v)
            flip = _dot(tn, (fn.x, fn.y, fn.z)) < 0
        except Exception:
            pass
        if flip:
            tris = [(t[0], t[2], t[1]) for t in tris]
        acc = [[0.0, 0.0, 0.0] for _ in pts]
        for t in tris:
            p0, p1, p2 = (pts[i] for i in t)
            n = _cross(_sub(p1, p0), _sub(p2, p0))
            for i in t:
                acc[i][0] += n[0]
                acc[i][1] += n[1]
                acc[i][2] += n[2]
        base = len(pos)
        for p, n in zip(pts, acc):
            l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
            pos.append(p)
            nor.append((n[0] / l, n[1] / l, n[2] / l))
        for t in tris:
            idx.extend((base + t[0], base + t[1], base + t[2]))
    return pos, nor, idx


def write_glb(path, root_name, root_extras, parts, materials, tol=0.4):
    """parts: dicts with name, shape (local frame, mm), mat, pos (mm), rot ([x,y,z,w] glTF) and extras."""
    blob = bytearray()
    accessors, views, meshes, nodes = [], [], [], []
    mat_index = {name: i for i, name in enumerate(materials)}
    gl_materials = []
    for name, m in materials.items():
        gl_materials.append({
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorFactor": list(m["color"]) + [1.0],
                "metallicFactor": m.get("metal", 0.0),
                "roughnessFactor": m.get("rough", 0.6),
            },
            "doubleSided": False,
        })

    def add_view(data, target):
        while len(blob) % 4:
            blob.append(0)
        off = len(blob)
        blob.extend(data)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(views) - 1

    stats = {"triangles": 0, "vertices": 0}
    for part in parts:
        # Deflection scales with the part: 0.4 mm on a piston ring, ~2 mm on a 2.3 m propeller.
        diag = part["shape"].BoundBox.DiagonalLength
        p, n, ix = tessellate(part["shape"], part.get("tol", max(tol, min(2.5, diag / 900))))
        if not ix:
            raise RuntimeError("empty tessellation for " + part["name"])
        gp = [to_gltf(v) for v in p]
        gn = [dir_to_gltf(v) for v in n]
        mins = [min(v[k] for v in gp) for k in range(3)]
        maxs = [max(v[k] for v in gp) for k in range(3)]
        pv = add_view(b"".join(struct.pack("<3f", *v) for v in gp), 34962)
        nv = add_view(b"".join(struct.pack("<3f", *v) for v in gn), 34962)
        big = len(gp) > 65535
        iv = add_view(struct.pack("<%d%s" % (len(ix), "I" if big else "H"), *ix), 34963)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": len(gp), "type": "VEC3", "min": mins, "max": maxs})
        accessors.append({"bufferView": nv, "componentType": 5126, "count": len(gn), "type": "VEC3"})
        accessors.append({"bufferView": iv, "componentType": 5125 if big else 5123, "count": len(ix), "type": "SCALAR"})
        a0 = len(accessors) - 3
        meshes.append({"name": part["name"], "primitives": [{
            "attributes": {"POSITION": a0, "NORMAL": a0 + 1}, "indices": a0 + 2, "material": mat_index[part["mat"]]}]})
        node = {"name": part["name"], "mesh": len(meshes) - 1, "translation": to_gltf(part.get("pos", (0, 0, 0)))}
        if part.get("rot"):
            node["rotation"] = part["rot"]
        node["extras"] = part.get("extras", {})
        nodes.append(node)
        stats["triangles"] += len(ix) // 3
        stats["vertices"] += len(gp)

    root = {"name": root_name, "children": list(range(len(nodes))), "extras": root_extras}
    nodes.append(root)
    gltf = {
        "asset": {"version": "2.0", "generator": "EngineDisplay cad/build_engines.py (FreeCAD)"},
        "scene": 0,
        "scenes": [{"name": root_name, "nodes": [len(nodes) - 1]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": gl_materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    while len(blob) % 4:
        blob.append(0)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942))
        f.write(blob)
    stats["bytes"] = total
    return stats
