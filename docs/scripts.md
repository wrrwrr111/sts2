# 脚本说明

本文档汇总当前仓库可直接使用的脚本。

## 前置环境

- Node.js（用于 Astro 与 `tools/spine-renderer` 下的 Node 脚本）
- Python 3（用于 `tools/*.py`）
- Pillow（`compress_images.py` 依赖）
- 可选：ILSpy（用于把 DLL 反编译到 `extraction/decompiled`）

---

## 1. npm scripts（站点开发）

来自根目录 `package.json`：

| 命令 | 作用 |
| --- | --- |
| `npm run dev` | 本地开发服务器 |
| `npm run build` | 生产构建（输出到 `dist/`） |
| `npm run preview` | 本地预览构建产物 |
| `npm run astro` | 透传 Astro CLI |

---

## 2. 一键更新脚本

### `python3 tools/update_from_extraction.py`

用途：在更新 `extraction/` 后，一次性完成数据解析、图片同步、压缩、diff 报告。

默认执行链路：

1. `python3 tools/parsers/parse_all.py`
2. `python3 tools/copy_images.py`
3. `python3 tools/compress_images.py --root public/images --max 300 --quality 90 --png-colors 0`
4. `python3 tools/diff_data.py HEAD --record --out-dir reports/diff`

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--skip-images` | 跳过图片同步 |
| `--skip-compress` | 跳过图片压缩 |
| `--no-diff` | 跳过 diff 报告 |
| `--old-ref <ref>` | 指定 diff 基准 git ref（默认 `HEAD`） |
| `--game-version <v>` | 手动指定游戏版本号 |
| `--force` | 即使检测到版本未变化也强制执行 |

状态文件：

- `tools/.cache/update_state.json`：记录上次已处理版本

---

## 3. 数据解析脚本

### `python3 tools/parsers/parse_all.py`

用途：统一触发所有 parser，把 `extraction/` 原始数据转换为 `data/*.json`。

会覆盖/刷新多个类别文件（如 cards、characters、relics、events、monsters、potions 等）。

---

## 4. 图片同步脚本

### `python3 tools/copy_images.py`

用途：把提取的图片从 `extraction/raw/images` 归档到 `public/images`，包含卡牌、遗物、药剂、角色、怪物、orbs、icons、ancients、bosses、card_overlays 等目录。

特点：

- 按 md5 跳过未变化文件
- 支持 baseline 跳过策略（首次接入基线时避免重复覆盖）

缓存文件：

- `tools/.cache/copy_images_md5.json`
- `tools/.cache/source_images_md5.json`（可选基线）

---

## 5. 图片压缩脚本

### `python3 tools/compress_images.py --root public/images --max 300 --quality 90 --png-colors 0`

用途：对图片进行尺寸/质量优化（原地处理）。

默认行为：

- 处理 `png/jpg/jpeg/webp`
- 自动跳过 `public/images/monsters/sprites/`
- 自动跳过 `atlases` 目录

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--root` | 扫描根目录 |
| `--max` | 最大宽高 |
| `--quality` | JPEG/WebP 质量 |
| `--png-colors` | PNG 量化色数，`0` 表示保留原色 |
| `--cache-file` | 压缩缓存文件路径 |
| `--baseline-file` | baseline md5 文件路径 |

缓存文件：

- `tools/.cache/compress_images_md5.json`
- `tools/.cache/source_images_md5.json`（可选基线）

---

## 6. 数据差异脚本

### `python3 tools/diff_data.py <old_ref_or_dir> [new_ref_or_dir]`

用途：比较两个版本的数据，输出实体新增/删除/修改摘要。

支持输入：

- git ref（tag/commit/branch）
- 本地目录（`data/*.json`）

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--format text|md|json` | 输出格式 |
| `--record` | 同时写入报告文件 |
| `--out-dir <dir>` | 报告目录（默认 `reports/diff`） |
| `--report-name <name>` | 报告文件名（不含扩展名） |
| `--game-version <v>` | 游戏版本号（用于 json 报告元数据） |
| `--build-id <id>` | Steam build id |
| `--codex-version <n>` | 同游戏版本下的 codex 修订号 |

---

## 7. Spine 渲染相关脚本（可选）

目录：`tools/spine-renderer/`

| 脚本 | 作用 |
| --- | --- |
| `node tools/spine-renderer/render_sprites.mjs` | 把怪物 Spine 动画渲染为精灵图与元数据（输出到 `public/images/monsters/sprites`） |
| `node tools/spine-renderer/export_monster_spine.mjs` | 导出怪物 Spine 原始资源到 `public/images/monsters/spine` |
| `node tools/spine-renderer/render_all.mjs` | 扫描 `extraction/raw/animations` 下所有 `.skel` 并渲染 |

说明：这组脚本主要用于资源补全/调试，不属于日常站点启动必需步骤。

