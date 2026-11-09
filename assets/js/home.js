// Landing plate: all three engines in one orthographic view, at one scale,
// turning on one shared crank angle.
import * as THREE from 'three';
import { makeRenderer, makeScene, loadEngine, loadIndex, fireAngles, fmt } from './engine-core.js';

const stage = document.getElementById('stage');
const canvas = stage.querySelector('canvas');
const status = stage.querySelector('.loading');
const renderer = makeRenderer(canvas);
const scene = makeScene(renderer);
const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -50, 50);
const VIEW = new THREE.Vector3(0.62, 0.42, 1).normalize();
camera.position.copy(VIEW).multiplyScalar(10);
camera.lookAt(0, 0, 0);
camera.updateMatrixWorld();

const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
let playing = !reduce;
const btn = document.getElementById('play');
btn.setAttribute('aria-pressed', String(playing));
btn.textContent = playing ? 'Pause' : 'Play';
btn.addEventListener('click', () => {
  playing = !playing;
  btn.setAttribute('aria-pressed', String(playing));
  btn.textContent = playing ? 'Pause' : 'Play';
});

const ORDER = ['car', 'diesel', 'aircraft'];
let engines = [], rigs = [], fires = [], holders = [];

async function boot() {
  engines = await loadIndex();
  fillCompare(engines);
  const byId = Object.fromEntries(engines.map((e) => [e.id, e]));
  let loaded = 0;
  rigs = await Promise.all(ORDER.map(async (id) => {
    const rig = await loadEngine(byId[id].files.glb);
    loaded += 1;
    status.textContent = `Loading engines ${loaded}/3`;
    return rig;
  }));
  status.remove();
  rigs.forEach((rig, i) => {
    const holder = new THREE.Group();
    holder.add(rig.object);
    if (rig.id === 'aircraft') holder.rotation.y = Math.PI; // propeller toward the viewer
    scene.add(holder);
    holders.push(holder);
    fires.push(fireAngles(byId[rig.id], rig.kin));
    rig.engine = byId[rig.id];
    rig.setXray(true, 0.3); // ghost the castings so the moving parts, and the firing glow, show
    makeTag(rig, i);
  });
  layout();
  requestAnimationFrame(tick);
}

function makeTag(rig, i) {
  const e = rig.engine;
  const a = document.createElement('a');
  a.className = 'tag';
  a.href = `${e.id}.html`;
  a.setAttribute('aria-label', `${e.title}, ${fmt(e.displacement_cc)} cc: open the ${e.use.toLowerCase()} engine`);
  a.innerHTML = `<span class="cc">${fmt(e.displacement_cc)} cc</span><span class="nm">${e.use} · ${e.n} cyl</span><span class="go">Take it apart →</span>`;
  stage.appendChild(a);
  rig.tag = a;
}

const groundEls = [];
let screenRects = new Map();
// The engines themselves are links too: a click inside an engine's box opens its page.
canvas.style.cursor = 'default';
stage.addEventListener('click', (ev) => {
  if (ev.target !== canvas) return;
  const r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  for (const [id, b] of screenRects) if (x >= b.x0 && x <= b.x1 && y >= b.y0 && y <= b.y1) location.href = `${id}.html`;
});
stage.addEventListener('pointermove', (ev) => {
  if (ev.target !== canvas) return;
  const r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  canvas.style.cursor = [...screenRects.values()].some((b) => x >= b.x0 && x <= b.x1 && y >= b.y0 && y <= b.y1) ? 'pointer' : 'default';
});
function layout() {
  // The plate must end at the fold: size the stage from where it starts.
  const top = stage.getBoundingClientRect().top + scrollY;
  stage.style.height = `${Math.max(300, innerHeight - top - 2)}px`;
  const W = stage.clientWidth, H = stage.clientHeight;
  renderer.setSize(W, H, false);
  const portrait = W / H < 0.95;
  const shelves = portrait ? [['aircraft'], ['car', 'diesel']] : [['car', 'diesel', 'aircraft']];
  const byId = Object.fromEntries(rigs.map((r, i) => [r.id, holders[i]]));
  // Place: reset, then put each engine's bounding box on its shelf.
  let s = 0.004; // world metres per pixel, refined below
  const gapX = portrait ? 1.25 : 0.42;
  for (let pass = 0; pass < 3; pass++) {
    const labelGap = (portrait ? 136 : 74) * s;
    let y = 0;
    for (let si = shelves.length - 1; si >= 0; si--) {
      let x = 0, tallest = 0;
      for (const id of shelves[si]) {
        const h = byId[id];
        h.position.set(0, 0, 0);
        h.updateMatrixWorld(true);
        const b = new THREE.Box3().setFromObject(h);
        const size = b.getSize(new THREE.Vector3());
        h.position.set(x - b.min.x, y - b.min.y, -(b.min.z + b.max.z) / 2);
        x += size.x + gapX;
        tallest = Math.max(tallest, size.y);
      }
      const shift = (x - gapX) / 2;
      for (const id of shelves[si]) byId[id].position.x -= shift;
      y += tallest + labelGap;
    }
    s = fit(W, H, portrait);
  }
  placeOverlays(W, H, shelves, byId);
}

