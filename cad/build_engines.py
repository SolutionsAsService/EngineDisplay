"""Build the three EngineDisplay engines as parametric FreeCAD solids.

Run with FreeCAD's Python (no GUI needed):
    freecadcmd cad/build_engines.py            # or
    python cad/build_engines.py                # if FreeCAD's lib dir is importable

Writes, per engine, into models/:
    <id>.glb   one node per part, PBR materials, kinematics in the root node's extras
    <id>.step  every part placed at crank angle 0, for CAD tools
    <id>.stl   the same assembly as one mesh, for measurement
and models/engines.json, the figures the site prints (computed here, not typed).

Frame: FreeCAD millimetres, Z up. The GLB writer converts to glTF metres, Y up.
These are illustrative, generic engines (no particular manufacturer's design),
proportioned from their bore, stroke and rod length.
"""
import json
import math
import os
import sys

for p in ("/opt/freecad/lib", os.environ.get("FREECAD_LIB", "")):
    if p and p not in sys.path:
        sys.path.append(p)

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Mesh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glb  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "models")
V = FreeCAD.Vector

MATERIALS = {
    "castIron": {"color": (0.30, 0.31, 0.33), "metal": 0.6, "rough": 0.75},
    "aluminium": {"color": (0.72, 0.74, 0.76), "metal": 0.9, "rough": 0.38},
    "steel": {"color": (0.58, 0.60, 0.63), "metal": 1.0, "rough": 0.28},
    "forged": {"color": (0.42, 0.44, 0.47), "metal": 1.0, "rough": 0.35},
    "piston": {"color": (0.82, 0.83, 0.84), "metal": 0.85, "rough": 0.3},
    "paint": {"color": (0.70, 0.10, 0.06), "metal": 0.2, "rough": 0.45},
    "black": {"color": (0.06, 0.06, 0.07), "metal": 0.3, "rough": 0.6},
    "exhaust": {"color": (0.46, 0.30, 0.20), "metal": 0.8, "rough": 0.55},
    "brass": {"color": (0.78, 0.60, 0.28), "metal": 1.0, "rough": 0.3},
    "ceramic": {"color": (0.93, 0.92, 0.88), "metal": 0.0, "rough": 0.4},
    "wood": {"color": (0.45, 0.27, 0.13), "metal": 0.0, "rough": 0.55},
    "olive": {"color": (0.28, 0.32, 0.22), "metal": 0.3, "rough": 0.6},
    "blue": {"color": (0.08, 0.20, 0.45), "metal": 0.3, "rough": 0.45},
}


# ---------------------------------------------------------------- primitives
def cyl(r, h, base, d=(0, 0, 1)):
    return Part.makeCylinder(r, h, V(*base), V(*d))


def box(sx, sy, sz, center):
    cx, cy, cz = center
    return Part.makeBox(sx, sy, sz, V(cx - sx / 2, cy - sy / 2, cz - sz / 2))


def sphere(r, c):
    return Part.makeSphere(r, V(*c))


def seg(p0, p1, r):
    a, b = V(*p0), V(*p1)
    d = b - a
    return Part.makeCylinder(r, d.Length, a, d)


def pipe(points, r):
    """A bent pipe: straight segments with spheres at the bends."""
    solids = [seg(points[i], points[i + 1], r) for i in range(len(points) - 1)]
    solids += [sphere(r, p) for p in points[1:-1]]
    return Part.makeCompound(solids)


def comp(shapes):
    return Part.makeCompound([s for s in shapes if s is not None])


def rotated(shape, axis, deg, center=(0, 0, 0)):
    s = shape.copy()
    s.rotate(V(*center), V(*axis), deg)
    return s


def moved(shape, by):
    s = shape.copy()
    s.translate(V(*by))
    return s


def loft_rect(x0, x1, y0_half, z_top, z_bot, y1_half):
    """Tapered tray (oil pan): rectangle at z_top lofted to a narrower one at z_bot."""
    def rect(yh, z, xm=0):
        pts = [V(x0 + xm, -yh, z), V(x1 - xm, -yh, z), V(x1 - xm, yh, z), V(x0 + xm, yh, z), V(x0 + xm, -yh, z)]
        return Part.makePolygon(pts)
    return Part.makeLoft([rect(y0_half, z_top), rect(y1_half, z_bot, 25)], True)


# ---------------------------------------------------------------- vectors
def vadd(*vs):
    return tuple(sum(c) for c in zip(*vs))


def vmul(v, s):
    return tuple(c * s for c in v)


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def vnorm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


