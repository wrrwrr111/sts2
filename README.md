# STS2 中文资料库

> Slay the Spire 2 fan-made database site (Astro + Tailwind)

感谢并参考：<https://github.com/ptrlrd/spire-codex>

## 当前已实现功能

- 双语站点：中文/英文路由（`/` 与 `/en`）与页面级 SEO 信息
- 全站资料页：卡牌、角色、药剂、遗物、事件、怪物六大模块
- 卡牌库：
  - 类型/稀有度/角色/费用筛选
  - 关键词/描述搜索
  - 基础版/升级版切换
- 卡牌详情：
  - 基础版与升级版并排展示
  - 生成卡牌（spawn）预览与跳转
  - 关键词补充说明
- 角色详情：
  - 基础属性、起始牌组、初始遗物、充能球（Defect）
  - 远古者相关台词/对话与事件信息展开
- 事件页：
  - 支持选项、分页内容、角色变体对话
  - 从事件文本中自动提取并聚合关联卡牌/遗物/药剂
- 怪物页：
  - 怪物基础信息、动作列表、伤害/格挡数值
  - 支持基于精灵图元数据的帧动画预览
- 文本渲染：
  - 游戏样式标签（颜色、强调、能量图标等）渲染
  - 局部文本自动链接到实体详情页
- 数据更新流程：
  - 支持从 `extraction/` 一键更新数据、图片和 diff 报告
  - 带 md5 缓存，避免重复复制与重复压缩

## 本地开发

### 1) 安装依赖

```bash
npm install
```

### 2) 启动开发环境

```bash
npm run dev
```

### 3) 构建与预览

```bash
npm run build
npm run preview
```

## 数据更新（推荐流程）

游戏文件是通过 `Godot RE Tools` 提取的。

当你把新版本游戏文件放到 `extraction/` 后：

```bash
# 用 ILSpy 反编译 DLL 到 extraction/decompiled
DOTNET_ROOT=/opt/homebrew/Cellar/dotnet/10.0.103/libexec DOTNET_ROLL_FORWARD=Major ~/.dotnet/tools/ilspycmd -p -o extraction/decompiled extraction/sts2.dll
```

然后执行：

```bash
python3 tools/update_from_extraction.py
```

该命令会按顺序执行：

1. `tools/parsers/parse_all.py`（解析结构化数据）
2. `tools/copy_images.py`（同步图片）
3. `tools/compress_images.py`（压缩图片）
4. `tools/diff_data.py --record`（生成变更报告）

常用参数：

```bash
# 不压缩图片（更快）
python3 tools/update_from_extraction.py --skip-compress

# 跳过 diff
python3 tools/update_from_extraction.py --no-diff

# 强制执行（即使版本号未变化）
python3 tools/update_from_extraction.py --force
```

## 脚本说明

完整脚本说明（含参数和输出位置）见：

- [docs/scripts.md](docs/scripts.md)

## 升级展望

- 增加统一站内搜索（跨卡牌/遗物/事件等）与 URL 参数持久化分享
- 在页面内展示数据版本与差异（直接消费 `reports/diff`）
- 增强事件/角色关联图谱（补全更多实体互链与关系可视化）
- 引入自动化更新流水线（定时解析、构建、发布）
- 增加基础测试与数据校验（解析回归、字段完整性检查）
- 增加更多游戏内容模块页面（如 powers/enchantments/keywords 专页）

## 项目目录

```text
src/                Astro 页面与组件
data/               解析后的结构化 JSON 数据
public/images/      站点静态图片资源
extraction/         从游戏提取的原始数据与反编译产物
tools/              解析、图片处理、diff 等脚本
reports/diff/       生成的数据差异报告
```

## 许可证

本仓库代码与脚本以 [MIT](./LICENSE) 协议开源。

注意：`extraction/`、`data/`、`public/images/` 中的游戏相关资源与衍生内容不属于 MIT 授权范围，其版权归原作者与版权方所有。

## 免责声明

本项目仅用于学习与交流，所有内容版权归原作者与版权方所有。