function corners(obj) {
  obj.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(obj);
  const out = [];
  for (const x of [b.min.x, b.max.x]) for (const y of [b.min.y, b.max.y]) for (const z of [b.min.z, b.max.z]) out.push(new THREE.Vector3(x, y, z));
  return out;
}

function fit(W, H, portrait) {
  const inv = camera.matrixWorldInverse;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const h of holders) for (const c of corners(h)) {
    const v = c.applyMatrix4(inv);
    x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
  }
  const pad = { l: 12, r: 12, t: 40, b: portrait ? 82 : 116 };
  const s = Math.max((x1 - x0) / (W - pad.l - pad.r), (y1 - y0) / (H - pad.t - pad.b));
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  camera.left = cx - (s * W) / 2 - (s * (pad.l - pad.r)) / 2;
  camera.right = camera.left + s * W;
  camera.bottom = cy - (s * H) / 2 - (s * (pad.b - pad.t)) / 2;
  camera.top = camera.bottom + s * H;
  camera.updateProjectionMatrix();
  return s;
}

function toScreen(v, W, H) {
  const p = v.clone().project(camera);
  return { x: (p.x + 1) / 2 * W, y: (1 - p.y) / 2 * H };
}

function placeOverlays(W, H, shelves, byId) {
  groundEls.forEach((g) => g.remove());
  groundEls.length = 0;
  const rects = new Map();
  for (const [i, h] of holders.entries()) {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const c of corners(h)) { const p = toScreen(c, W, H); x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y); }
    rects.set(rigs[i].id, { x0, x1, y0, y1 });
  }
  for (const shelf of shelves) {
    const rs = shelf.map((id) => rects.get(id));
    const y = Math.max(...rs.map((r) => r.y1)) + 4;
    const g = document.createElement('div');
    g.className = 'ground';
    const left = Math.min(...rs.map((r) => r.x0)), right = Math.max(...rs.map((r) => r.x1));
    Object.assign(g.style, { left: `${left}px`, width: `${right - left}px`, top: `${y}px` });
    stage.appendChild(g);
    groundEls.push(g);
    for (const id of shelf) {
      const r = rects.get(id);
      const tag = rigs.find((x) => x.id === id).tag;
      let cx = (r.x0 + r.x1) / 2;
      tag.style.top = `${y + 8}px`;
      tag.style.left = `${cx}px`;
      const half = tag.offsetWidth / 2;
      cx = Math.min(Math.max(cx, half + 4), W - half - 4);
      tag.style.left = `${cx}px`;
    }
  }
  // One metre, measured on the camera's horizontal axis.
  const pxPerM = W / (camera.right - camera.left);
  const bar = document.querySelector('.scalebar i');
  bar.style.width = `${Math.round(pxPerM * 0.5)}px`;
  document.querySelector('.scalebar span').textContent = W < 600 ? '0.5 m across the view' : '0.5 m across the view, all three engines';
  screenRects = rects;
}

let theta = 0, last = performance.now();
const angleEl = document.querySelector('.angle b');
const strokeEl = document.querySelector('.angle span');
function tick(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (playing) theta += dt * Math.PI * 1.2; // 36 rpm on screen: slow enough to follow one piston
  const deg = (theta * 180 / Math.PI) % 720;
  rigs.forEach((r, i) => { r.update(theta); r.fireGlow(deg, fires[i]); });
  angleEl.textContent = `${Math.floor(deg % 360)}°`;
  strokeEl.textContent = deg < 360 ? 'first turn of the cycle' : 'second turn of the cycle';
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

let rt;
addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => rigs.length && layout(), 80); });

boot().catch((err) => {
  status.textContent = 'The 3D view needs WebGL and the model files. ' + err.message;
  console.error(err);
});

function fillCompare(list) {
  const rows = [
    ['Layout', (e) => e.title],
    ['Cylinders', (e) => e.n],
    ['Bore × stroke', (e) => `${e.bore} × ${e.stroke} mm`],
    ['Displacement', (e) => `${fmt(e.displacement_cc)} cc`],
    ['Bore / stroke', (e) => e.bore_stroke_ratio.toFixed(2)],
    ['Rod / crank radius', (e) => e.rod_ratio.toFixed(2)],
    ['Firing order', (e) => e.firing],
    ['Cycle', (e) => e.cycle],
    ['Modelled parts', (e) => e.parts],
    ['Envelope (mm)', (e) => e.envelope_mm.join(' × ')],
  ];
  const order = ['car', 'diesel', 'aircraft'].map((id) => list.find((e) => e.id === id));
  const t = document.getElementById('compare');
  t.innerHTML = `<thead><tr><th scope="col"></th>${order.map((e) => `<th scope="col"><a href="${e.id}.html">${e.use}</a></th>`).join('')}</tr></thead>` +
    `<tbody>${rows.map(([k, f]) => `<tr><th scope="row">${k}</th>${order.map((e) => `<td class="n">${f(e)}</td>`).join('')}</tr>`).join('')}</tbody>`;
}