class Kin:
    """Slider-crank kinematics shared by Python (pose at theta=0) and the site (live)."""

    def __init__(self, origin, k, e0, r, l):
        self.c, self.k, self.e0, self.r, self.l = origin, vnorm(k), vnorm(e0), r, l
        self.e1 = vcross(self.k, self.e0)

    def dir(self, ang):
        return vadd(vmul(self.e0, math.cos(ang)), vmul(self.e1, math.sin(ang)))

    def pose(self, theta, s, alpha, psi):
        a = self.dir(alpha)
        phi = theta + psi - alpha
        x = self.r * math.cos(phi) + math.sqrt(self.l ** 2 - (self.r * math.sin(phi)) ** 2)
        base = vadd(self.c, vmul(self.k, s))
        pin = vadd(base, vmul(a, x))
        crankpin = vadd(base, vmul(self.dir(theta + psi), self.r))
        return a, pin, crankpin


def rod_rotation(a, pin, crankpin):
    """Quaternion (glTF frame) turning the rod's rest direction -a onto pin->crankpin."""
    rest = glb.dir_to_gltf(vmul(a, -1))
    want = glb.dir_to_gltf(vnorm(vadd(crankpin, vmul(pin, -1))))
    d = sum(x * y for x, y in zip(rest, want))
    ax = vcross(rest, want)
    w = 1 + d
    q = [ax[0], ax[1], ax[2], w]
    n = math.sqrt(sum(c * c for c in q)) or 1
    return [c / n for c in q]


# ---------------------------------------------------------------- shared moving parts
def piston_shape(bore, ch, plen, a, crown="flat"):
    """Piston in its local frame: pin at the origin, axis along a."""
    rr = bore / 2 - 0.4
    up, down = ch, plen - ch
    sk = cyl(rr, plen, vmul(a, -down), a)
    if crown == "bowl":
        sk = sk.cut(sphere(bore * 0.33, vmul(a, up + bore * 0.18)))
    grooves = []
    for i, off in enumerate((up - 6, up - 13, up - 20)):
        grooves.append(cyl(rr + 0.2, 2.2, vmul(a, off), a))
    pin = cyl(bore * 0.13, bore * 0.84, vmul(_perp(a), -bore * 0.42), _perp(a))
    return sk, comp(grooves), pin


def _perp(a):
    """Gudgeon-pin direction: across the cylinder, along the crank axis family."""
    # Pins run parallel to the crank axis; for every engine here that axis is
    # perpendicular to a, so pick the world axis least aligned with a and the other.
    cands = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    best = min(cands, key=lambda c: abs(sum(x * y for x, y in zip(c, a))))
    return best


def rod_shape(l, bore, a, k):
    """Connecting rod in its local frame: small end at the origin, big end at -a*l."""
    t = bore * 0.24
    w = bore * 0.16
    big_r, small_r = bore * 0.30, bore * 0.18
    beam_len = l - big_r - small_r * 0.6
    side = vcross(a, k)
    pts = []
    # I-beam approximated by a slab plus two flanges, built along -a.
    def slab(width, depth, center):
        return box_along(center, a, beam_len, side, width, k, depth)
    shank = comp([slab(w * 0.45, t, vmul(a, -(small_r + beam_len / 2))),
                  slab(w * 1.25, t * 0.28, vadd(vmul(a, -(small_r + beam_len / 2)), vmul(k, t * 0.36))),
                  slab(w * 1.25, t * 0.28, vadd(vmul(a, -(small_r + beam_len / 2)), vmul(k, -t * 0.36)))])
    small = cyl(small_r, t, vmul(k, -t / 2), k)
    big = cyl(big_r, t, vadd(vmul(a, -l), vmul(k, -t / 2)), k)
    cap_bolts = [cyl(bore * 0.045, bore * 0.5, vadd(vmul(a, -l - bore * 0.25), vmul(side, sgn * big_r * 0.95)), a)
                 for sgn in (-1, 1)]
    return comp([shank, small, big] + cap_bolts)


def box_along(center, ax, la, bx, lb, cx_, lc):
    """Box centered at center with edges along unit vectors ax, bx, cx_."""
    b = Part.makeBox(la, lb, lc, V(-la / 2, -lb / 2, -lc / 2))
    m = FreeCAD.Matrix(ax[0], bx[0], cx_[0], center[0],
                       ax[1], bx[1], cx_[1], center[1],
                       ax[2], bx[2], cx_[2], center[2],
                       0, 0, 0, 1)
    return b.transformGeometry(m)


def crankshaft(kin, throws, journal_r, pin_r, web_t, web_w, front, rear):
    """throws: list of (s, psi). Built at theta=0 in world frame around kin.c."""
    k = kin.k
    solids = []
    ss = [s for s, _ in throws]
    for (s, psi) in throws:
        d = kin.dir(psi)
        side = vcross(k, d)
        base = vadd(kin.c, vmul(k, s))
        pin_len = web_w * 0.75
        solids.append(cyl(pin_r, pin_len, vadd(base, vmul(d, kin.r), vmul(k, -pin_len / 2)), k))
        for sgn in (-1, 1):
            wc = vadd(base, vmul(k, sgn * (pin_len / 2 + web_t / 2)), vmul(d, kin.r * 0.35))
            solids.append(box_along(wc, d, kin.r * 2.4, side, web_w, k, web_t))
            # counterweight
            cw = vadd(base, vmul(k, sgn * (pin_len / 2 + web_t / 2)), vmul(d, -kin.r * 0.75))
            solids.append(box_along(cw, d, kin.r * 1.0, side, web_w * 1.45, k, web_t))
    lo, hi = min(ss) - front, max(ss) + rear
    solids.append(cyl(journal_r, hi - lo, vadd(kin.c, vmul(k, lo)), k))
    return comp(solids)


