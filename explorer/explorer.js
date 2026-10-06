// Project Horae 3D explorer: the real CAD parts (cad/web.py) and the KiCad board, exploded, recoloured and labelled.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const BASE = new URL("./", import.meta.url);
const $ = id => document.getElementById(id);
const stage = $("ex-stage");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

let manifest, renderer, labels, scene, camera, controls, shadow, raf = null;
const parts = new Map();          // key -> { info, node, meshes: [], base: Vector3 }
const state = { t: 0, target: 0, colorway: null, selected: null, hover: null, cut: false, strap: true, dock: false, labels: false };
const textures = {};

// ---------------------------------------------------------------- materials
function srgb(hex) { return new THREE.Color(hex); }   // three converts sRGB hex to linear itself

function noiseTexture(kind) {
  if (textures[kind]) return textures[kind];
  const n = 512, c = document.createElement("canvas"); c.width = c.height = n;
  const g = c.getContext("2d"), img = g.createImageData(n, n), d = img.data;
  let seed = kind === "cf" ? 7 : 13;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < n * n; i++) { d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = 128; d[i * 4 + 3] = 255; }
  if (kind === "cf") {             // short chopped fibres: thin streaks along the print lines
    for (let k = 0; k < 2600; k++) {
      const x0 = rnd() * n, y0 = rnd() * n, len = 10 + rnd() * 40, a = (rnd() - 0.5) * 0.35, v = 90 + rnd() * 120;
      for (let s = 0; s < len; s++) {
        const x = Math.floor(x0 + s * Math.cos(a)) & (n - 1), y = Math.floor(y0 + s * Math.sin(a)) & (n - 1), i = (y * n + x) * 4;
        d[i] = d[i + 1] = d[i + 2] = v;
      }
    }
  } else {                         // glitter: sparse bright flakes
    for (let k = 0; k < 900; k++) {
      const x = Math.floor(rnd() * n), y = Math.floor(rnd() * n), i = (y * n + x) * 4;
      d[i] = d[i + 1] = d[i + 2] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.NoColorSpace;
  return (textures[kind] = t);
}

function finishMaterial(hex, finish) {
  const f = manifest.finishes[finish] || manifest.finishes.plastic;
  const m = new THREE.MeshPhysicalMaterial({ color: srgb(hex), metalness: f.metallic, roughness: f.roughness });
  if (f.opacity < 1) { m.transparent = true; m.opacity = f.opacity; m.transmission = 0.35; m.thickness = 0.4; }
  if (finish === "cf") { m.roughnessMap = noiseTexture("cf"); m.bumpMap = noiseTexture("cf"); m.bumpScale = 0.6; }
  if (finish === "glitter") {
    m.metalnessMap = noiseTexture("glitter"); m.metalness = 1; m.roughnessMap = noiseTexture("glitter");
    m.roughness = 0.25; m.clearcoat = 0.6; m.clearcoatRoughness = 0.15;
  }
  if (finish === "gloss") { m.clearcoat = 0.4; m.clearcoatRoughness = 0.2; }
  if (finish === "tpu" || finish === "tpu_clear" || finish === "strap") { m.sheen = 0.4; m.sheenRoughness = 0.7; m.sheenColor = srgb(hex); }
  return m;
}

function lookOf(info) {
  // (hex, finish) of a part in the current colourway: case / TPU / strap follow the colourway, the rest is technical
  const cw = manifest.colorways[state.colorway], role = info.role;
  if (role === "case" || role === "insert") return [cw.case_hex, role === "insert" ? "matte" : cw.case_finish];
  if (role === "tpu") return [cw.tpu_hex, cw.tpu_finish];
  if (role === "dock") return [cw.case_hex, "matte"];      // the dock prints in the case colour, matte
  if (role === "strap") return [info.key.startsWith("strap") ? cw.strap_hex : "#1e1f21", "strap"];
  const fin = manifest.finishes[role] ? role : "plastic";
  return [manifest.tech[info.key] || manifest.tech[info.key.replace(/_[lr]$/, "")] || "#8a8d93", fin];
}

function applyColorway(name) {
  state.colorway = name;
  for (const p of parts.values()) {
    if (p.info.key === "pcb") continue;                 // the board keeps KiCad's own materials
    const [hex, fin] = lookOf(p.info);
    for (const mesh of p.meshes) {
      if (mesh.userData.keep) continue;                 // the e-paper face keeps its texture
      mesh.material.dispose(); mesh.material = finishMaterial(hex, fin);
    }
  }
  document.querySelectorAll("#ex-swatches button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.cw === name)));
  const cw = manifest.colorways[name];
  $("ex-cw").textContent = `${cw.case} · ${cw.tpu}${cw.inserts ? " · windows: " + cw.inserts : ""}`;
  refreshHighlight(); applyCut();
  if (state.selected) showInfo(state.selected);
}

// ---------------------------------------------------------------- scene
function backgroundColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--card").trim() || "#f6f5f0";
}

function shadowTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 256;
  const g = c.getContext("2d"), r = g.createRadialGradient(128, 128, 10, 128, 128, 128);
  r.addColorStop(0, "rgba(0,0,0,0.38)"); r.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = r; g.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}

