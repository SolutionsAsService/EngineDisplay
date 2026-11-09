"""Write the site's HTML pages from one template and models/engines.json.

    python3 tools/build_pages.py

Static output (no build step at serve time): index.html, car.html, diesel.html,
aircraft.html, about.html. Every figure printed in the HTML comes from engines.json.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = json.load(open(os.path.join(ROOT, "models", "engines.json")))
BY = {e["id"]: e for e in ENG["engines"]}
ORDER = ["car", "diesel", "aircraft"]
fmt = "{:,}".format

IMPORTMAP = """<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>"""


def page(name, title, desc, body, script=None):
    nav = [("index.html", "Engines"), ("car.html", "Car"), ("diesel.html", "Truck"),
           ("aircraft.html", "Aircraft"), ("about.html", "How it's made")]
    links = "".join('<a href="%s"%s>%s</a>' % (h, ' aria-current="page"' if h == name else "", t) for h, t in nav)
    s = '<script type="module" src="%s"></script>' % script if script else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="assets/img/plate.png">
<link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/css/site.css">
{IMPORTMAP}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="mast">
  <a class="brand" href="index.html">Engine<b>Display</b></a>
  <nav class="nav" aria-label="Site">{links}</nav>
</header>
<main id="main">
{body}
</main>
<footer class="foot">Models are generic, illustrative engines built as parametric solids in FreeCAD {ENG["freecad"]} by
<code>cad/build_engines.py</code>; they are not any manufacturer's design. Source and STEP files:
<a href="https://github.com/SolutionsAsService/EngineDisplay">github.com/SolutionsAsService/EngineDisplay</a>. MIT licence.</footer>
{s}
</body>
</html>
"""
    with open(os.path.join(ROOT, name), "w") as f:
        f.write(html)


def home():
    total = sum(BY[i]["displacement_cc"] for i in ORDER)
    parts = sum(BY[i]["parts"] for i in ORDER)
    body = f"""<div class="plate">
  <h1><span>Three engines.</span> <em>One crank angle.</em> <span>One scale.</span></h1>
  <p class="dek">A car's {BY['car']['displacement_cc']/1000:.1f}-litre four, a truck's {BY['diesel']['displacement_cc']/1000:.1f}-litre six and an aircraft's {BY['aircraft']['displacement_cc']/1000:.1f}-litre radial, drawn to the same ruler and turning together. A glowing piston has just fired. Pick one to take it apart.</p>
  <div class="stage" id="stage" aria-label="The three engines side by side at true relative scale, animated">
    <canvas aria-hidden="true"></canvas>
    <div class="loading">Loading engines 0/3</div>
    <div class="scalebar" aria-hidden="true"><span>0.5 m</span><i></i></div>
    <div class="angle" aria-live="off">Crank <b>0°</b><span></span></div>
    <button class="ctl" id="play" type="button" aria-pressed="true">Pause</button>
  </div>
</div>
<section aria-labelledby="h-strokes"><div class="wrap">
  <h2 id="h-strokes">Every one of them does the same four things</h2>
  <p class="lede">Each cylinder repeats a cycle of four strokes over two turns of the crank. What differs is how many cylinders share the work, how they are arranged, and what lights the fuel.</p>
  <div class="strokes">
    <div><b>1</b><h3>Intake</h3>The piston falls and draws in air (and, in a petrol engine, fuel).</div>
    <div><b>2</b><h3>Compression</h3>It rises and squeezes the charge, in the diesel hard enough to make it hot enough to ignite.</div>
    <div class="p"><b>3</b><h3>Power</h3>The charge burns and drives the piston down. Its first 70° make the piston crown glow.</div>
    <div><b>4</b><h3>Exhaust</h3>It rises again and pushes the burnt gas out, ready to start over.</div>
  </div>
</div></section>
<section aria-labelledby="h-compare"><div class="wrap">
  <h2 id="h-compare">Side by side</h2>
  <p class="lede">{fmt(total)} cc across {sum(BY[i]['n'] for i in ORDER)} cylinders and {parts} modelled parts. Every figure below is computed from the CAD source; the envelope is the mesh's length × width × height.</p>
  <div class="scroll-x"><table class="spec" id="compare"></table></div>
</div></section>"""
    page("index.html", "EngineDisplay: three engines at one scale",
         "A car inline-four, a turbo diesel six and a nine-cylinder aircraft radial, modelled in FreeCAD and animated at true relative scale.",
         body, "assets/js/home.js")