# ---------------------------------------------------------------- inline engines
def inline_engine(spec):
    n, bore, stroke, l, pitch = spec["n"], spec["bore"], spec["stroke"], spec["rod"], spec["pitch"]
    r = stroke / 2
    ch, plen = bore * 0.36, bore * 0.72
    diesel = spec["kind"] == "diesel"
    kin = Kin((0, 0, 0), (1, 0, 0), (0, 0, 1), r, l)
    xs = [(i - (n - 1) / 2) * pitch for i in range(n)]
    L = n * pitch + 40
    W = bore + 70
    deck = r + l + ch + 1.5
    hh = bore * (0.95 if diesel else 0.85) + 20
    parts = []

    def P(name, label, group, mat, shape, info, pos=(0, 0, 0), rot=None, extras=None):
        e = {"label": label, "group": group, "info": info}
        if extras:
            e.update(extras)
        parts.append({"name": name, "shape": shape, "mat": mat, "pos": pos, "rot": rot, "extras": e})

    # Block with real bores and a crankcase cavity so the moving parts are housed, not buried.
    zb = -55
    block = box(L, W + 30, deck - zb, (0, 0, (deck + zb) / 2))
    cav = box(L - 24, 2 * (r + bore * 0.45), (l - r - 5) - zb + 1, (0, 0, (zb - 1 + (l - r - 5)) / 2))
    block = block.cut(cav)
    for x in xs:
        block = block.cut(cyl(bore / 2 + 0.6, deck + 2, (x, 0, 0)))
    ribs = [box(10, 8, deck - 60, (x + pitch / 2, sg * (W / 2 + 18), (deck + 40) / 2)) for x in xs[:-1] for sg in (-1, 1)]
    P("block", "Cylinder block", "Structure", "castIron" if diesel else "aluminium", comp([block] + ribs),
      "%d bores of %d mm in one casting; the deck sits %.0f mm above the crank axis." % (n, bore, deck))

    pan = loft_rect(-L / 2 + 8, L / 2 - 8, (W + 20) / 2, zb, zb - (130 if diesel else 105), (W - 30) / 2)
    P("oilpan", "Oil pan", "Lubrication", "black" if diesel else "aluminium", pan,
      "The sump: holds the oil the pump lifts to every bearing.")

    head = box(L - 4, W + 18, hh, (0, 0, deck + hh / 2))
    for x in xs:
        head = head.cut(cyl(bore / 2 - 2, 8, (x, 0, deck - 1)))  # combustion chamber recess
    P("head", "Cylinder head", "Structure", "aluminium", head,
      "Closes the bores; carries the valves, ports and %s." % ("injectors" if diesel else "spark plugs"))

    cz = deck + hh + 22
    cover_h = 50
    cover = box(L - 30, W - 6, cover_h, (0, 0, deck + hh + cover_h / 2))
    try:
        cover = cover.makeFillet(14, [e for e in cover.Edges if e.BoundBox.ZMax > deck + hh + cover_h - 1])
    except Exception:
        pass
    P("cover", "Cam cover", "Valvetrain", "black" if diesel else "paint", cover,
      "Seals the valvetrain and keeps the oil mist in.")

    cam_ys = [0] if diesel else [-bore * 0.26, bore * 0.26]
    cams = []
    for ci, cy in enumerate(cam_ys):
        center = (0, cy, cz)
        lobes = []
        for i, x in enumerate(xs):
            for j, dx in enumerate((-bore * 0.2, bore * 0.2)):
                ph = math.radians(spec["throws"][i] / 2 + (90 if j else 0) + ci * 40)
                off = (0, math.cos(ph) * 6, math.sin(ph) * 6)
                lobes.append(cyl(15, 12, vadd((x + dx - 6, cy, cz), off), (1, 0, 0)))
        shaft = cyl(9, L - 20, (-L / 2 + 10, cy, cz), (1, 0, 0))
        name = "camshaft" if diesel else ("cam_exhaust" if cy < 0 else "cam_intake")
        P(name, "Camshaft" if diesel else ("Exhaust camshaft" if cy < 0 else "Intake camshaft"), "Valvetrain", "steel",
          comp([moved(shaft, (0, -cy, -cz))] + [moved(s, (0, -cy, -cz)) for s in lobes]),
          "Turns at half crank speed; each lobe opens one valve once per four-stroke cycle.",
          pos=center, extras={"spin": {"axis": glb.dir_to_gltf((1, 0, 0)), "ratio": 0.5}})
        cams.append(name)

    # moving parts
    throws = [(x, math.radians(t)) for x, t in zip(xs, spec["throws"])]
    crank = crankshaft(kin, throws, bore * 0.29, bore * 0.25, bore * 0.2, bore * 0.75, pitch * 0.5 + 10, pitch * 0.5 + 10)
    flywheel_x = -L / 2 - 25
    fw_r = bore * (1.75 if diesel else 1.5)
    flywheel = comp([cyl(fw_r, 26, (flywheel_x - 26, 0, 0), (1, 0, 0)),
                     cyl(bore * 0.29, L / 2 - 20 + 26, (flywheel_x - 1, 0, 0), (1, 0, 0))])
    teeth = [box_along((flywheel_x - 13, fw_r * math.cos(t), fw_r * math.sin(t)), (1, 0, 0), 22,
                       (0, -math.sin(t), math.cos(t)), 5, (0, math.cos(t), math.sin(t)), 9)
             for t in [i * 2 * math.pi / 110 for i in range(110)]]
    pulley_x = L / 2 + 30
    pulley = comp([cyl(bore * 0.85, 30, (pulley_x, 0, 0), (1, 0, 0)), cyl(bore * 0.3, 60, (L / 2 - 30, 0, 0), (1, 0, 0))])
    P("crankshaft", "Crankshaft", "Rotating assembly", "forged", crank,
      "Turns the pistons' up-and-down push into rotation. Throws at %s degrees." % ", ".join(str(t) for t in spec["throws"]),
      extras={"spin": {"axis": glb.dir_to_gltf((1, 0, 0)), "ratio": 1}})
    P("flywheel", "Flywheel and ring gear", "Rotating assembly", "steel", comp([flywheel] + teeth),
      "Stores energy between power strokes; the starter meshes with its %d teeth." % len(teeth),
      extras={"spin": {"axis": glb.dir_to_gltf((1, 0, 0)), "ratio": 1}})
    P("pulley", "Crank pulley", "Accessories", "black", pulley, "Drives the accessory belt.",
      extras={"spin": {"axis": glb.dir_to_gltf((1, 0, 0)), "ratio": 1}})

    cyls = []
    for i, (x, psi) in enumerate(throws):
        a, pin, cp = kin.pose(0, x, 0, psi)
        sk, rings, gpin = piston_shape(bore, ch, plen, a, "bowl" if diesel else "flat")
        P("piston%d" % (i + 1), "Piston %d" % (i + 1), "Rotating assembly", "piston", comp([sk, gpin]),
          "%d mm across; travels %d mm from bottom to top dead centre." % (bore, stroke), pos=pin)
        P("rings%d" % (i + 1), "Rings %d" % (i + 1), "Rotating assembly", "black", rings,
          "Three rings seal combustion pressure above and scrape oil below.", pos=pin)
        P("rod%d" % (i + 1), "Connecting rod %d" % (i + 1), "Rotating assembly", "forged", rod_shape(l, bore, a, kin.k),
          "%d mm centre to centre; links piston %d to its crank throw." % (l, i + 1), pos=pin, rot=rod_rotation(a, pin, cp))
        cyls.append({"pistons": ["piston%d" % (i + 1), "rings%d" % (i + 1)], "rod": "rod%d" % (i + 1),
                     "s": x, "alpha": 0, "psi": psi, "axis": glb.dir_to_gltf(a)})

    zport = deck + hh * 0.45
    # Intake (+Y)
    yh = (W + 18) / 2
    runners = [pipe([(x, yh, zport), (x, yh + 70, zport + 30), (x * 0.9, yh + 105, zport + 95)], bore * 0.2) for x in xs]
    plenum = cyl(bore * 0.55, L * 0.92, (-L * 0.46, yh + 110, zport + 105), (1, 0, 0))
    if diesel:
        P("intake", "Intake manifold", "Air", "aluminium", comp(runners + [plenum]),
          "Charge air from the intercooler is shared out to all %d cylinders." % n)
    else:
        throttle = cyl(bore * 0.38, 70, (L * 0.46, yh + 110, zport + 105), (1, 0, 0))
        P("intake", "Intake manifold", "Air", "black", comp(runners + [plenum]),
          "Equal-length runners share the plenum's air between the %d cylinders." % n)
        P("throttle", "Throttle body", "Air", "aluminium", throttle, "The driver's foot: a butterfly valve metering the air.")
    # Exhaust (-Y)
    if diesel:
        log = cyl(bore * 0.33, L * 0.95, (-L * 0.47, -yh - 75, zport - 10), (1, 0, 0))
        stubs = [seg((x, -yh + 2, zport - 10), (x, -yh - 75, zport - 10), bore * 0.22) for x in xs]
        P("exhaust", "Exhaust manifold", "Exhaust", "exhaust", comp([log] + stubs),
          "A cast log collecting all six exhaust pulses for the turbine.")
        tx, ty, tz = 0.0, -yh - 150, zport + 40
        turbine = comp([Part.makeTorus(68, 34, V(tx - 40, ty, tz), V(1, 0, 0)), cyl(55, 70, (tx - 75, ty, tz), (1, 0, 0)),
                        seg((tx - 40, -yh - 75, zport - 10), (tx - 40, ty + 30, tz - 40), 32),
                        seg((tx - 75, ty, tz), (tx - 200, ty, tz), 45)])
        compressor = comp([Part.makeTorus(70, 36, V(tx + 60, ty, tz), V(1, 0, 0)), cyl(58, 60, (tx + 30, ty, tz), (1, 0, 0)),
                           cyl(62, 120, (tx + 90, ty, tz), (1, 0, 0))])
        core = cyl(32, 70, (tx - 15, ty, tz), (1, 0, 0))
        P("turbine", "Turbine housing", "Turbocharger", "exhaust", turbine,
          "Exhaust gas spins the turbine wheel inside this scroll.")
        P("compressor", "Compressor housing", "Turbocharger", "aluminium", compressor,
          "The compressor wheel on the same shaft packs air for the intake.")
        P("turbocore", "Turbo bearing housing", "Turbocharger", "steel", core,
          "Oil-fed bearings let the shaft spin at well over 100,000 rpm.")
        cooler = pipe([(tx + 60, ty, tz + 70), (tx + 60, ty, deck + hh + 140), (L / 2 + 60, 0, deck + hh + 140),
                       (L / 2 + 60, yh + 110, zport + 105), (L * 0.45, yh + 110, zport + 105)], 38)
        P("chargepipe", "Charge-air pipe", "Air", "blue", cooler,
          "Carries compressed air from the turbo, via the intercooler, to the intake.")
        injectors = [comp([cyl(9, 70, (x, 0, deck + hh + cover_h - 20)), cyl(13, 28, (x, 0, deck + hh + cover_h + 30))]) for x in xs]
        rail = cyl(10, L * 0.85, (-L * 0.42, 40, deck + hh + cover_h + 30), (1, 0, 0))
        feeds = [seg((x, 40, deck + hh + cover_h + 30), (x, 0, deck + hh + cover_h + 44), 4) for x in xs]
        P("injectors", "Injectors", "Fuel", "brass", comp(injectors), "Spray diesel straight into each hot, compressed charge: no spark needed.")
        P("fuelrail", "Common rail", "Fuel", "steel", comp([rail] + feeds), "Holds fuel at very high pressure for every injector.")
        bell = Part.makeCone(fw_r + 40, fw_r + 25, 110, V(flywheel_x + 20, 0, 0), V(-1, 0, 0))
        bell = bell.cut(Part.makeCone(fw_r + 30, fw_r + 15, 112, V(flywheel_x + 21, 0, 0), V(-1, 0, 0)))
        P("bellhousing", "Flywheel housing", "Structure", "castIron", bell, "Bolts the engine to the gearbox around the flywheel.")
        filt = cyl(48, 150, (L * 0.15, yh + 15, zb - 20), (0, 0.4, -0.9))
        P("oilfilter", "Oil filter", "Lubrication", "paint", filt, "Strains the oil before it reaches the bearings.")
    else:
        heads = [pipe([(x, -yh + 2, zport), (x, -yh - 55, zport - 10), (x * 0.8, -yh - 80, zport - 120),
                       (x * 0.25, -yh - 88, zport - 215), (0, -yh - 90, zport - 250)], bore * 0.17) for x in xs]
        down = pipe([(0, -yh - 90, zport - 250), (0, -yh - 90, zb - 60), (-L * 0.45, -yh - 90, zb - 95)], bore * 0.25)
        P("exhaust", "Exhaust headers", "Exhaust", "exhaust", comp(heads + [down]),
          "Four primaries merge in a collector so each pulse helps draw out the next.")
        coils = [comp([cyl(14, 40, (x, 0, deck + hh + cover_h - 10)), box(42, 30, 26, (x, 0, deck + hh + cover_h + 40))]) for x in xs]
        P("coils", "Ignition coils", "Ignition", "black", comp(coils), "One coil per plug fires the charge near top dead centre.")
        alt = comp([cyl(62, 110, (L / 2 - 120, yh + 40, zb + 120), (1, 0, 0)), cyl(28, 25, (L / 2 - 10, yh + 40, zb + 120), (1, 0, 0))])
        P("alternator", "Alternator", "Accessories", "aluminium", alt, "Belt-driven generator that charges the battery.")
        filt = cyl(42, 95, (L * 0.1, -W / 2 - 30, zb + 40), (0, -0.5, -0.86))
        P("oilfilter", "Oil filter", "Lubrication", "blue", filt, "Strains the oil before it reaches the bearings.")

    tcover = box(30, W - 10, deck + hh - zb, (L / 2 + 13, 0, (deck + hh + zb) / 2))
    P("timingcover", "Timing cover", "Valvetrain", "black" if diesel else "aluminium", tcover,
      "Encloses the chain that keeps the camshaft%s in step with the crank." % ("" if diesel else "s"))

    kinematics = {"r": glb.SCALE * r, "l": glb.SCALE * l, "origin": glb.to_gltf((0, 0, 0)),
                  "axis": glb.dir_to_gltf(kin.k), "e0": glb.dir_to_gltf(kin.e0), "e1": glb.dir_to_gltf(kin.e1),
                  "cylinders": [dict(c, s=c["s"] * glb.SCALE) for c in cyls], "cams": cams}
    return parts, kinematics