let started = false;
async function init() {
  if (started) return;
  started = true;
  $("ex-load").hidden = true;
  stage.classList.add("ex-loading");
  try {
    manifest = await (await fetch(new URL("manifest.json", BASE))).json();
  } catch (e) { return fail("Couldn't load the model list."); }
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  if (!renderer.getContext()) return fail("WebGL isn't available in this browser.");
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.localClippingEnabled = true;
  renderer.domElement.setAttribute("role", "img");
  renderer.domElement.setAttribute("aria-label", "Interactive 3D model of the Horae watch; the controls beside it change the view");
  stage.prepend(renderer.domElement);
  labels = new CSS2DRenderer();
  labels.domElement.className = "ex-labels";
  stage.appendChild(labels.domElement);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(backgroundColor());
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(-30, 60, 40); scene.add(key);

  camera = new THREE.PerspectiveCamera(28, 1, 0.5, 2000);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08; controls.enablePan = false;   // the view re-centres itself
  controls.minDistance = 25; controls.maxDistance = 260;
  controls.autoRotate = !reduceMotion; controls.autoRotateSpeed = 0.7;
  controls.addEventListener("start", () => setSpin(false));
  resetView();

  shadow = new THREE.Mesh(new THREE.PlaneGeometry(70, 40), new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2;
  scene.add(shadow);

  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  let done = 0;
  const progress = () => { $("ex-progress").textContent = `Loading model… ${Math.round(++done / 3 * 100)}%`; };
  const [caseGltf, pcbGltf, face] = await Promise.all([
    loader.loadAsync(new URL(manifest.files.case, BASE).href).then(g => (progress(), g)),
    loader.loadAsync(new URL(manifest.files.pcb, BASE).href).then(g => (progress(), g)),
    new THREE.TextureLoader().loadAsync(new URL(manifest.face.file, BASE).href).then(t => (progress(), t)),
  ]).catch(() => [null, null, null]);
  if (!caseGltf) return fail("Couldn't load the 3D model.");

  const byKey = Object.fromEntries(manifest.parts.map(p => [p.key, p]));
  const root = new THREE.Group(); scene.add(root);
  const addPart = (info, node) => {
    const group = new THREE.Group(); group.add(node); root.add(group);
    const meshes = []; node.traverse(o => { if (o.isMesh) { meshes.push(o); o.userData.key = info.key; } });
    parts.set(info.key, { info, node: group, meshes });
  };
  caseGltf.scene.scale.setScalar(1000);              // metres -> mm
  caseGltf.scene.updateMatrixWorld(true);
  for (const child of [...caseGltf.scene.children]) {
    const info = byKey[child.name];
    if (!info) continue;
    child.applyMatrix4(caseGltf.scene.matrixWorld);   // bake the mm scale into the part
    addPart(info, child);
  }
  const pcb = pcbGltf.scene; pcb.scale.setScalar(1000);
  pcb.position.set(...manifest.pcb_offset);
  addPart(byKey.pcb, pcb);
  parts.get("pcb").meshes.forEach(m => { m.material = m.material.clone(); });

  face.colorSpace = THREE.SRGBColorSpace; face.anisotropy = 8;
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(...manifest.face.size), new THREE.MeshStandardMaterial({ map: face, roughness: 0.85 }));
  screen.rotation.x = -Math.PI / 2; screen.position.set(...manifest.face.center);
  screen.userData.key = "display"; screen.userData.keep = true;
  parts.get("display").node.add(screen); parts.get("display").meshes.push(screen);

  manifest.hotspots.forEach((h, i) => {
    const el = document.createElement("div"); el.className = "ex-hot"; el.textContent = String(i + 1);
    el.title = h.label;
    const obj = new CSS2DObject(el); obj.position.set(...h.pos);
    parts.get("pcb").node.add(obj);
  });

  buildUi();
  applyColorway(manifest.hero);
  setStrap(true); setDock(false); setLabels(false);
  stage.classList.remove("ex-loading"); stage.classList.add("ex-ready");
  $("ex-progress").textContent = "";
  bindPointer(); resize(); new ResizeObserver(resize).observe(stage);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { scene.background = new THREE.Color(backgroundColor()); });
  new IntersectionObserver(([e]) => e.isIntersecting ? start() : stop()).observe(stage);
}

