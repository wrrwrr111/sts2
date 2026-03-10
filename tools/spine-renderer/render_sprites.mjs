/**
 * Render Spine animations to sprite sheets for monsters.
 *
 * Usage:
 *   node render_sprites.mjs            # render all monsters
 *   node render_sprites.mjs NAME       # render one monster folder name
 *   node render_sprites.mjs --limit 10 # render first N monsters
 */
import { createCanvas, loadImage } from "canvas";
import {
  TextureAtlas,
  AtlasAttachmentLoader,
  SkeletonBinary,
  Skeleton,
  AnimationState,
  AnimationStateData,
  SkeletonRenderer,
  Texture,
  Physics,
} from "@esotericsoftware/spine-canvas";
import fs from "node:fs";
import path from "node:path";

const BASE = path.resolve(import.meta.dirname, "../..");
const MONSTERS_DIR = path.join(BASE, "extraction/raw/animations/monsters");
const OUTPUT_DIR = path.join(BASE, "public/images/monsters/sprites");

const FRAME_SIZE = 256;
const SUPERSAMPLE = 2;
const RENDER_SIZE = FRAME_SIZE * SUPERSAMPLE;
const PADDING = 16 * SUPERSAMPLE;
const FRAME_COUNT = 30;
const FPS = 30;
const SHADOW_NAMES = new Set(["shadow", "shadow2", "ground", "ground_shadow"]);
const IDLE_NAMES = ["idle_loop", "idle", "Idle_loop", "Idle", "rest_idle", "rest_loop", "loop", "animation"];

class NodeTexture extends Texture {
  constructor(image) {
    super(image);
  }
  setFilters() {}
  setWraps() {}
  dispose() {}
}

function pickAnimation(skelData) {
  for (const name of IDLE_NAMES) {
    const anim = skelData.findAnimation(name);
    if (anim) return anim;
  }
  return skelData.animations.length > 0 ? skelData.animations[0] : null;
}

function computeBounds(skeleton) {
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const slot of skeleton.slots) {
    const att = slot.getAttachment();
    if (!att || !att.computeWorldVertices) continue;
    const sn = slot.data.name.toLowerCase();
    const an = (att.name || "").toLowerCase();
    if (SHADOW_NAMES.has(sn) || SHADOW_NAMES.has(an)) continue;
    const verts = new Float32Array(1000);
    const nf = att.worldVerticesLength || 8;
    try {
      att.computeWorldVertices(slot, 0, nf, verts, 0, 2);
      for (let i = 0; i < nf; i += 2) {
        if (verts[i] < minX) minX = verts[i];
        if (verts[i] > maxX) maxX = verts[i];
        if (verts[i + 1] < minY) minY = verts[i + 1];
        if (verts[i + 1] > maxY) maxY = verts[i + 1];
      }
    } catch {}
  }
  if (!isFinite(minX)) return null;
  return { minX, minY, maxX, maxY };
}

async function loadSkeleton(monsterDir, name) {
  const skelPath = path.join(monsterDir, `${name}.skel`);
  const atlasPath = path.join(monsterDir, `${name}.atlas`);
  if (!fs.existsSync(skelPath) || !fs.existsSync(atlasPath)) {
    return null;
  }

  const atlasText = fs.readFileSync(atlasPath, "utf-8");
  const atlas = new TextureAtlas(atlasText);

  for (const page of atlas.pages) {
    const pngPath = path.join(monsterDir, page.name);
    if (!fs.existsSync(pngPath)) return null;
    const img = await loadImage(pngPath);
    page.setTexture(new NodeTexture(img));
  }

  const loader = new AtlasAttachmentLoader(atlas);
  const bin = new SkeletonBinary(loader);
  const skelData = bin.readSkeletonData(new Uint8Array(fs.readFileSync(skelPath)));
  return { skelData, atlas };
}

