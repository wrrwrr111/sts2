# 点赞系统（Cloudflare Worker + D1）

## 功能

- 支持点赞与点踩，分别独立统计。
- 同一个人可重复投票。
- 服务端限流：同一人对同一对象的同一动作，在 `THROTTLE_SECONDS` 内会被拒绝（429）。
- 前端点击节流：`VotePanel` 会合并短时间连续点击（防抖 240ms + 最小发送间隔 800ms），减少请求次数。
- 前端只显示总数，不显示“我已点赞”状态。

## API

路由支持两种写法（方便你把 Worker 绑到 `/api/*`）：

- `/votes`
- `/api/votes`

### 1) 查询总数

`GET /api/votes?entityType=card&entityId=strike`

返回：

```json
{
  "ok": true,
  "data": {
    "entityType": "card",
    "entityId": "strike",
    "likeCount": 12,
    "dislikeCount": 3
  }
}
```

### 2) 提交投票

`POST /api/votes`

```json
{
  "entityType": "card",
  "entityId": "strike",
  "action": "like"
}
```

被节流时返回 `429`，包含：

```json
{
  "ok": false,
  "error": {
    "code": "RATE_LIMITED",
    "retryAfterSeconds": 5
  }
}
```

## D1 初始化

在 `workers/votes/` 目录执行：

```bash
# 1) 创建 D1（若你还没建）
wrangler d1 create sts2_votes

# 2) 把返回的 database_id 填到 wrangler.toml

# 3) 执行迁移（远端）
wrangler d1 migrations apply DB --remote
```

## 部署 Worker

```bash
cd workers/votes

# 建议设置盐值（不要写死在仓库）
wrangler secret put ACTOR_SALT

# 发布
wrangler deploy
```

## 查看日志

```bash
# 查看实时日志
wrangler tail --config workers/votes/wrangler.toml
```

可用 `LOG_LEVEL` 控制日志量（`debug`/`info`/`warn`/`error`）。
默认是 `warn`（仅输出警告和错误）；排查时可临时改成 `debug`。

## 挂到 /api

你要求路径是 `/api`，建议在 Cloudflare Dashboard 给这个 Worker 配路由：

- `your-domain.com/api/*`

这样前端默认 `PUBLIC_VOTE_API_BASE=/api` 就能直接工作。

## 本地开发代理

本项目已在 `astro.config.mjs` 内支持开发代理。

在根目录 `.env` 或 `.env.local` 配置：

```bash
VOTE_API_PROXY_TARGET=https://sts2.urarawin.com
```

然后启动开发环境后，请求 `http://localhost:4321/api/votes` 会自动转发到上述目标。

## 前端环境变量

默认不配也可用（走 `/api`）。

如果你把 Worker 部署在独立域名，比如 `https://vote.example.com`，再加：

```bash
PUBLIC_VOTE_API_BASE=https://vote.example.com/api
```

并在 Worker 的 `CORS_ORIGIN` 里允许你站点域名。

## 常见问题

1. `no such table: vote_counters`

未执行 D1 迁移。运行：

```bash
wrangler d1 migrations apply DB --remote --config workers/votes/wrangler.toml
```

2. `Required Worker name missing`

在仓库根目录执行 wrangler 时，需要显式指定配置文件：

```bash
wrangler secret put ACTOR_SALT --config workers/votes/wrangler.toml
```
