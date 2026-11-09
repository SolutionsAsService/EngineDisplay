// One engine on the bench: orbit, run, explode, X-ray, and pick parts.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { makeRenderer, makeScene, loadEngine, loadIndex, fireAngles, strokeOf } from './engine-core.js';

const id = document.querySelector('[data-engine]').dataset.engine;
const viewer = document.getElementById('viewer');
const canvas = viewer.querySelector('canvas');
const tip = viewer.querySelector('.tip');
const info = document.getElementById('info');
const renderer = makeRenderer(canvas);
const scene = makeScene(renderer);
const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

// X-ray opens what hides the moving parts; painted heads stay solid so each engine keeps its colour.
const SEE_THROUGH = /^(block|cover|oilpan|timingcover|bellhousing|crankcase|barrel\d+|nosecase|accessory)$/;
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
let playing = !reduce, speed = 1, theta = 0, rig, fires, picked = null;

const playBtn = document.getElementById('play');
function setPlay(v) { playing = v; playBtn.setAttribute('aria-pressed', String(v)); playBtn.textContent = v ? 'Pause' : 'Play'; }
setPlay(playing);
playBtn.addEventListener('click', () => setPlay(!playing));
document.getElementById('speed').addEventListener('input', (e) => { speed = +e.target.value; });
document.getElementById('explode').addEventListener('input', (e) => rig && rig.setExplode(+e.target.value));
const xr = document.getElementById('xray');
xr.addEventListener('click', () => {
  const on = xr.getAttribute('aria-pressed') !== 'true';
  xr.setAttribute('aria-pressed', String(on));
  rig && rig.setXray(on, 0.2, SEE_THROUGH);
});

function resize() {
  const w = viewer.clientWidth, h = viewer.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

async function boot() {
  const engines = await loadIndex();
  const engine = engines.find((e) => e.id === id);
  rig = await loadEngine(engine.files.glb);
  scene.add(rig.object);
  fires = fireAngles(engine, rig.kin);
  if (id === 'aircraft') rig.object.rotation.y = Math.PI;
  rig.setXray(xr.getAttribute('aria-pressed') === 'true', 0.2, SEE_THROUGH); // start see-through so the mechanism shows
  resize();
  frame();
  buildBom();
  buildFiring(engine);
  requestAnimationFrame(tick);
}

function frame() {
  const box = new THREE.Box3().setFromObject(rig.object);
  const c = box.getCenter(new THREE.Vector3());
  const r = box.getSize(new THREE.Vector3()).length() / 2;
  const d = r / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * (camera.aspect < 1 ? 1.25 : 0.95);
  camera.position.copy(c).add(new THREE.Vector3(0.62, 0.42, 1).normalize().multiplyScalar(d));
  camera.near = d / 100; camera.far = d * 10;
  camera.updateProjectionMatrix();
  controls.target.copy(c);
  controls.update();
}

function buildBom() {
  const groups = new Map();
  for (const m of rig.parts.values()) {
    const g = m.userData.group;
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(m);
  }
  const bom = document.getElementById('bom');
  for (const [g, list] of [...groups].sort()) {
    const h = document.createElement('h4');
    h.textContent = `${g} (${list.length})`;
    bom.appendChild(h);
    for (const m of list) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = m.userData.label;
      b.dataset.part = m.name;
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', () => pick(m.name === picked ? null : m.name));
      bom.appendChild(b);
    }
  }
}

function pick(name) {
  picked = name;
  for (const m of rig.parts.values()) m.userData.picked = m.name === name;
  rig.highlight(name);
  document.querySelectorAll('#bom button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.part === name)));
  if (!name) { info.innerHTML = '<b>Pick a part</b>Tap a part in the model or the list below to see what it does.'; return; }
  const m = rig.parts.get(name);
  info.innerHTML = `<b></b><span></span>`;
  info.querySelector('b').textContent = m.userData.label;
  info.querySelector('span').textContent = m.userData.info;
}

let firingRows = [];
function buildFiring(engine) {
  const el = document.getElementById('firing');
  firingRows = rig.kin.cylinders.map((c, i) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span>Cyl ${i + 1}</span><span class="bar"></span>`;
    el.appendChild(row);
    return row.querySelector('.bar');
  });
}

// Hover and tap picking.
const ray = new THREE.Raycaster();
const ptr = new THREE.Vector2();
let down = null;
function hit(ev) {
  const r = canvas.getBoundingClientRect();
  ptr.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ptr, camera);
  const xray = xr.getAttribute('aria-pressed') === 'true';
  const hits = ray.intersectObjects([...rig.parts.values()], false).filter((h) => !(xray && h.object.userData.housing));
  return hits[0] && hits[0].object;
}
canvas.addEventListener('pointermove', (ev) => {
  if (!rig || ev.pointerType !== 'mouse') return;
  const o = hit(ev);
  if (o) {
    const r = viewer.getBoundingClientRect();
    tip.style.display = 'block';
    tip.textContent = o.userData.label;
    tip.style.left = `${Math.min(ev.clientX - r.left + 14, r.width - 200)}px`;
    tip.style.top = `${ev.clientY - r.top + 14}px`;
  } else tip.style.display = 'none';
  if (!picked) rig.highlight(o ? o.name : null);
});
canvas.addEventListener('pointerleave', () => { tip.style.display = 'none'; if (!picked && rig) rig.highlight(null); });
canvas.addEventListener('pointerdown', (ev) => { down = [ev.clientX, ev.clientY]; });
canvas.addEventListener('pointerup', (ev) => {
  if (!rig || !down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 6) return;
  const o = hit(ev);
  pick(o ? o.name : null);
});

let last = performance.now();
const crankEl = document.getElementById('crank');
function tick(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (playing) theta += dt * Math.PI * 1.2 * speed;
  const deg = (theta * 180 / Math.PI) % 720;
  rig.update(theta);
  rig.fireGlow(deg, fires);
  firingRows.forEach((bar, i) => {
    const s = strokeOf(deg, fires[i]);
    if (bar.textContent !== s) { bar.textContent = s; bar.className = `bar ${s}`; }
  });
  crankEl.textContent = `· crank ${Math.floor(deg)}° of 720°`;
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

boot().catch((err) => {
  info.innerHTML = '<b>3D view unavailable</b>This page needs WebGL and the model files. ' + err.message;
  console.error(err);
});