async function renderSpriteSheet(monsterDir, name) {
  const loaded = await loadSkeleton(monsterDir, name);
  if (!loaded) {
    console.log(`  SKIP ${name}: missing files`);
    return false;
  }

  const { skelData } = loaded;
  const anim = pickAnimation(skelData);
  if (!anim) {
    console.log(`  SKIP ${name}: no animation`);
    return false;
  }

  const stateData = new AnimationStateData(skelData);
  const state = new AnimationState(stateData);
  state.setAnimation(0, anim.name, true);

  const skeleton = new Skeleton(skelData);
  skeleton.setToSetupPose();
  state.apply(skeleton);
  skeleton.updateWorldTransform(Physics.reset);

  const duration = anim.duration || 1;
  const dt = duration / FRAME_COUNT;

  let bounds = null;
  for (let i = 0; i < FRAME_COUNT; i += 1) {
    if (i > 0) state.update(dt);
    state.apply(skeleton);
    skeleton.updateWorldTransform(Physics.reset);
    const frameBounds = computeBounds(skeleton);
    if (!frameBounds) continue;
    if (!bounds) {
      bounds = { ...frameBounds };
    } else {
      bounds.minX = Math.min(bounds.minX, frameBounds.minX);
      bounds.minY = Math.min(bounds.minY, frameBounds.minY);
      bounds.maxX = Math.max(bounds.maxX, frameBounds.maxX);
      bounds.maxY = Math.max(bounds.maxY, frameBounds.maxY);
    }
  }

  if (!bounds) {
    console.log(`  SKIP ${name}: no renderable bounds`);
    return false;
  }

  const sw = bounds.maxX - bounds.minX;
  const sh = bounds.maxY - bounds.minY;
  const avail = RENDER_SIZE - PADDING * 2;
  const scale = Math.min(avail / sw, avail / sh);

  const cols = Math.ceil(Math.sqrt(FRAME_COUNT));
  const rows = Math.ceil(FRAME_COUNT / cols);

  const sheetCanvas = createCanvas(FRAME_SIZE * cols, FRAME_SIZE * rows);
  const sheetCtx = sheetCanvas.getContext("2d");
  sheetCtx.clearRect(0, 0, sheetCanvas.width, sheetCanvas.height);

  // Reset animation for rendering frames
  const renderState = new AnimationState(stateData);
  renderState.setAnimation(0, anim.name, true);
  const renderSkeleton = new Skeleton(skelData);
  renderSkeleton.setToSetupPose();
  renderState.apply(renderSkeleton);
  renderSkeleton.updateWorldTransform(Physics.reset);

  for (let i = 0; i < FRAME_COUNT; i += 1) {
    if (i > 0) renderState.update(dt);
    renderState.apply(renderSkeleton);
    renderSkeleton.updateWorldTransform(Physics.reset);

    const frameCanvas = createCanvas(RENDER_SIZE, RENDER_SIZE);
    const ctx = frameCanvas.getContext("2d");
    ctx.clearRect(0, 0, RENDER_SIZE, RENDER_SIZE);
    ctx.save();
    ctx.translate(RENDER_SIZE / 2, RENDER_SIZE / 2);
    ctx.scale(scale, -scale);
    ctx.translate(-(bounds.minX + bounds.maxX) / 2, -(bounds.minY + bounds.maxY) / 2);
    const renderer = new SkeletonRenderer(ctx);
    renderer.triangleRendering = true;
    renderer.draw(renderSkeleton);
    ctx.restore();

    const outCanvas = createCanvas(FRAME_SIZE, FRAME_SIZE);
    const outCtx = outCanvas.getContext("2d");
    outCtx.drawImage(frameCanvas, 0, 0, FRAME_SIZE, FRAME_SIZE);

    const col = i % cols;
    const row = Math.floor(i / cols);
    sheetCtx.drawImage(outCanvas, col * FRAME_SIZE, row * FRAME_SIZE);
  }

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const outPath = path.join(OUTPUT_DIR, `${name}.png`);
  fs.writeFileSync(outPath, sheetCanvas.toBuffer("image/png"));

  const meta = {
    frameWidth: FRAME_SIZE,
    frameHeight: FRAME_SIZE,
    columns: cols,
    rows,
    frameCount: FRAME_COUNT,
    fps: FPS,
  };
  fs.writeFileSync(path.join(OUTPUT_DIR, `${name}.json`), JSON.stringify(meta));
  console.log(`  OK  ${name} -> ${path.relative(BASE, outPath)}`);
  return true;
}

function listMonsterDirs() {
  return fs
    .readdirSync(MONSTERS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}

async function main() {
  const args = process.argv.slice(2);
  const limitIndex = args.indexOf("--limit");
  const limit = limitIndex >= 0 ? Number(args[limitIndex + 1]) : null;
  const target = args.find((arg) => !arg.startsWith("--") && arg !== String(limit));

  let names = listMonsterDirs();
  if (target) names = names.filter((n) => n === target);
  if (limit && Number.isFinite(limit)) names = names.slice(0, limit);

  console.log(`Rendering ${names.length} monsters...`);
  let ok = 0;
  for (const name of names) {
    const dir = path.join(MONSTERS_DIR, name);
    const result = await renderSpriteSheet(dir, name);
    if (result) ok += 1;
  }
  console.log(`Done. Rendered ${ok}/${names.length} sprite sheets.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
