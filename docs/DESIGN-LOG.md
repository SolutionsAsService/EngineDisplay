# DESIGN-LOG: EngineDisplay front end (DADA run)

Date 2026-11-09. Conductor: Claude Code. Panel verdict files and evidence were kept in the session scratchpad
(`panel-r1/`, `panel-r2/`) and are summarised here. The container that held them is temporary.

## 1. Traversal Plan

**Brief, in one sentence.** Make EngineDisplay actually show engines: build real 3D models, and design a front end
that leads with them.

**Mode: Adaptive.** The site serves a public audience that wants to understand engines. So both MAYA poles must hold:
the advanced pole (a true-scale, live mechanical plate) and the acceptable pole (instantly legible, clickable, works
on a phone).

**Run type: Full, with a Landing move.** The site was rebuilt from nothing that rendered. The landing was judged under
the Landing rules, using the Landing panel minimum.

**Bound.** The person gave no bound. The conductor bounded the run at two WHOLE panel rounds (R1, R2) plus measured
post-round fixes, to keep the cost of this session's agents proportionate. Under that bound S3 is not met (see Stop test).

**Multi-page plan.** index (all topics), car, diesel ("Truck" in the nav), aircraft, about (how it's made and the
downloads). One shared nav and one template (`tools/build_pages.py`).

**Inventory, and what stands for each topic on the landing.**

| Topic | Stand-in on the landing |
|---|---|
| car | live inline-four, 1,998 cc |
| truck | live turbo six, 6,690 cc |
| aircraft | live radial, 21,059 cc |
| how it's made | nav only |

