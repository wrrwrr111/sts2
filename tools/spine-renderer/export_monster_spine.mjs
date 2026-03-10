/**
 * Copy monster Spine assets (.skel/.atlas/.png) into public/images/monsters/spine/<name>/
 * Usage:
 *   node export_monster_spine.mjs            # export all
 *   node export_monster_spine.mjs NAME       # export one
 *   node export_monster_spine.mjs --limit 10
 */
import fs from "node:fs";
import path from "node:path";

const BASE = path.resolve(import.meta.dirname, "../..");
const MONSTERS_DIR = path.join(BASE, "extraction/raw/animations/monsters");
const OUTPUT_DIR = path.join(BASE, "public/images/monsters/spine");

function listMonsterDirs() {
  return fs
    .readdirSync(MONSTERS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
}

function copyIfExists(src, dst) {
  if (!fs.existsSync(src)) return false;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  return true;
}

function exportMonster(name) {
  const dir = path.join(MONSTERS_DIR, name);
  const skel = path.join(dir, `${name}.skel`);
  const atlas = path.join(dir, `${name}.atlas`);
  if (!fs.existsSync(skel) || !fs.existsSync(atlas)) {
    console.log(`  SKIP ${name}: missing skel/atlas`);
    return false;
  }

  const atlasText = fs.readFileSync(atlas, "utf-8");
  const pages = atlasText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.includes(":"))
    .filter((l) => l.toLowerCase().endsWith(".png"));

  const outDir = path.join(OUTPUT_DIR, name);
  let ok = true;
  ok = copyIfExists(skel, path.join(outDir, `${name}.skel`)) && ok;
  ok = copyIfExists(atlas, path.join(outDir, `${name}.atlas`)) && ok;

  if (pages.length === 0) {
    const png = path.join(dir, `${name}.png`);
    if (!copyIfExists(png, path.join(outDir, `${name}.png`))) {
      console.log(`  SKIP ${name}: missing png`);
      return false;
    }
  } else {
    for (const page of pages) {
      const src = path.join(dir, page);
      const dst = path.join(outDir, page);
      if (!copyIfExists(src, dst)) {
        console.log(`  SKIP ${name}: missing ${page}`);
        return false;
      }
    }
  }

  console.log(`  OK  ${name} -> ${path.relative(BASE, outDir)}`);
  return ok;
}

async function main() {
  const args = process.argv.slice(2);
  const limitIndex = args.indexOf("--limit");
  const limit = limitIndex >= 0 ? Number(args[limitIndex + 1]) : null;
  const target = args.find((arg) => !arg.startsWith("--") && arg !== String(limit));

  let names = listMonsterDirs();
  if (target) names = names.filter((n) => n === target);
  if (limit && Number.isFinite(limit)) names = names.slice(0, limit);

  console.log(`Exporting ${names.length} monsters...`);
  let ok = 0;
  for (const name of names) {
    if (exportMonster(name)) ok += 1;
  }
  console.log(`Done. Exported ${ok}/${names.length} monsters.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
