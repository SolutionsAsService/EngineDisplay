# EngineDisplay

Three engines (a car inline-four, a turbo inline-six truck diesel and a nine-cylinder aircraft radial) modelled as
parametric solids in FreeCAD and shown in the browser at true relative scale. Their pistons, rods, crank, cams and
propeller move by real slider-crank geometry.

- `index.html`: all three engines on one plate, one scale, one shared crank angle
- `car.html`, `diesel.html`, `aircraft.html`: one engine on the bench (orbit, run, explode, X-ray, live firing chart, parts list)
- `about.html`: how the models are made, with GLB and STEP downloads

## Run it

Static site, no build step:

```bash
npx serve .        # or: python3 -m http.server
```

three.js r160 loads from jsDelivr through an import map; fonts load from Google Fonts.

## Rebuild the models

Everything in `models/` comes from one script:

```bash
freecadcmd cad/build_engines.py          # or FreeCAD's python: /path/to/freecad/bin/python cad/build_engines.py
python3 tools/build_pages.py             # rewrite the HTML from models/engines.json
```

`cad/build_engines.py` writes `<id>.glb` (one node per part, PBR materials, kinematics in the root node's `extras`),
`<id>.step`, `<id>.stl` (git-ignored, for measurement) and `engines.json` (every figure the pages print). Change a
bore, stroke, rod length, cylinder count or throw angle in `ENGINES` and rerun. `cad/glb.py` is the small GLB
writer. It meshes each B-rep face on its own so edges stay crisp.

Tested with FreeCAD 1.1.3 (conda-forge) on Linux. Ubuntu 24.04 has no `freecad` apt package, so install it with
`micromamba create -p /opt/freecad -c conda-forge freecad`.

## Kinematics in the GLB

The root node's `extras.kinematics` holds the crank radius `r`, rod length `l`, crank axis and reference directions, and
for each cylinder its offset `s` along the crank, its axis angle `alpha` and its throw angle `psi` (radians). The pin
then sits at `x = r cos(phi) + sqrt(l^2 - r^2 sin^2(phi))` along the cylinder axis, where `phi = theta + psi - alpha`.
Parts with `extras.spin` rotate about their own origin at `ratio` x crank speed (cams 0.5, crank and propeller 1).

## Measuring

The STL exports were checked with the [Unified CAD MCP](https://github.com/SolutionsAsService/unified-CAD-MCP)
(`cad_inspect_stl_geometry`, units mm). All three report 0 inverted shells. Full integrity is UNKNOWN because the
meshes exceed the tool's triangle limit.

The models are generic teaching models, not any manufacturer's design. See `about.html` for what is simplified.

## Licence

MIT. See [LICENSE](LICENSE).
