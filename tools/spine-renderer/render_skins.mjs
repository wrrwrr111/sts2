/**
 * Render skeletons that require specific skins to be set.
 */
import { createCanvas, loadImage } from "canvas";
import {
  TextureAtlas, AtlasAttachmentLoader, SkeletonBinary, Skeleton,
  AnimationState, AnimationStateData, SkeletonRenderer, Texture, Physics,
} from "@esotericsoftware/spine-canvas";
import fs from "fs";
import path from "path";

class NT extends Texture {
  constructor(i) { super(i); }
  setFilters() {}
  setWraps() {}
  dispose() {}
}

async function renderWithSkin(dir, skelName, atlasName, skinName, outPath) {
  const atlasText = fs.readFileSync(path.join(dir, atlasName + ".atlas"), "utf-8");
  const atlas = new TextureAtlas(atlasText);
  for (const page of atlas.pages) {
    const img = await loadImage(path.join(dir, page.name));
    page.setTexture(new NT(img));
  }
  const loader = new AtlasAttachmentLoader(atlas);
  const bin = new SkeletonBinary(loader);
  const sd = bin.readSkeletonData(new Uint8Array(fs.readFileSync(path.join(dir, skelName + ".skel"))));

  // List skins
  console.log(`  ${skelName} skins: ${sd.skins.map(s => s.name).join(", ")}`);

  const sk = new Skeleton(sd);

  // Set skin
  if (skinName) {
    const skin = sd.findSkin(skinName);
    if (skin) {
      sk.setSkin(skin);
      console.log(`  Set skin: ${skinName}`);
    } else {
      console.log(`  Skin "${skinName}" not found!`);
    }
  }

  sk.setToSetupPose();
  sk.setSlotsToSetupPose();

  const st = new AnimationState(new AnimationStateData(sd));
  const idleNames = ["idle_loop", "idle", "loop"];
  let found = false;
  for (const n of idleNames) {
    if (sd.findAnimation(n)) { st.setAnimation(0, n, false); st.apply(sk); found = true; break; }
  }
  if (!found && sd.animations.length > 0) {
    st.setAnimation(0, sd.animations[0].name, false);
    st.apply(sk);
  }
  sk.updateWorldTransform(Physics.reset);

  const SH = new Set(["shadow", "shadow2", "ground", "ground_shadow"]);
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  for (const slot of sk.slots) {
    const a = slot.getAttachment();
    if (!a || !a.computeWorldVertices) continue;
    if (SH.has(slot.data.name.toLowerCase())) continue;
    const v = new Float32Array(1000);
    const nf = a.worldVerticesLength || 8;
    try {
      a.computeWorldVertices(slot, 0, nf, v, 0, 2);
      for (let i = 0; i < nf; i += 2) {
        if (v[i] < x1) x1 = v[i];
        if (v[i] > x2) x2 = v[i];
        if (v[i + 1] < y1) y1 = v[i + 1];
        if (v[i + 1] > y2) y2 = v[i + 1];
      }
    } catch {}
  }
  if (!isFinite(x1)) { console.log("  No bounds for " + skelName + " (skin: " + skinName + ")"); return; }

  const RS = 1024, PAD = 40;
  const avail = RS - PAD * 2;
  const sc = Math.min(avail / (x2 - x1), avail / (y2 - y1));
  const c = createCanvas(RS, RS);
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, RS, RS);
  ctx.save();
  ctx.translate(RS / 2, RS / 2);
  ctx.scale(sc, -sc);
  ctx.translate(-(x1 + x2) / 2, -(y1 + y2) / 2);
  const renderer = new SkeletonRenderer(ctx);
  renderer.triangleRendering = true;
  renderer.draw(sk);
  ctx.restore();

  const o = createCanvas(512, 512);
  const oc = o.getContext("2d");
  oc.drawImage(c, 0, 0, 512, 512);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, o.toBuffer("image/png"));
  console.log("  OK -> " + path.basename(outPath));
}

const base = path.resolve(import.meta.dirname, "../../extraction/raw/animations/monsters");
const out = path.resolve(import.meta.dirname, "../../backend/static/images/monsters");

// Bowlbug variants — likely different skins on same skeleton
console.log("\n=== BOWLBUG ===");
await renderWithSkin(base + "/bowlbug", "bowlbug", "bowlbug", null, out + "/bowlbug_default.png");
// Try each potential skin
for (const skin of ["egg", "nectar", "rock", "silk", "default"]) {
  await renderWithSkin(base + "/bowlbug", "bowlbug", "bowlbug", skin, out + `/bowlbug_${skin}.png`);
}

// Devoted sculptor
console.log("\n=== DEVOTED SCULPTOR ===");
await renderWithSkin(base + "/devoted_sculptor", "devoted_scultpor", "devoted_sculptor", null, out + "/devoted_sculptor_default.png");
for (const skin of ["default", "coral", "slug"]) {
  await renderWithSkin(base + "/devoted_sculptor", "devoted_scultpor", "devoted_sculptor", skin, out + `/devoted_sculptor_${skin}.png`);
}

// Cultists with individual skins
console.log("\n=== CULTISTS ===");
await renderWithSkin(base + "/cultists", "cultists", "cultists", "coral", out + "/calcified_cultist.png");
await renderWithSkin(base + "/cultists", "cultists", "cultists", "slug", out + "/damp_cultist.png");

// Cubex construct
console.log("\n=== CUBEX CONSTRUCT ===");
await renderWithSkin(base + "/cubex_construct", "cubex_construct", "cubex_construct", null, out + "/cubex_construct_default.png");
