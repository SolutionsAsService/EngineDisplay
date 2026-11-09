// Shared 3D core: load an engine GLB built by cad/build_engines.py and drive it.
// The GLB's root node carries the slider-crank kinematics in its extras, so the
// pistons, rods, crank, cams and propeller move from geometry, not keyframes.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const loader = new GLTFLoader();

// Parts that read as the engine's skin; X-ray makes these translucent.
const HOUSING = /^(block|head\d*|cover|oilpan|timingcover|bellhousing|crankcase|barrel\d+|nosecase|accessory)$/;

export function makeRenderer(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  return renderer;
}

export function makeScene(renderer) {
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(3, 5, 4);
  scene.add(key, new THREE.HemisphereLight(0xffffff, 0x444444, 0.5));
  return scene;
}

export async function loadEngine(url, onProgress) {
  const gltf = await loader.loadAsync(url, onProgress);
  return new Rig(gltf.scene);
}

export class Rig {
  constructor(scene) {
    this.object = scene;
    const root = scene.children[0];
    this.root = root;
    this.kin = root.userData.kinematics;
    this.id = root.userData.id;
    this.parts = new Map();
    root.traverse((o) => {
      if (!o.isMesh) return;
      o.material = o.material.clone();
      o.userData.baseColor = o.material.color.clone();
      o.userData.restPos = o.position.clone();
      o.userData.restQuat = o.quaternion.clone();
      o.userData.housing = HOUSING.test(o.name);
      this.parts.set(o.name, o);
    });
    // Explode directions: from the engine's centre to each part's centre at rest.
    root.updateMatrixWorld(true);
    const all = new THREE.Box3().setFromObject(root);
    this.center = all.getCenter(new THREE.Vector3());
    this.size = all.getSize(new THREE.Vector3());
    const box = new THREE.Box3();
    for (const m of this.parts.values()) {
      box.setFromObject(m);
      const c = box.getCenter(new THREE.Vector3()).sub(this.center);
      m.userData.explode = c;
    }
    this.v = { k: vec(this.kin.axis), e0: vec(this.kin.e0), e1: vec(this.kin.e1), o: vec(this.kin.origin) };
    this.explode = 0;
    this.theta = 0;
    this.update(0);
  }

  // theta in radians of crank rotation.
  update(theta) {
    this.theta = theta;
    const { r, l, cylinders } = this.kin;
    const { k, e0, e1, o } = this.v;
    const tmp = new THREE.Vector3(), pin = new THREE.Vector3(), cp = new THREE.Vector3();
    for (const c of cylinders) {
      const a = c._a || (c._a = vec(c.axis));
      const negA = c._na || (c._na = a.clone().negate());
      const phi = theta + c.psi - c.alpha;
      const x = r * Math.cos(phi) + Math.sqrt(l * l - (r * Math.sin(phi)) ** 2);
      const base = tmp.copy(o).addScaledVector(k, c.s);
      pin.copy(base).addScaledVector(a, x);
      cp.copy(base).addScaledVector(e0, r * Math.cos(theta + c.psi)).addScaledVector(e1, r * Math.sin(theta + c.psi));
      for (const name of c.pistons) this.parts.get(name).position.copy(pin);
      const rod = this.parts.get(c.rod);
      rod.position.copy(pin);
      rod.quaternion.setFromUnitVectors(negA, cp.sub(pin).normalize());
    }
    for (const m of this.parts.values()) {
      const spin = m.userData.spin;
      if (spin) {
        m.userData._axis = m.userData._axis || vec(spin.axis);
        m.quaternion.setFromAxisAngle(m.userData._axis, theta * spin.ratio);
      }
      if (!isKinematic(m, this.kin)) m.position.copy(m.userData.restPos);
      if (this.explode) m.position.addScaledVector(m.userData.explode, this.explode);
    }
  }

  setExplode(f) {
    this.explode = f;
    this.update(this.theta);
  }

  // only: optional RegExp narrowing which housings go see-through (the landing ghosts only what hides the pistons).
  setXray(on, opacity = 0.12, only = null) {
    for (const m of this.parts.values()) {
      if (!m.userData.housing) continue;
      if (only && !only.test(m.name)) continue;
      m.material.transparent = on;
      m.material.opacity = on ? opacity : 1;
      m.material.depthWrite = !on;
      m.material.needsUpdate = true;
    }
  }

  highlight(name) {
    for (const m of this.parts.values()) {
      const hit = name && (m.name === name);
      m.material.emissive.setHex(hit ? 0xd2361c : 0x000000);
      m.material.emissiveIntensity = hit ? 0.55 : 0;
    }
  }

  // Glow piston crowns while their cylinder is early in its power stroke.
  fireGlow(thetaDeg, fireAngles) {
    this.kin.cylinders.forEach((c, i) => {
      const p = (((thetaDeg - fireAngles[i]) % 720) + 720) % 720;
      const m = this.parts.get(c.pistons[0]);
      if (m.userData.picked) return;
      const g = p < 70 ? 1 - p / 70 : 0;
      m.material.emissive.setRGB(g * 1.0, g * 0.35, g * 0.05);
      m.material.emissiveIntensity = g ? 1.2 : 0;
    });
  }
}

function isKinematic(m, kin) {
  if (!kin._names) {
    kin._names = new Set();
    for (const c of kin.cylinders) { c.pistons.forEach((n) => kin._names.add(n)); kin._names.add(c.rod); }
  }
  return kin._names.has(m.name);
}

function vec(a) { return new THREE.Vector3(a[0], a[1], a[2]); }

// Angle (deg, 0..720) at which each cylinder fires, from the firing order and the
// crank geometry: cylinder i reaches top dead centre when theta + psi - alpha = 0.
export function fireAngles(engine, kin) {
  const order = engine.firing.split('-').map((s) => parseInt(s, 10) - 1);
  const step = 720 / order.length;
  const out = new Array(order.length);
  order.forEach((cyl, j) => { out[cyl] = j * step; });
  // Sanity: the firing slot must be one of that cylinder's two TDC angles.
  kin.cylinders.forEach((c, i) => {
    const tdc = (((c.alpha - c.psi) * 180 / Math.PI) % 360 + 360) % 360;
    const ok = Math.abs(((out[i] - tdc) % 360 + 360) % 360) < 1 || Math.abs(((out[i] - tdc) % 360 + 360) % 360 - 360) < 1;
    if (!ok) console.warn('firing slot does not match TDC for cylinder', i + 1, out[i], tdc);
  });
  return out;
}

export const STROKES = ['Power', 'Exhaust', 'Intake', 'Compression'];
export function strokeOf(thetaDeg, fireAt) {
  const p = (((thetaDeg - fireAt) % 720) + 720) % 720;
  return STROKES[Math.floor(p / 180)];
}

export async function loadIndex(base = '') {
  const res = await fetch(base + 'models/engines.json');
  return (await res.json()).engines;
}

export const fmt = (n) => n.toLocaleString('en-US');