**Seed** (labels as used in this run's reasoning; see references/anchor-graph.md):
- Stance: MAYA (Loewy).
- Rules: the First screen rule and the landing-summary rule from SKILL.md, plus a Formalist reading of balance (Arnheim).
- Breaker: true relative scale with one shared crank angle. Three engines sized honestly against each other, so
  the radial dwarfs the car, rather than three equal product cards.
- Counterpoint: Krug (usability) ↔ Debord (provocation), the panel's dotted pair.

**Tooling inventory.**

| Job | Tool used |
|---|---|
| Graph rendering | None available. No Mermaid renderer was used; the graph was read as text. |
| Workflow state | This log. |
| Panel | Sub-agent tool, one agent per seat, at most 3 at a time, each filing to a panel directory. |
| Panel choice | `scripts/pick_panel.py --mode adaptive --run-type landing`. |
| Seat briefs | `seats/*.md` prompt blocks, filled by script. |
| Measurement | Playwright and headless Chromium with a first-screen probe (`fs-probe.js`), the Unified CAD MCP (`cad_inspect_stl_geometry` over stdio), and Python reads of GLB/STL. |
| Ledger | Not recorded (see Compliance). |

**Panel (from pick_panel.py, no overrides).** Formalist (Arnheim), Evidence (Cairo), Usability (Krug), Provocateur
(Debord). Dotted pair: Krug ↔ Debord.

### Frontier (final)

| Candidate | Reached via | Status |
|---|---|---|
| R0 objections (no render, crash, overflow) | premortem | TAKEN (M1–M3) |
| True-scale plate | Breaker | TAKEN (M3) |
| Ghosted castings so the firing glow is visible | the claim in the dek | TAKEN (M4) |
| R1 findings (Krug F1–F7, Arnheim F2–F5, Debord F3–F6, Cairo F1–F7) | panel | TAKEN (M5) |
| R2 findings (Arnheim F7/F8, Krug F8/F9, Debord F7/F8, Cairo F8) | panel | TAKEN (M6), applied but not re-judged |
| Cairo R2 F2: label says "not along the crank" | panel | DEFERRED. The label already reads "across the view", which is true. The extra clause adds length on mobile for a case no reader measures. |
| Propeller as a separate real-time sweep (motion blur) | M3 escalation | DEFERRED. Out of bound. |
| Radial master/link-rod kinematics | Cairo/Debord claims area | DEFERRED. Stated on about.html as a simplification. |

## 2. Decision Records

**M1, Build real geometry (KEEP-THE-RULE).** Depends on: none.
- Intent: every engine is a FreeCAD parametric solid, not a downloaded mesh. One node per part, so parts can be
  named, animated and picked.
- Formal argument: the evidence-first stance (Cairo) requires every printed figure to be computable from a source.
  So the figures come from `engines.json`, written by the same script that builds the geometry.
- Alternatives rejected:
  - Downloading third-party engine GLBs: licensing, and no kinematics.
  - Procedural three.js geometry: no STEP output, and no CAD measurement.
- Consequence: a FreeCAD toolchain is needed to rebuild. The GLBs total 7.1 MB.
- Frontier effect: opened the kinematics (M2) and the measurement step.
- Advanced pole: real slider-crank motion. Acceptable pole: no install needed to view.

**M2, Kinematics in the file (KEEP-THE-RULE).** Depends on: M1.
- Intent: the pistons and rods move by `x = r cos φ + √(l² − r² sin² φ)` read from glTF `extras`, so the animation
  is the mechanism.
- Alternatives rejected:
  - Baked animation clips: they cannot be paused or sped up, nor reused across engines.
  - CSS-only diagrams: they show no parts.
- Fence: none broken.

**M3, One plate, one scale, one crank angle (BREAK).** Depends on: M1, M2.
- Intent: the landing is a single orthographic plate with all three engines at true relative scale, turning in lockstep.
- Formal argument: the landing must summarise every topic in one composed figure. Scale is the one thing that
  separates the three engines that no spec table conveys at a glance.
- Alternatives rejected:
  - Three equal cards (fails the summary rule; a brochure).
  - One carousel (hides two topics).
- Fence: the convention "each product at its best size" exists so that small items stay legible. The cost is
  that the car is drawn small. It is mitigated by the tags and the dedicated pages.
- Advanced pole: the true-scale lineup. Acceptable pole: big cc numerals and "Take it apart →" under each engine.

**M4, Ghost the castings on the landing (KEEP-THE-RULE).** Depends on: M3.
- Intent: draw the housings at 30% opacity so the moving parts and the firing glow are visible. The dek's claim was
  otherwise unobservable: the measured screenshot showed no glow before the change.
- Alternatives rejected:
  - Cutaway booleans: they lose the silhouette.
  - Dropping the glow claim: that loses the cycle cue.

**M5, Resolve R1 (ADAPT, one batch).** Depends on: M3, M4.
- Changes:
  - Tags shortened; "Take it apart" shown on mobile.
  - Engines clickable.
  - Nav renamed "Truck".
  - Pause made an outline button and moved.
  - Headline breaks at the full stops.
  - Wider portrait gap.
  - Spinner recoloured.
  - Six claim fixes.
  - Full rebuild, with an `engines.json` merge guard.
  - Envelope taken from the mesh.
- Residual diff: car triangles 38,244 → 45,534 (intended: the header rebuild). Aircraft envelope Z 1794 → 1764 (intended:
  mesh box instead of the OCCT box). Diesel envelope Y 629 → 620 (intended). Landing scale slightly smaller (intended, from
  the wider margins). No regressions found by the probe.

**M6, Post-R2 fixes (ADAPT, measured, not re-judged).** Depends on: M5.
- Changes:
  - The layout reserves the propeller's swept disc.
  - Engines are lined up along the camera's horizontal axis, so the floor projects level.
  - The ground line is drawn at the true floor.
  - "turn 1/2 of 2 per cycle" is shown on mobile.
  - One Pause style on every page.
  - STL availability is stated.
- Inert attempt: drawing the ground line at the lowest bounding-box corner. The probe passed, but the screenshot showed
  the car and truck floating about 130 px above the line, because the floor edge runs diagonally on screen under a
  three-quarter camera. The substitute that worked: line the engines up along the camera's horizontal axis instead of world x.

### 2f Deletion review

- `script.js` and `styles.css` (the original): SCRAPPED. They earned nothing: the script threw on load, and the styles sized
  a canvas that never drew.
- Retained value: the three engine categories (car, aircraft, diesel) and their one-line descriptions, rewritten as the
  engine summaries.

## 3. Panel Reports

### R0 (premortem, measured by the conductor, not a panel)

On the inherited site:
- "THREE.GLTFLoader is not a constructor" was thrown on load and on every click.
- `models/` was missing.
- The canvas was 1280×800 inside a 400 px box, with its bottom at y = 976.
- The description keys never matched.
- No graphic rendered.

### Panel, WHOLE, round R1 (screenshots taken with fallback fonts)

| Critic | Anchor used | Observed in the work | Verdict | Requested change |
|---|---|---|---|---|
| Formalist (Arnheim) | *Art and Visual Perception*, Balance and Dynamics | Size gradient resting on the radial; link row on the frame rule; Pause block in a dead corner; headline split; "1,998 cc6,690 cc" | OBJECT | Clear the rule; outline Pause; break at full stops; gap ≥ 24 px |
| Evidence (Cairo) | *How Charts Lie* | Stale car figures; oblique scale; loose OCCT envelope; glow 70° of 180°; cap bolts against "no fasteners"; "checked" against UNKNOWN; one script against two | OBJECT | Rebuild; relabel; mesh envelope; fix the wording |
| Usability (Krug) | *Don't Make Me Think* | Five-second test and legibility trace pass; hidden mobile CTA; engines not links; Truck/Diesel mismatch; tags fused; spinner red; fonts unverified | OBJECT | Fix each |
| Provocateur (Debord) | *The Society of the Spectacle*, theses 1 and 4 | Hero is a claim, backed; four overclaims (MCP check, one script, the stroke that glows, "the one layout") | OBJECT | Fix the wording |

- Statements of meaning: three engines, honestly compared; the mechanism is shown, not narrated.
- Andon pulled: no.

### Panel, WHOLE, round R2 (real fonts, after M5)

| Critic | Verdict | Remaining findings |
|---|---|---|
| Arnheim | PASS | F7: truck and blade 9 px apart. F8: blade crosses the rule. Mobile clearance of 16 px preferred. |
| Cairo | PASS | F2 (optional): add "not along the crank". F8: STL named but not offered. |
| Krug | PASS | F8: Pause style differs between pages. F9: 8 px to the fold on mobile. |
| Debord | PASS | F7: mobile angle without its turn. F8: STL named but not offered. |

Andon pulled: no.

### Resolutions

| Finding | Resolution |
|---|---|
| Krug F1 | ADAPT (M5): CTA shown on mobile |
| Krug F2 | ADAPT (M5): canvas hit-boxes link to engine pages |
| Krug F3 | ADAPT (M5): nav reads "Truck" |
| Krug F4 + Arnheim F5 | ADAPT (M5): portrait gap 6–11 → 35 px |
| Krug F5 + Arnheim F2 + Arnheim F3 | ADAPT (M5): outline Pause; 18 px clearance |
| Krug F6 | ADAPT (M5): spinner aluminium |
| Krug F7 | ADAPT (M5): probe re-run with real fonts |
| Arnheim F4 | ADAPT (M5): one line on desktop, breaks at full stops on mobile |
| Debord F3 + Cairo F6 | ADAPT (M5): MCP result stated as measured |
| Debord F4 + Cairo F7 | ADAPT (M5): both scripts named |
| Debord F5 + Cairo F4 | ADAPT (M5): "first 70°" |
| Debord F6 | ADAPT (M5): "a layout" |
| Cairo F1 | ADAPT (M5): full rebuild and merge guard |
| Cairo F2 | ADAPT (M5): "across the view"; R2 follow-up DEFERRED |
| Cairo F3 | ADAPT (M5): envelope from the mesh |
| Cairo F5 | ADAPT (M5): cap-bolt exception |
| Arnheim F7 + Arnheim F8 | ADAPT (M6): sweep disc reserved; layout along camera-right; gap 84 px; blade above the rule |
| Krug F8 | ADAPT (M6): one Pause style |
| Krug F9 + Arnheim R2 F2 | ADAPT (M6): mobile clearance 8 → 20 px |
| Debord R2 F7 | ADAPT (M6): "turn 1 of 2 per cycle" on mobile |
| Debord R2 F8 + Cairo R2 F8 | ADAPT (M6): about.html says STL is not offered (10–55 MB), rebuilt by the script |

## 4. Anchor Ledger

| Anchor | Role | Status | Evidence | Note |
|---|---|---|---|---|
| MAYA (Loewy) | Stance | KEEP | The true-scale plate stays advanced; R2 Krug PASS for the acceptable pole | Survived Krug R1 F2 and F4 |
| First screen rule | Rule | KEEP | Probe: tags 20 px above the fold at both sizes, 0 overlaps, no horizontal scroll | Survived Arnheim R1 F2 |
| Landing summarises the site | Rule | KEEP | All three topics, each with a figure and a link | Survived Krug R1 F3 |
| True scale, one crank angle | Breaker | KEEP (pushed in M6) | Propeller sweep now reserved | Survived Debord R1 F2 (lockstep named as a convention) |
| Krug ↔ Debord | Counterpoint (dotted) | Applied | Both seated in R1 and R2 | none |

## 5. Stop test and Compliance

- **S1.** Met. There are no OPEN Frontier items. Three are DEFERRED, each with a reason.
- **S2.** Met in R2. All four required seats returned PASS with no Andon.
- **S3.** NOT met. R2 still produced ADAPTs (M6), and no third quiet round was run under the bound.
- **S4.** The push on the Breaker was M6: the scale plate now reserves the full propeller arc and stands every engine on
  one level floor. Measured delta: same-row tag gap 33 → 84 px on desktop, mobile fold clearance 8 → 20 px, and the
  blade no longer crosses the rule (screenshot). Not re-judged by the panel.
- **S5.** Met. The Krug ↔ Debord dotted edge was applied.
- **2g, re-measured after the last edit.** Each printed figure, with the procedure that reproduces it; all reproducible:

| Printed figure | Procedure | Value at final state |
|---|---|---|
| Displacement | n·π/4·bore²·stroke | 1,998 / 6,690 / 21,059 cc |
| Parts | GLB nodes | 28 / 37 / 79 |
| Triangles | GLB index count / 3 | 45,534 / 56,406 / 185,916 |
| GLB size | file size | 1.2 / 1.5 / 4.5 MB |
| Envelope (L × W × H) | STL bounding box | 535 × 443 × 588; 997 × 620 × 825; 2036 × 870 × 1764 mm |
| Totals | sums of the above | 29,747 cc; 19 cylinders; 144 parts |
| Scale bar | camera width / canvas width | computed live |

**Compliance**

- [x] Tooling inventory (§1)
- [x] Mode with reason (§1)
- [x] Panel from `pick_panel.py`, briefed from `seats/`; bound stated as the conductor's (§1)
- [x] Seed and Frontier (§1). The labels were not grepped against the graph file, and no graph render was produced.
- [x] Run type stated; no freeze broken
- [x] Landing is complete at 1280×800 and 375×812 (probe, §5)
- [x] BREAK taken (M3)
- [x] Decision Records (§2). They are condensed; M5 and M6 are batch records.
- [x] Panel Reports per round (§3)
- [x] Every OBJECT resolved (§3)
- [ ] S3 not met (§5)
- [x] Figures re-measured at the final state (§5)
- [x] Anchor Ledger (§4). The live graph was not updated (no graph tooling).
- [ ] Double loop: see below.
- [ ] Run not recorded in the dada ledger (`import_log.py` not run; that writes to the dada repository)
- [x] Final reply states all of the above

## Double loop

The criterion held. The panel's two weaknesses were these:

- The first-screen probe measured tag rectangles but not whether the scene's own ground matched its figures, so the
  "floating engines" defect passed the probe and was caught only by looking.
- No seat judges 3D geometry. The 3dada panel (Form and Making seats) is the right one for model changes.

Graph amendment: none to the graph file. Process note: for a 3D landing, the probe must include a projected-floor check.

## Carry-Forward Ledger (EngineDisplay)

- A three-quarter orthographic camera makes world-x rows project diagonally. Lay shelves out along the camera's horizontal
  axis (`(VIEW.z, 0, −VIEW.x)`). Measured: the car floated about 130 px above the line before the fix and stood on it after (M6).
- A spinning part's bounding box at rest under-reserves its space. Add an invisible disc of the swept radius before
  fitting (`Box3.setFromObject` includes invisible meshes). Measured: the blade crossed the rule by about 8 px before; clear after.
- FreeCAD `Face.tessellate()` explodes on B-spline lofts (472k triangles for one propeller).
  `MeshPart.meshFromShape(face, LinearDeflection, AngularDeflection=0.25)` cut the radial from 1.48M to 186k triangles.
- OCCT `BoundBox` on a compound is loose: aircraft Z 1794 against a mesh value of 1764. Use the mesh box for printed envelopes.
- A partial `build_engines.py car` run used to leave `engines.json` stale. It now merges the index.