def engine(eid):
    e = BY[eid]
    others = [o for o in ORDER if o != eid]
    body = f"""<div class="bench" data-engine="{eid}">
  <div class="viewer" id="viewer">
    <canvas aria-label="Interactive 3D model of the {e['title'].lower()}; drag to orbit, scroll or pinch to zoom"></canvas>
    <div class="hud"><h1>{e['title']}</h1><span class="cc">{fmt(e['displacement_cc'])} cc · {e['n']} cylinders · {e['use']}</span></div>
    <div class="tip" role="status"></div>
    <div class="controls">
      <button class="ctl" id="play" type="button" aria-pressed="true">Pause</button>
      <label>Speed <input id="speed" type="range" min="0.1" max="3" step="0.1" value="1"></label>
      <label>Explode <input id="explode" type="range" min="0" max="1.2" step="0.02" value="0"></label>
      <button class="ctl" id="xray" type="button" aria-pressed="true">X-ray</button>
    </div>
  </div>
  <aside class="panel">
    <p>{e['summary']}</p>
    <table class="spec">
      <tr><th scope="row">Bore × stroke</th><td class="n">{e['bore']} × {e['stroke']} mm</td></tr>
      <tr><th scope="row">Displacement</th><td class="n">{fmt(e['displacement_cc'])} cc</td></tr>
      <tr><th scope="row">Rod length</th><td class="n">{e['rod']} mm ({e['rod_ratio']:.2f} × crank radius)</td></tr>
      <tr><th scope="row">Firing order</th><td class="n">{e['firing']}</td></tr>
      <tr><th scope="row">Cycle</th><td>{e['cycle']}</td></tr>
    </table>
    <h3 style="margin-top:20px">Firing chart <span id="crank" style="font-family:var(--mono);font-size:14px;font-weight:500"></span></h3>
    <div class="firing" id="firing" aria-live="off"></div>
    <div class="info" id="info"><b>Pick a part</b>Tap a part in the model or the list below to see what it does.</div>
    <h3>Parts ({e['parts']})</h3>
    <div class="bom" id="bom"></div>
    <div class="next">{''.join('<a href="%s.html">%s →</a>' % (o, BY[o]['title']) for o in others)}</div>
  </aside>
</div>"""
    page(eid + ".html", "%s · EngineDisplay" % e["title"],
         "%s: %s cc, %d cylinders, firing order %s. An interactive FreeCAD model you can run, explode and X-ray." % (
             e["title"], fmt(e["displacement_cc"]), e["n"], e["firing"]),
         body, "assets/js/engine-page.js")


def about():
    rows = "".join(
        f"<tr><th scope='row'><a href='{i}.html'>{BY[i]['title']}</a></th><td class='n'>{BY[i]['parts']}</td>"
        f"<td class='n'>{fmt(BY[i]['triangles'])}</td><td class='n'>{BY[i]['glb_bytes']/1e6:.1f} MB</td>"
        f"<td><a href='models/{i}.glb' download>GLB</a> · <a href='models/{i}.step' download>STEP</a></td></tr>" for i in ORDER)
    body = f"""<section aria-labelledby="h-made" style="border-top:0"><div class="wrap">
  <h2 id="h-made">How the models are made</h2>
  <p class="lede">Nothing here is a downloaded mesh. One Python script, <code>cad/build_engines.py</code>, builds every part as a solid in FreeCAD {ENG['freecad']} from a handful of numbers per engine: cylinder count, bore, stroke, rod length, cylinder pitch and crank throw angles. Change a number, run it and then <code>tools/build_pages.py</code>, and the block, crank, pistons, rods and the site's tables all follow.</p>
  <h3>From solids to the page</h3>
  <ol class="lede">
    <li>FreeCAD builds each part with its own origin: pistons at the gudgeon pin, rods at the small end, the crank on its axis.</li>
    <li>Each face is meshed separately, so edges stay crisp, and written to a GLB with one node per part and the crank geometry (radius, rod length, cylinder axes, throw angles) stored in the file.</li>
    <li>In the browser, the pistons and rods are placed every frame by slider-crank geometry, so the animation is the mechanism, not a recorded clip.</li>
    <li>The same parts are exported as STEP (for any CAD program, offered below) and as STL, which is not offered for download (10 to 55 MB) but is rebuilt by the script; the STL was inspected with the Unified CAD MCP's <code>cad_inspect_stl_geometry</code>: 0 inverted shells on all three; the full integrity check did not run because the meshes exceed the tool's triangle limit.</li>
  </ol>
  <h3>Downloads</h3>
  <div class="scroll-x"><table class="spec"><thead><tr><th scope="col">Engine</th><th scope="col">Parts</th><th scope="col">Triangles</th><th scope="col">GLB</th><th scope="col">Files</th></tr></thead><tbody>{rows}</tbody></table></div>
  <h3 style="margin-top:28px">What is simplified</h3>
  <p class="lede">These are teaching models, not engineering drawings. Valves, the oil pump, gaskets and fasteners (apart from the connecting-rod cap bolts) are left out. The radial's link rods are drawn as plain rods all riding one crankpin, rather than hanging off a master rod. Proportions follow the bore, stroke and rod length; detail parts are sized by eye.</p>
</div></section>"""
    page("about.html", "How it's made · EngineDisplay",
         "How EngineDisplay's engines are built as parametric FreeCAD solids and animated in the browser by slider-crank geometry.", body)


if __name__ == "__main__":
    home()
    for i in ORDER:
        engine(i)
    about()
    print("wrote index.html, %s, about.html" % ", ".join(i + ".html" for i in ORDER))