# ---------------------------------------------------------------- radial engine
def radial_engine(spec):
    n, bore, stroke, l = spec["n"], spec["bore"], spec["stroke"], spec["rod"]
    r = stroke / 2
    ch, plen = bore * 0.36, bore * 0.72
    k, e0 = (0, 1, 0), (0, 0, 1)  # crank axis points forward (+Y), cylinder 1 straight up
    kin = Kin((0, 0, 0), k, e0, r, l)
    parts = []

    def P(name, label, group, mat, shape, info, pos=(0, 0, 0), rot=None, extras=None):
        e = {"label": label, "group": group, "info": info}
        if extras:
            e.update(extras)
        parts.append({"name": name, "shape": shape, "mat": mat, "pos": pos, "rot": rot, "extras": e})

    Rc = 230
    case = cyl(Rc, 200, (0, -100, 0), k)
    case = case.cut(cyl(Rc - 25, 170, (0, -85, 0), k))
    alphas = [2 * math.pi * i / n for i in range(n)]
    for al in alphas:
        d = kin.dir(al)
        case = case.cut(seg(vmul(d, Rc - 40), vmul(d, Rc + 5), bore / 2 + 1))
    bosses = [seg(vmul(kin.dir(al), Rc - 12), vmul(kin.dir(al), Rc + 18), bore / 2 + 16) for al in alphas]
    bosses = [b.cut(seg(vmul(kin.dir(al), Rc - 14), vmul(kin.dir(al), Rc + 20), bore / 2 + 1)) for b, al in zip(bosses, alphas)]
    P("crankcase", "Crankcase", "Structure", "olive", comp([case] + bosses),
      "Two-piece drum carrying all %d cylinders around a single crank throw." % n)
    nose = Part.makeCone(Rc - 30, 110, 170, V(0, 100, 0), V(*k))
    P("nosecase", "Nose case", "Propeller drive", "olive", nose, "Houses the thrust bearing that carries the propeller's pull.")
    rear = comp([cyl(Rc - 40, 110, (0, -210, 0), k), cyl(45, 120, (110, -330, 70), k), cyl(45, 120, (-110, -330, 70), k)])
    P("accessory", "Accessory case and magnetos", "Ignition", "black", rear,
      "Two magnetos make their own spark: each cylinder has two plugs, so either can fail.")

    barrel0, barrel1 = Rc - 5, r + l + ch + 2
    head1 = barrel1 + bore * 0.62
    cyls = []
    exhaust = []
    for i, al in enumerate(alphas):
        d = kin.dir(al)
        side = vcross(k, d)
        fins = [seg(vmul(d, z), vmul(d, z + 3), bore / 2 + 22) for z in range(int(barrel0 + 30), int(barrel1 - 6), 10)]
        barrel = seg(vmul(d, barrel0), vmul(d, barrel1), bore / 2 + 9).cut(seg(vmul(d, barrel0 - 1), vmul(d, barrel1 + 1), bore / 2 + 0.6))
        P("barrel%d" % (i + 1), "Cylinder %d barrel" % (i + 1), "Cylinders", "steel", comp([barrel] + fins),
          "Steel barrel with machined fins: air, not water, carries the heat away.")
        hfins = [seg(vmul(d, z), vmul(d, z + 3), bore / 2 + 34) for z in range(int(barrel1 + 4), int(head1 - 12), 9)]
        head = seg(vmul(d, barrel1), vmul(d, head1), bore / 2 + 14)
        rockers = [box_along(vadd(vmul(d, head1 - 10), vmul(k, sg * bore * 0.33)), d, 46, side, 56, k, 34) for sg in (-1, 1)]
        plugs = [seg(vadd(vmul(d, barrel1 + 30), vmul(side, sg * (bore / 2 + 30))),
                     vadd(vmul(d, barrel1 + 30), vmul(side, sg * (bore / 2 + 52))), 9) for sg in (-1, 1)]
        P("head%d" % (i + 1), "Cylinder %d head" % (i + 1), "Cylinders", "aluminium", comp([head] + hfins + rockers),
          "Finned aluminium head with rocker boxes for one intake and one exhaust valve.")
        P("plugs%d" % (i + 1), "Spark plugs %d" % (i + 1), "Ignition", "ceramic", comp(plugs), "Two plugs per cylinder, one from each magneto.")
        tubes = [seg(vadd(vmul(d, Rc - 10), vmul(k, 110 + 0 * sg), vmul(side, sg * 28)),
                     vadd(vmul(d, head1 - 25), vmul(k, sg * bore * 0.33)), 8) for sg in (-1, 1)]
        P("pushrods%d" % (i + 1), "Pushrod tubes %d" % (i + 1), "Valvetrain", "steel", comp(tubes),
          "Pushrods run from the cam ring in the nose up to the rockers.")
        intake = seg(vadd(vmul(d, barrel1 + 20), vmul(k, -bore * 0.45)), vadd(vmul(d, Rc - 40), vmul(k, -150)), 20)
        P("intake%d" % (i + 1), "Intake pipe %d" % (i + 1), "Air", "steel", intake,
          "Feeds mixture from the supercharger section at the rear.")
        exhaust.append(seg(vadd(vmul(d, barrel1 + 25), vmul(k, -bore * 0.5)), vadd(vmul(d, 420), vmul(k, -230)), 24))
        a, pin, cp = kin.pose(0, 0, al, 0)
        sk, rings, gpin = piston_shape(bore, ch, plen, a)
        P("piston%d" % (i + 1), "Piston %d" % (i + 1), "Rotating assembly", "piston", comp([sk, gpin]),
          "%d mm across; travels %d mm per stroke." % (bore, stroke), pos=pin)
        P("rings%d" % (i + 1), "Rings %d" % (i + 1), "Rotating assembly", "black", rings, "Seal the combustion chamber.", pos=pin)
        P("rod%d" % (i + 1), ("Master rod" if i == 0 else "Link rod %d" % (i + 1)), "Rotating assembly", "forged",
          rod_shape(l, bore * (1.0 if i == 0 else 0.75), a, kin.k),
          "All %d rods share one crankpin. Shown here as simple rods; a real radial hangs eight link rods off one master rod." % n
          if i == 0 else "Rides on the master rod's big end.", pos=pin, rot=rod_rotation(a, pin, cp))
        cyls.append({"pistons": ["piston%d" % (i + 1), "rings%d" % (i + 1)], "rod": "rod%d" % (i + 1),
                     "s": 0, "alpha": al, "psi": 0, "axis": glb.dir_to_gltf(a)})
    ring = Part.makeTorus(420, 30, V(0, -230, 0), V(*k))
    P("collector", "Exhaust collector ring", "Exhaust", "exhaust", comp([ring] + exhaust),
      "Gathers all %d exhaust stubs into one ring behind the cylinders." % n)

    crank = crankshaft(kin, [(0, 0)], 60, 55, 40, 130, 210, 230)
    P("crankshaft", "Crankshaft", "Rotating assembly", "forged", crank,
      "A single throw: in a radial every cylinder works on the same crankpin.",
      extras={"spin": {"axis": glb.dir_to_gltf(k), "ratio": 1}})

    # Propeller: hub, spinner and three twisted blades, direct drive.
    py = 300
    hub = comp([cyl(55, 160, (0, 260, 0), k), cyl(95, 90, (0, py - 45, 0), k)])
    spinner = Part.makeCone(110, 4, 200, V(0, py + 40, 0), V(*k))
    blades = []
    R = spec["prop_r"]
    for b in range(3):
        secs = []
        for j, f in enumerate((0.12, 0.3, 0.5, 0.7, 0.88, 1.0)):
            rr = R * f
            chord = 190 * (0.55 + 0.45 * math.sin(math.pi * min(f, 0.9) * 0.9)) * (0.6 if f == 1.0 else 1)
            thick = chord * (0.2 - 0.11 * f)
            twist = 62 - 48 * f
            tw = math.radians(twist)
            pts = []
            for q in range(24):
                t = 2 * math.pi * q / 24
                x, y = chord / 2 * math.cos(t), thick / 2 * math.sin(t) * (1.25 if math.sin(t) > 0 else 0.6)
                pts.append(V(x * math.cos(tw) - y * math.sin(tw), py + x * math.sin(tw) + y * math.cos(tw), rr))
            bs = Part.BSplineCurve()
            bs.interpolate(pts, PeriodicFlag=True)
            w = Part.Wire([bs.toShape()])
            secs.append(w)
        blade = Part.makeLoft(secs, True)
        blade.rotate(V(0, py, 0), V(*k), b * 120)
        blades.append(blade)
    P("propeller", "Propeller", "Propeller drive", "black", comp(blades + [hub]),
      "Three blades, %.1f m across, turned directly by the crankshaft." % (2 * R / 1000),
      extras={"spin": {"axis": glb.dir_to_gltf(k), "ratio": 1}})
    parts[-1]["tol"] = 3.0  # B-spline blades tessellate very finely at the default deflection
    P("spinner", "Spinner", "Propeller drive", "aluminium", spinner, "Smooths the airflow over the hub and into the cowl.",
      extras={"spin": {"axis": glb.dir_to_gltf(k), "ratio": 1}})

    kinematics = {"r": glb.SCALE * r, "l": glb.SCALE * l, "origin": glb.to_gltf((0, 0, 0)),
                  "axis": glb.dir_to_gltf(kin.k), "e0": glb.dir_to_gltf(kin.e0), "e1": glb.dir_to_gltf(kin.e1),
                  "cylinders": cyls, "cams": []}
    return parts, kinematics


