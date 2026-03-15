# sts2

thanks https://github.com/ptrlrd/spire-codex

## 一键更新（推荐）
当你把新版本游戏文件放到 `extraction/` 后，执行：

```bash
# 用 ILSpy 反编译 DLL 到 extraction/decompiled
DOTNET_ROOT=/opt/homebrew/Cellar/dotnet/10.0.103/libexec DOTNET_ROLL_FORWARD=Major ~/.dotnet/tools/ilspycmd -p -o extraction/decompiled extraction/sts2.dll
```

然后执行：

```bash
python3 tools/update_from_extraction.py
```

这个脚本会自动做：
- 解析数据（`tools/parsers/parse_all.py`）
- 复制图片（`tools/copy_images.py`）
- 压缩图片（`tools/compress_images.py`）
- 生成 diff 报告（`tools/diff_data.py --record`）

图片导出/压缩会自动记录 md5 缓存，避免重复导出和重复处理：
- `tools/.cache/copy_images_md5.json`
- `tools/.cache/compress_images_md5.json`
- `tools/.cache/source_images_md5.json`（基线，可选；用于差异跳过）

`copy_images.py` 和 `compress_images.py` 会自动读取该基线文件（如果存在），对已匹配基线的图片直接跳过。

说明：
- 默认自动对比 `HEAD`，不需要手动传 `--old-ref`
- 脚本会把“上次处理的版本号”记录到 `tools/.cache/update_state.json`
- 只有检测到 `extraction/raw/release_info.json` 版本和上次记录不同，才会执行整套流程
- 如果你要强制执行：`--force`
- 如需手动指定对比基准，仍可传：`--old-ref <ref>`
- 游戏版本默认从 `extraction/raw/release_info.json` 自动读取
- 如果自动识别不到，可以手动传：`--game-version 0.99.0`

常用参数：

```bash
# 不压缩图片（更快）
python3 tools/update_from_extraction.py --skip-compress

# 只更新数据和图片，不生成 diff
python3 tools/update_from_extraction.py --no-diff
```

## 单独压缩图片
```bash
python3 tools/compress_images.py --root public/images --max 300 --quality 90 --png-colors 0
```

默认会跳过：`public/images/monsters/sprites/`（避免压缩怪物精灵图）。

## 清理缓存（可选）
```bash
rm -rf tools/.cache
```