function fail(msg) {
  stage.classList.remove("ex-loading");
  $("ex-progress").textContent = msg + " The rendered views are in the build log below.";
}

function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false); labels.setSize(w, h);
  camera.aspect = w / h; camera.updateProjectionMatrix();
}

function resetView() {
  lastZoom = 1; focus = null;
  camera.position.set(-62, 46, 78);
  controls.target.set(0, 3.4, 0);
  camera.updateProjectionMatrix();
}

// ---------------------------------------------------------------- explode / visibility
const ease = x => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;

let lastZoom = 1, focus = null;
function layout() {
  const e = ease(state.t);
  const zoom = 1 + 0.55 * e;                          // pull the camera back as the stack grows (keeps user zoom)
  if (Math.abs(zoom - lastZoom) > 1e-5) {
    camera.position.sub(controls.target).multiplyScalar(zoom / lastZoom).add(controls.target);
    lastZoom = zoom;
  }
  for (const p of parts.values()) {
    const [dx, dy, dz] = p.info.explode;
    p.node.position.set(dx * e, dy * e, dz * e);
  }
  const low = state.dock ? manifest.dock.low : -11;
  shadow.position.y = (state.dock ? manifest.dock.desk : -0.05) + low * e;
  const aim = focus || new THREE.Vector3(controls.target.x * 0.9, 3.4 + (state.dock ? -2 : 6) * e, controls.target.z * 0.9);
  controls.target.lerp(aim, 0.12);
  $("ex-explode").value = String(state.t);
}

function setView(view) {
  document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  state.target = view === "exploded" ? 1 : 0;
  state.cut = view === "cut";
  applyCut();
}

const CUT = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);   // removes the half nearest the default camera
function applyCut() {
  for (const p of parts.values()) for (const m of p.meshes) {
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    for (const mat of mats) {
      mat.clippingPlanes = state.cut ? [CUT] : null;
      mat.side = state.cut && !m.userData.keep ? THREE.DoubleSide : THREE.FrontSide;   // the screen stays one-sided
      mat.needsUpdate = true;
    }
  }
}

function setVisible(test, on) { for (const p of parts.values()) if (test(p.info)) p.node.visible = on; }
function setStrap(on) { state.strap = on; setVisible(i => i.key.startsWith("strap"), on); press("ex-strap", on); }
function setDock(on) { state.dock = on; setVisible(i => i.group === "Dock", on); press("ex-dock", on); listParts(); }
function setLabels(on) {
  state.labels = on; labels.domElement.hidden = !on; press("ex-labels", on);
  $("ex-legend").hidden = !on;
  $("ex-legend").innerHTML = manifest.hotspots.map((h, i) => `<li><b>${i + 1}</b>${h.label}</li>`).join("");
}
function setSpin(on) { controls.autoRotate = on; press("ex-spin", on); }
function press(id, on) { const b = $(id); if (b) b.setAttribute("aria-pressed", String(on)); }

// ---------------------------------------------------------------- selection
function refreshHighlight() {
  for (const p of parts.values()) {
    const glow = (p.info.key === state.selected ? 0.16 : p.info.key === state.hover ? 0.08 : 0) * (p.info.key === "pcb" ? 0.5 : 1);
    for (const m of p.meshes) {
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of mats) if (mat.emissive) { mat.emissive.set(0x3d8bff); mat.emissiveIntensity = glow; }
    }
  }
  document.querySelectorAll("#ex-parts button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.key === state.selected)));
}

function keysOf(name) { return [...parts.values()].filter(p => p.info.name === name).map(p => p.info.key); }

function select(key) {
  state.selected = key;
  refreshHighlight();
  showInfo(key);
}

function showInfo(key) {
  const box = $("ex-info");
  if (!key) { box.innerHTML = `<p class="ex-hint">Tap a part in the model or the list.</p>`; return; }
  const info = parts.get(key).info, cw = manifest.colorways[state.colorway];
  const mat = info.role === "case" ? cw.case : info.role === "tpu" ? cw.tpu : info.role === "strap" && key.startsWith("strap") ? cw.strap : "";
  const size = info.size ? info.size.map(v => v.toFixed(1)).join(" × ") + " mm" : "";
  box.innerHTML = `<h3>${info.name}</h3><p>${info.desc}</p>` +
    `<p class="mono ex-meta">${[mat, size].filter(Boolean).join(" · ")}</p>` +
    `<div class="ex-actions"><button type="button" id="ex-iso">Show only this</button><button type="button" id="ex-all">Show everything</button></div>`;
  $("ex-iso").onclick = () => {
    const keep = keysOf(info.name), box = new THREE.Box3();
    for (const p of parts.values()) { p.node.visible = keep.includes(p.info.key); if (p.node.visible) box.expandByObject(p.node); }
    focus = box.getCenter(new THREE.Vector3());            // glide the orbit centre onto the part
  };
  $("ex-all").onclick = () => { for (const p of parts.values()) p.node.visible = true; setStrap(state.strap); setDock(state.dock); focus = null; };
  if (matchMedia("(min-width: 861px)").matches) box.scrollIntoView({ block: "nearest" });
}