ENGINES = [
    {"id": "car", "title": "Inline-four", "kind": "petrol", "n": 4, "bore": 86, "stroke": 86, "rod": 145, "pitch": 96,
     "throws": [0, 180, 180, 0], "firing": "1-3-4-2", "cycle": "Four-stroke, spark ignition",
     "builder": inline_engine, "use": "Car",
     "summary": "Four cylinders in a row, two camshafts overhead. Pistons 1 and 4 rise while 2 and 3 fall, so the crank sees a power stroke every half turn."},
    {"id": "aircraft", "title": "Nine-cylinder radial", "kind": "radial", "n": 9, "bore": 140, "stroke": 152, "rod": 280,
     "prop_r": 1150, "firing": "1-3-5-7-9-2-4-6-8", "cycle": "Four-stroke, air-cooled, dual ignition",
     "builder": radial_engine, "use": "Aircraft",
     "summary": "Nine finned cylinders in a star around one crankpin, turning the propeller directly. An odd count lets every other cylinder fire, two turns per cycle."},
    {"id": "diesel", "title": "Turbo inline-six diesel", "kind": "diesel", "n": 6, "bore": 107, "stroke": 124, "rod": 192,
     "pitch": 124, "throws": [0, 240, 120, 120, 240, 0], "firing": "1-5-3-6-2-4", "cycle": "Four-stroke, compression ignition",
     "builder": inline_engine, "use": "Truck",
     "summary": "Six cylinders in a row: a layout whose shaking forces cancel by themselves, with no balance shafts. Compression alone ignites the fuel; a turbo recycles exhaust energy into charge air."},
]