function bindPointer() {
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), el = renderer.domElement;
  let downAt = null;
  const pick = e => {
    const r = el.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const meshes = [...parts.values()].filter(p => p.node.visible).flatMap(p => p.meshes);
    const hit = ray.intersectObjects(meshes, false).find(h => !state.cut || CUT.distanceToPoint(h.point) >= 0);
    return hit ? hit.object.userData.key : null;
  };
  el.addEventListener("pointermove", e => { if (e.pointerType !== "mouse") return; const k = pick(e); if (k !== state.hover) { state.hover = k; refreshHighlight(); el.style.cursor = k ? "pointer" : ""; } });
  el.addEventListener("pointerdown", e => { downAt = [e.clientX, e.clientY]; });
  el.addEventListener("pointerup", e => {
    if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
    const k = pick(e); select(k ? keysOf(parts.get(k).info.name)[0] : null);
  });
}

// ---------------------------------------------------------------- UI
function listParts() {
  const order = ["Case", "Strap", "Display", "Electronics", "Seals", "Dock"], seen = new Set(), groups = {};
  for (const p of parts.values()) {
    if (seen.has(p.info.name) || (p.info.group === "Dock" && !state.dock)) continue;
    seen.add(p.info.name); (groups[p.info.group] ||= []).push(p.info);
  }
  $("ex-parts").innerHTML = order.filter(g => groups[g]).map(g =>
    `<div class="ex-group"><h4 class="mono">${g}</h4>${groups[g].map(i => `<button type="button" data-key="${i.key}" aria-pressed="false">${i.name}</button>`).join("")}</div>`).join("");
  $("ex-parts").querySelectorAll("button").forEach(b => b.onclick = () => select(state.selected === b.dataset.key ? null : b.dataset.key));
  refreshHighlight();
}

function buildUi() {
  $("ex-swatches").innerHTML = Object.entries(manifest.colorways).map(([name, cw]) =>
    `<button type="button" data-cw="${name}" aria-pressed="false" aria-label="${name}: ${cw.case}" title="${name}: ${cw.case}"><i style="--c:${cw.case_hex};--r:${cw.tpu_hex}"></i><span>${name}</span></button>`).join("");
  $("ex-swatches").querySelectorAll("button").forEach(b => b.onclick = () => applyColorway(b.dataset.cw));
  document.querySelectorAll("[data-view]").forEach(b => b.onclick = () => setView(b.dataset.view));
  $("ex-explode").oninput = e => { state.t = state.target = Number(e.target.value); document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", "false")); };
  $("ex-strap").onclick = () => setStrap(!state.strap);
  $("ex-dock").onclick = () => setDock(!state.dock);
  $("ex-dock").hidden = !manifest.parts.some(p => p.group === "Dock");   // shown once the dock is exported
  $("ex-labels").onclick = () => setLabels(!state.labels);
  $("ex-spin").onclick = () => setSpin(!controls.autoRotate);
  $("ex-reset").onclick = () => { resetView(); setView("assembled"); select(null); for (const p of parts.values()) p.node.visible = true; setStrap(true); setDock(state.dock); };
  $("ex-full").onclick = () => document.fullscreenElement ? document.exitFullscreen() : stage.closest(".explorer").requestFullscreen?.();
  $("ex-dims").textContent = `${manifest.case.L.toFixed(1)} × ${manifest.case.W.toFixed(1)} × ${manifest.case.T.toFixed(2)} mm`;
  listParts(); showInfo(null);
}

// ---------------------------------------------------------------- loop
function frame() {
  raf = requestAnimationFrame(frame);
  if (Math.abs(state.target - state.t) > 1e-4) state.t += Math.sign(state.target - state.t) * Math.min(0.03, Math.abs(state.target - state.t));
  layout();
  controls.update();
  renderer.render(scene, camera);
  if (state.labels) labels.render(scene, camera);
}
function start() { if (raf === null) frame(); }
function stop() { if (raf !== null) cancelAnimationFrame(raf); raf = null; }

// ---------------------------------------------------------------- boot: load when asked, or when scrolled to on a roomy connection
$("ex-load").onclick = init;
document.querySelector(".ex-panel").addEventListener("click", () => { if (!started) init(); }, { capture: true });
const roomy = innerWidth >= 900 && !(navigator.connection && navigator.connection.saveData);
if (roomy) new IntersectionObserver(([e], o) => { if (e.isIntersecting) { o.disconnect(); init(); } }, { rootMargin: "200px" }).observe(stage);