def main():
    os.makedirs(OUT, exist_ok=True)
    index = []
    only = set(sys.argv[1:])
    for spec in ENGINES:
        if only and spec["id"] not in only:
            continue
        parts, kinematics = spec["builder"](spec)
        disp_cc = spec["n"] * math.pi / 4 * spec["bore"] ** 2 * spec["stroke"] / 1000.0
        placed = []
        for p in parts:
            s = p["shape"].copy()
            if p.get("rot"):
                q = p["rot"]  # glTF frame quaternion -> FreeCAD rotation (axis back to Z-up)
                ang = 2 * math.acos(max(-1, min(1, q[3])))
                ax = (q[0], -q[2], q[1])
                if ang > 1e-9 and any(abs(c) > 1e-12 for c in ax):
                    s.rotate(V(0, 0, 0), V(*ax), math.degrees(ang))
            s.translate(V(*p["pos"]))
            placed.append(s)
        assembly = Part.makeCompound(placed)
        bb = assembly.BoundBox
        stats = glb.write_glb(os.path.join(OUT, spec["id"] + ".glb"), spec["title"],
                              {"kinematics": kinematics, "id": spec["id"]}, parts, MATERIALS)
        assembly.exportStep(os.path.join(OUT, spec["id"] + ".step"))
        mesh = Mesh.Mesh(assembly.tessellate(1.0))
        mesh.write(os.path.join(OUT, spec["id"] + ".stl"))
        bb = mesh.BoundBox  # envelope from the mesh, not OCCT's loose B-rep box
        groups = sorted({p["extras"]["group"] for p in parts})
        entry = {k: spec[k] for k in ("id", "title", "kind", "n", "bore", "stroke", "rod", "firing", "cycle", "use", "summary")}
        entry.update({
            "displacement_cc": round(disp_cc),
            "bore_stroke_ratio": round(spec["bore"] / spec["stroke"], 3),
            "rod_ratio": round(spec["rod"] / (spec["stroke"] / 2), 2),
            "parts": len(parts), "groups": groups, "triangles": stats["triangles"], "glb_bytes": stats["bytes"],
            "envelope_mm": [round(bb.XLength), round(bb.YLength), round(bb.ZLength)],
            "files": {"glb": "models/%s.glb" % spec["id"], "step": "models/%s.step" % spec["id"], "stl": "models/%s.stl" % spec["id"]},
        })
        index.append(entry)
        print("%-9s parts=%3d tris=%7d glb=%6.1f kB  %d cc  envelope %s mm" % (
            spec["id"], len(parts), stats["triangles"], stats["bytes"] / 1024, round(disp_cc), entry["envelope_mm"]))
    path = os.path.join(OUT, "engines.json")
    if only and os.path.exists(path):  # merge, so a partial build never leaves stale figures
        old = {e["id"]: e for e in json.load(open(path))["engines"]}
        old.update({e["id"]: e for e in index})
        index = [old[s["id"]] for s in ENGINES if s["id"] in old]
    if True:
        with open(path, "w") as f:
            json.dump({"generated_by": "cad/build_engines.py", "freecad": ".".join(FreeCAD.Version()[:3]),
                       "engines": index}, f, indent=2)


if __name__ == "__main__":
    main()
