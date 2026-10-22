# 福彩数据与预测平台（caipiao-lab）

福利彩票数据中台：4 大彩种全量历史、逐期查看与图表统计、多供应商自动同步、统计 + 机器学习预测、滚动回测验证、票夹记录、AI 解读，前后端一体、单端口部署、手机端自适应、带管理员后台。

> 预测结果是基于历史数据的概率模型输出，仅供研究参考，不构成投注建议，也不承诺任何中奖结果。

---

## 1. 功能清单

| 模块 | 能力 |
| --- | --- |
| 彩种 | 双色球 ssq / 福彩3D 3d / 七乐彩 qlc / 快乐8 kl8（不含体彩） |
| 历史 | 全量落库 16,403 期：ssq 3,517（2003-02 起）· 3d 7,786（2004-10 起）· qlc 3,000（2007-01 起）· kl8 2,100（2020-10 起） |
| 逐期查看 | 分页列表（可切彩种/日期区间/期号搜索）、单期详情（号码 / 销量 / 奖池 / 奖级明细）、CSV 导出当前筛选范围 |
| 数据源 | 供应商抽象层 + 优先级 failover：福彩官方 cwl_official → 500.com c500 → CSV 离线导入；单个源失败自动切下一个 |
| 同步 | 增量 / 全量 / 深历史补录三种模式；调度器开奖后自动拉取；SSE 实时进度；同步记录留痕 |
| 统计 | 号码频率、遗漏分布、走势图、形态分布、随机性检验（卡方） |
| 预测 | 6 种引擎：均匀基线 / 频率 / 遗漏 / 马尔可夫 / 贝叶斯平滑 / 梯度提升树 + 多模型集成；返回注数 1–100 可配 |
| 回测 | 滚动窗口（严格防未来信息泄漏）、命中数 vs 随机基线、TOP-K 命中率、logloss / Brier、逐期明细 |
| AI 解读 | 统计模型选号 + 大模型解读：支持 OpenAI / DeepSeek / Moonshot / 智谱 / 通义 / Ollama / 自定义；用户可在前台提交自己的 Key，管理员审核后启用 |
| 票夹 | 保存预测票、记录落地情况、统计命中；登录后跨设备同步，游客按设备隔离 |
| 账号 | 普通用户自助注册登录（role=user），票夹随账号同步，注册时自动迁移本设备游客票 |
| 管理后台 | 账号密码登录、运行状态、账号增删改、审计日志、登录会话吊销、AI 供应商审核 |
| 移动端 | 底部 Tab 导航（总览/历史/预测/AI/更多）+ 抽屉菜单，表格在手机上自动切成卡片 |
| 运维 | 单端口自托管（FastAPI 托管前端产物）、会话 + CSRF、入站限流、安全响应头、只读模式、SQLite 热备份脚本 |

---

## 2. 技术栈与结构

- 后端：Python 3.11+ / FastAPI / SQLAlchemy 2.0 / SQLite（WAL）/ APScheduler / numpy + scikit-learn / cryptography
- 前端：React 18 + TypeScript + Vite + Tailwind v4 + ECharts
- 部署：单进程 8787 端口同时提供 API 与静态页面；可选 Nginx 反代 / Docker / systemd

```
caipiao-lab/
├── backend/
│   ├── app/
│   │   ├── main.py            应用入口、中间件、静态托管、SPA 兜底
│   │   ├── config.py          环境变量（pydantic-settings）
│   │   ├── db.py              引擎 / 会话 / WAL
│   │   ├── models.py          draws / draw_numbers / prize_grades / sync_runs / providers /
│   │   │                      tickets / predictions / users / user_sessions / audit_logs /
│   │   │                      ai_providers / ai_analyses / app_settings
│   │   ├── schemas.py         请求响应模型
│   │   ├── games.py           彩种规则（号码域、开奖日、期号规则）
│   │   ├── security.py        scrypt 口令、会话、Fernet 加密、审计、登录失败计数
│   │   ├── auth_deps.py       鉴权依赖（会话 Cookie / 静态令牌 / CSRF）
│   │   ├── ratelimit.py       入站限流 + 安全响应头中间件
│   │   ├── bootstrapping.py   老库补列、默认管理员
│   │   ├── routers/           draws / stats / analytics / predict / backtest / providers /
│   │   │                      sync / tickets / auth / admin / ai
│   │   ├── providers/         base 抽象 + cwl_official + c500 + csv_import + registry
│   │   ├── engine/            dataset / stats / models / generator / predictor / backtest / settle
│   │   ├── ai/                client（多厂商 OpenAI 兼容调用）+ prompt（提示词与降级解读）
│   │   ├── jobs/              sync_job（同步服务）+ scheduler（定时任务）
│   │   ├── scripts/sync.py    命令行同步入口
│   │   └── static/            前端构建产物（make build 生成）
│   └── tests/                 pytest 174 例（含防未来信息泄漏、鉴权、兑奖、注册、AI 离线用例）
├── web/                       Vite + React 前端源码
├── deploy/                    Dockerfile / docker-compose / nginx.conf / systemd unit / start.sh
├── scripts/backup.sh          SQLite 热备份 + 轮转
├── data/lottery.db            SQLite 数据库（WAL）
└── Makefile
```

---

## 3. 本地开发

```bash
make install     # 建后端 venv + 装前端依赖
make build       # 构建前端并复制到 backend/app/static
make api         # 启动后端 http://127.0.0.1:8787
make dev         # 前端热更新（5173，/api 反代到 8787）
make test        # 后端 pytest
make web-test    # 前端 vitest
make test-all    # 前后端一起跑
```

首次拉数据（两种任选）：

```bash
make sync        # 官方源全量（约 40 次请求，11k 期）
make backfill    # 500.com 深历史补录（只补缺期，不覆盖已有数据）
```

也可以直接跑命令行：

```bash
cd backend
.venv/bin/python -m app.scripts.sync --game ssq --mode incremental   # 增量
.venv/bin/python -m app.scripts.sync --game all --mode full          # 全量
.venv/bin/python -m app.scripts.sync --game ssq --mode backfill      # 深历史补录
```

首次启动会自动建管理员账号（取自 `ADMIN_USERNAME` / `ADMIN_PASSWORD`），登录入口 `/login`，后台 `/admin`。

---

## 4. 环境变量

复制 `deploy/.env.example` 为 `deploy/.env` 后按需修改：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_HOST` | 127.0.0.1 | 监听地址，容器内用 0.0.0.0 |
| `APP_PORT` | 8787 | 监听端口 |
| `DB_PATH` | ../data/lottery.db | SQLite 路径，容器内 /data/lottery.db |
| `ADMIN_USERNAME` | admin | 首次启动创建的管理员账号 |
| `ADMIN_PASSWORD` | （见 .env.example） | 首次启动创建的管理员密码，**上线前务必改掉** |
| `ADMIN_TOKEN` | 空 | 可选静态令牌，给脚本调用；留空表示只用账号密码 |
| `SECRET_KEY` | 空 | 会话与 API Key 加密密钥；留空自动生成 `data/data-secret.key` |
| `SESSION_TTL_HOURS` | 72 | 登录会话有效期 |
| `COOKIE_SECURE` | false | HTTPS 部署时设 true（Cookie Secure + HSTS） |
| `LOGIN_MAX_FAILS` | 5 | 同账号 + IP 连续失败几次后锁定 |
| `LOGIN_LOCK_MINUTES` | 15 | 锁定时长 |
| `MIN_PASSWORD_LENGTH` | 10 | 新密码最小长度 |
| `INBOUND_RATE_PER_MIN` | 240 | 入站全局限流（每 IP 每分钟） |
| `INBOUND_BURST` | 60 | 入站突发配额 |
| `HEAVY_RATE_PER_MIN` | 12 | 重接口（预测 / 回测 / AI / 同步）每 IP 每分钟上限 |
| `CORS_ORIGINS` | 空 | 额外允许的前端源，逗号分隔 |
| `ENABLE_DOCS` | true | 是否暴露 `/api/docs`；生产建议 false |
| `READ_ONLY` | false | true = 全站只读（禁同步 / 建票 / 改配置） |
| `SYNC_ENABLED` | true | 是否启用定时同步调度器 |
| `SYNC_TZ` | Asia/Shanghai | 调度时区 |
| `PROVIDER_PRIMARY` | cwl_official | 首选供应商 |
| `PROVIDER_FALLBACK` | c500 | 兜底供应商 |
| `RATE_LIMIT_PER_MIN` | 120 | 对上游数据源的出站请求速率（保持克制） |
| `REQUEST_TIMEOUT` | 20 | 单次请求超时（秒） |
| `PAGE_SIZE` | 300 | 单页抓取条数 |
| `HTTP_PROXY` | 空 | 服务器访问不到 cwl.gov.cn 时填代理 |
| `PREDICT_DEFAULT_COUNT` | 5 | 前端默认返回注数 |
| `PREDICT_MAX_COUNT` | 100 | 单次返回注数上限 |
| `AI_ENABLED` | true | 是否开放 AI 解读 |
| `AI_TIMEOUT` | 60 | 单次大模型调用超时（秒） |
| `AI_MAX_CALLS_PER_HOUR` | 30 | 每个调用方每小时的 AI 分析上限 |
| `AI_ALLOW_PUBLIC_SUBMIT` | true | 是否允许游客提交 AI 供应商 |
| `AI_ALLOW_PRIVATE_ENDPOINT` | false | 是否允许供应商 base_url 指向内网（默认禁防 SSRF；用本地 Ollama 时设 true） |

---

## 5. 账号与权限

| 能力 | 游客 / 普通用户 | 管理员 |
| --- | --- | --- |
| 查看历史、统计、走势 | ✅ 免登录 | ✅ |
| 注册 / 登录 / 改密 | ✅ 自助 | ✅ |
| 生成预测、回测、AI 解读 | ✅ 免登录（受限流约束） | ✅ |
| 票夹（增删查） | ✅ 游客按设备隔离；登录后跨设备同步 | ✅ 同样按身份隔离 |
| 提交 AI 供应商（Key） | ✅ 进待审队列，自己看不到明文 | ✅ |
| 触发同步 / 补录 / 兑奖 | ❌ | ✅ |
| 供应商启停 / 连通测试 | ❌ | ✅ |
| AI 供应商审核 / 账号管理 / 审计 / 会话吊销 | ❌ | ✅ |

- 登录：`/login`，成功后下发 **HttpOnly + SameSite=Lax** 会话 Cookie，前端拿不到 token。
- 写操作双保险：会话模式必须带 `X-CSRF: 1` 请求头，否则 403。
- 改密码 / 被停用会立刻吊销该账号全部会话。
- 所有管理动作（登录、同步、供应商变更、账号变更、AI 提交与审核）写入 `audit_logs`，后台「审计日志」可查。

---

## 6. 部署到服务器

### 6.1 裸机 + systemd（推荐）

```bash
# 通用 Linux，已装 python3.10+ / node18+ / nginx
sudo mkdir -p /opt && cd /opt
sudo git clone <你的仓库> caipiao-lab && cd caipiao-lab
chmod +x deploy/start.sh scripts/backup.sh
sudo ./deploy/start.sh            # 装依赖 + 构建前端 + 建库建管理员 + 初次同步 + 启动
```

配成系统服务：

```bash
sudo cp deploy/caipiao-lab.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now caipiao-lab
journalctl -u caipiao-lab -f
```

Nginx 反代（安全响应头由 FastAPI 统一下发，配置里不要再写 add_header）：

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/caipiao-lab.conf
sudo sed -i 's/cp.example.com/你的域名/' /etc/nginx/conf.d/caipiao-lab.conf
sudo nginx -t && sudo systemctl reload nginx
```

HTTPS 用 certbot（Ubuntu/Debian）：`sudo certbot --nginx -d 你的域名`；
老系统 certbot 因 pyOpenSSL 报 `X509_V_FLAG_CB_ISSUER_CHECK` 时改用 acme.sh（见下）。
之后把 `COOKIE_SECURE=true`（HSTS 会自动下发）。

### 6.1.1 阿里云 Alibaba Cloud Linux 3 实测记录（2026-10-21）

线上环境：2 核 / 1.9G / 40G 盘，nginx 由宝塔托管（vhost 在 `/www/server/panel/vhost/nginx/`），
系统 python3 只有 3.6.8，**nginx 反代到 127.0.0.1:8790**（8787 已被别的服务占用）。

踩过的 5 个坑，按顺序照抄能省两小时：

1. **不要靠 dnf 装 python**。`dnf install python3.11` 表面 EXIT=0，实际 rpm 事务没落地
   （`warning: Found bdb_ro Packages database ... using bdb_ro backend`），`python3.11 --version` 仍然 not found。
   用 uv 自带解释器：
   ```bash
   uv python install 3.11
   # /root 是 700，systemd 用 caipiao 用户跑会 Permission denied（status=203/EXEC）
   cp -a /root/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu /opt/python/cpython-3.11
   chmod -R a+rX /opt/python/cpython-3.11
   /opt/python/cpython-3.11/bin/python3.11 -m venv /opt/caipiao-lab/backend/.venv
   ```
2. **PyPI 必须走镜像**。直连 pypi.org 10s 超时、阿里云 pypi 也慢，用清华：
   `uv pip install --python backend/.venv/bin/python --index https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt`
3. **没有 www-data 用户**。`useradd --system --home-dir /opt/caipiao-lab --shell /sbin/nologin caipiao`，
   unit 里 `User=caipiao`；`chown -R caipiao:caipiao /opt/caipiao-lab`。
4. **不要用 certbot**。1.23 在 python3.6 上直接崩（`module 'lib' has no attribute 'X509_V_FLAG_CB_ISSUER_CHECK'`），用 acme.sh：
   ```bash
   ~/.acme.sh/acme.sh --issue -d 你的域名 --webroot /www/wwwroot/你的域名 --keylength ec-256 --server letsencrypt --force
   mkdir -p /etc/letsencrypt/live/你的域名     # 少这一步 install-cert 会 touch 失败
   ~/.acme.sh/acme.sh --install-cert -d 你的域名 --ecc \
     --key-file /etc/letsencrypt/live/你的域名/privkey.pem \
     --fullchain-file /etc/letsencrypt/live/你的域名/fullchain.pem \
     --reloadcmd "nginx -s reload"
   ```
   续期由 acme.sh 自带的 cron 完成（`--cron`），不用额外配。
5. **响应头不要写两遍**。nginx 里 `add_header` 和 FastAPI 的 `security_headers_middleware` 会叠加成重复头，
   nginx 配置里全部删掉，只让应用下发。
   验证：`curl -sI https://你的域名/api/health | grep -i x-content-type-options` 应只有一行。

数据迁移（把本机库搬到服务器）：

```bash
# 本机：WAL 检查点后导出干净快照
sqlite3 data/lottery.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM INTO '/tmp/lottery.sqlite';"
gzip -c /tmp/lottery.sqlite > /tmp/lottery.sqlite.gz
scp /tmp/lottery.sqlite.gz root@服务器:/tmp/
# 服务器
gunzip -c /tmp/lottery.sqlite.gz > /opt/caipiao-lab/data/lottery.db
chown caipiao:caipiao /opt/caipiao-lab/data/lottery.db
```

备份 cron（每日 04:10，保留 14 份）：

```bash
mkdir -p /opt/caipiao-lab/backup && chown caipiao:caipiao /opt/caipiao-lab/backup
crontab -e
# 10 4 * * * cd /opt/caipiao-lab && DB_PATH=/opt/caipiao-lab/data/lottery.db KEEP=14 bash scripts/backup.sh >> /var/log/caipiao-backup.log 2>&1
```

安全体检（本机 unit 实测 1.7 OK）：

```bash
systemd-analyze security caipiao-lab --no-pager | tail -2
```

### 6.2 Docker

```bash
cd deploy
cp .env.example .env      # 改 ADMIN_PASSWORD / SECRET_KEY
docker compose up -d --build
docker compose logs -f
```

容器只绑 `127.0.0.1:8787`，对外由宿主 Nginx 转发；数据卷 `deploy/data` 持久化 SQLite 与密钥文件。

### 6.3 更新

```bash
git pull
sudo ./deploy/start.sh --update     # 裸机：重建前端 + 重启 systemd
docker compose up -d --build        # Docker
```

---

## 7. 定时同步与备份

调度器默认在每期开奖后约 12 分钟拉取（时区 `SYNC_TZ`），开奖日按各彩种规则：

| 彩种 | 开奖日 | 时间 |
| --- | --- | --- |
| 双色球 | 周二 / 周四 / 周日 | 21:15 |
| 福彩3D | 每日 | 21:15 |
| 七乐彩 | 周一 / 周三 / 周五 | 21:15 |
| 快乐8 | 每日 | 21:30 |

备份（在线热备，不断服）：

```bash
./scripts/backup.sh              # 备份到 backup/，保留最近 14 份
KEEP=30 ./scripts/backup.sh      # 保留 30 份
```

加进 crontab 每天凌晨 3 点：

```cron
0 3 * * * cd /opt/caipiao-lab && KEEP=14 ./scripts/backup.sh >> /var/log/caipiao-backup.log 2>&1
```

---

## 8. 接口一览

```
GET    /api/health
GET    /api/games                      GET  /api/games/{code}
GET    /api/draws/{game}               分页列表（start_date/end_date/issue/page/page_size）
GET    /api/draws/{game}/latest/one    最新一期
GET    /api/draws/{game}/{issue}       单期详情（含奖级）
GET    /api/draws/{game}/export.csv    导出 CSV（UTF-8 BOM）
GET    /api/stats/...                  频率 / 遗漏 / 走势 / 形态 / 随机性
GET    /api/analytics/{game}/...       同上（前端图表用）
POST   /api/predict                    生成预测（game/count/engine/strategy/window/seed/pick）
GET    /api/predict/{game}/next        快速预测（count/engine/strategy/window）
GET    /api/predict/history/{game}     预测历史
POST   /api/backtest                   滚动回测（game/model/periods/window/k/stride）

POST   /api/auth/login                 POST /api/auth/register      POST /api/auth/logout
GET    /api/auth/me
POST   /api/auth/password              改密（吊销全部会话）
GET    /api/auth/sessions              DELETE /api/auth/sessions/{id}

GET    /api/admin/overview             运行状态与计数
GET    /api/admin/users                POST /api/admin/users        PATCH /api/admin/users/{id}
GET    /api/admin/audit                GET  /api/admin/audit/actions
GET    /api/admin/sessions             DELETE /api/admin/sessions/{id}

GET    /api/ai/vendors                 支持的厂商与默认 base_url/model
GET    /api/ai/providers               已启用的供应商
POST   /api/ai/providers/submit        用户提交自己的供应商（进待审）
GET    /api/ai/providers/all           管理员：全部供应商
PATCH  /api/ai/providers/{id}          管理员：通过 / 拒绝 / 改参数
DELETE /api/ai/providers/{id}
POST   /api/ai/providers/{id}/test     连通性测试
GET    /api/ai/insight/{game}          本彩种统计画像
POST   /api/ai/analyze                 提示模型 + 大模型解读
GET    /api/ai/analyses                历史分析记录

GET    /api/providers                  PATCH /api/providers/{code}   POST /api/providers/{code}/test
POST   /api/sync/all                   POST /api/sync/{game}?mode=incremental|full|backfill
GET    /api/sync/status                GET /api/sync/stream（SSE 进度）  GET /api/sync/missing/{game}
POST   /api/sync/settle/all            核对票夹兑奖
GET    /api/tickets                    POST /api/tickets   DELETE /api/tickets/{id}
POST   /api/tickets/claim               把本设备游客票迁移到登录账号
```

交互式文档：`http://127.0.0.1:8787/api/docs`（`ENABLE_DOCS=false` 时关闭）。

票夹接口需要客户端标识：登录用户自动按账号归属，游客由前端带 `X-Device-Id` 请求头。
脚本调用可用 `X-Admin-Token` 静态令牌替代登录态。

---

## 9. 预测是怎么实现的

整条链路是「历史 → 每球边际概率 → 按约束抽样成票 → 回测检验」。

### 9.1 数据与建模口径

- 每个彩种按**球**拆成独立序列（双色球红球 1–33、蓝球 1–16），存 `draw_numbers`。
- 对每颗球，用最近 `window` 期算「下一期它被抽中」的概率。
- 所有模型输出先归一化（`_normalize`），保证概率和为 1。

### 9.2 六个引擎

| 引擎 | 做法 | 作用 |
| --- | --- | --- |
| `uniform` | 全部等概率 | 对照组，任何模型打不过它就说明没有预测力 |
| `frequency` | 近窗出现次数，指数衰减加权（decay 0.985） | 追热 |
| `omission` | 当前遗漏期数的相对强度 | 补冷 |
| `markov` | 用上一期是否开出做一阶条件概率 | 短期相关 |
| `bayes` | Beta-Binomial 后验，alpha=20 平滑 | 抗小样本噪声 |
| `gbdt` | 特征矩阵（近 N 期是否开出、遗漏、频率、期序位置等）→ 梯度提升树 | 非线性组合 |

- `gbdt` 后端优先 LightGBM，缺 `libomp` 或未安装时自动退到 sklearn `HistGradientBoostingClassifier`，行为一致只是略慢。
- `ensemble` 按权重加权融合上述模型，默认引擎。

### 9.3 从概率到号码

1. `build_tickets` 按球依次无放回抽样（`probs` + 策略温度 `strategy`）。
2. `strategy` 调温度：`hot` 追热、`cold` 补冷、`balanced` 均衡、`mixed` 混合、`random` 随机。
3. 每注算出结构（奇偶、大小、和值、跨度、区间分布、连号），并按与历史分布的一致性打分。
4. 需要多少注就抽多少注（`count` 1–100），去重后返回；`seed` 可复现。

### 9.4 回测（关键）

`run_backtest` 从第 N 期往前滚：**每次只用该期之前的数据训练**，预测该期再核对命中，绝不使用未来信息。
输出模型平均命中、随机基线命中、提升倍数、TOP-K 命中率、logloss、Brier，并用 `_verdict` 给结论。
`stride` 控制每 N 期重训一次以加速（默认 5）。

### 9.5 兑奖规则

票夹与预测票在开奖后自动核对，奖金口径分两类：

| 彩种 | 规则 |
| --- | --- |
| 双色球 | 红球命中数 + 蓝球是否命中定奖级（一等~六等），浮动奖从该期官方 `prize_grades` 取实际金额 |
| 七乐彩 | 基本号命中 + 特别号定奖级，同样优先取官方金额 |
| 福彩3D | 直选 1040 / 组三 346 / 组六 173；组选奖金取决于**开奖号码形态**，豹子号组选不设奖 |
| 快乐8 | 按 `x{选几}z{中几}` 反查该期官方奖级，如 `x10z10` = 500 万；80 种组合零硬编码 |

官方奖级缺失时退回内置兜底表，不会算成 0。
单档「0 注 0 元」是真实情况（头奖空缺、选十中十无人中），页面显示为「空缺」。

清理整期奖级全为 0 的脏数据：

```bash
cd backend
.venv/bin/python -m app.scripts.clean_zero_prizes          # 先 dry-run 看数量
.venv/bin/python -m app.scripts.clean_zero_prizes --apply  # 确认后执行
```

### 9.6 必须知道的事实

彩票每期独立同分布，历史频率不改变下一期的真实概率。
模型的价值在于**证伪**：如果某个引擎在回测里打不过 `uniform` 基线，那它就只是噪声拟合。
页面上所有预测结果都带这句声明。

---

## 10. AI 供应商：可以接，也可以让用户自己填

### 10.1 现在的实现

`POST /api/ai/analyze` 做两件事：

1. 调本地统计引擎产出候选号码与画像（热号、冷号、遗漏前列、结构和值分布、卡方随机性检验、每球边际概率）。
2. 把这份**结构化数据**（`build_payload`，中文键 JSON）交给大模型，让它解释选号依据、点评结构、给 2–4 条建议。

大模型只做**解读**，不改号码、不改概率。没有可用供应商时自动回落到本地规则解读（`fallback_answer`），页面不会空着。

支持的厂商（`VENDORS`）：OpenAI / DeepSeek / Moonshot / 智谱 GLM / 通义 Qwen / Ollama 本地 / 自定义 OpenAI 兼容端点。

### 10.2 用户自己填供应商（已实现）

- 前台 `/ai` 页有「提交我的 AI 供应商」表单：名称、厂商、base_url、model、API Key、联系人、备注。
- Key 用 **Fernet 加密落库**（密钥来自 `SECRET_KEY` 或自动生成的 `data/data-secret.key`），接口只返回掩码（`sk-t******abcd`）。
- 提交进入 `pending` 待审队列（上限 200 条防刷），写审计日志 `ai_submit`。
- 管理员在 `/admin` → 「AI 供应商审核」里**通过 / 拒绝 / 测试连通 / 调温度与 max_tokens**，通过后才对前台可见可用。
- 每次调用累计 `calls`、`last_ok_at`、`last_error`，可随时停用。

### 10.3 要不要自己配

- **不配也能用**：统计引擎 + 本地规则解读，完全离线，零成本，零延迟。
- **配了更好读**：大模型能把「为什么这几个号」讲成人话，适合给用户看。
- 建议：先用便宜的 `deepseek-chat` 或本地 Ollama 试，确认话术符合预期再换更强的模型。

---

## 11. 安全设计

| 面 | 措施 |
| --- | --- |
| 口令 | scrypt（N=2^14, r=8, p=1）+ 每用户随机盐，格式 `scrypt$N$r$p$salt$hash` |
| 会话 | 32 字节随机 token，库里只存 SHA256；HttpOnly + SameSite=Lax Cookie；默认 72 小时过期 |
| CSRF | 会话模式的写操作必须带 `X-CSRF: 1`（自定义头，跨站表单无法伪造） |
| 爆破 | 同账号 + IP 连续失败 5 次锁定 15 分钟，失败与锁定都写审计 |
| 越权 | 管理员依赖 `require_admin`，读接口与管理接口分离；停用账号立即失效 |
| 隔离 | 票夹按 `owner_key`（`u:<id>` / `d:<device>`）过滤，删他人票返回 404 |
| 密钥 | AI Key 加密存储，接口只回掩码；`SECRET_KEY` 未配置时自动生成 600 权限文件 |
| 限流 | 全站入站限流 + 重接口（预测 / 回测 / AI / 同步）独立更严限流 |
| 头部 | `X-Content-Type-Options` / `X-Frame-Options: DENY` / `Referrer-Policy` / `Permissions-Policy` / CSP / HTTPS 下 HSTS |
| 暴露面 | `ENABLE_DOCS=false` 关文档；`READ_ONLY=true` 全站只读；Nginx `server_tokens off` |
| 审计 | `audit_logs` 记录登录、同步、供应商、账号、AI 提交与审核，含 IP 与 UA |

---

## 12. 数据源说明

| 源 | 代码 | 覆盖 | 用途 |
| --- | --- | --- | --- |
| 福彩官方 | `cwl_official` | 4 彩种，官方口径最新 | 首选，增量 / 全量 |
| 500.com 历史库 | `c500` | ssq 2003-02 起 / 3d 2004-10 起 / qlc 2007-01 起 | 深历史补录、交叉校验 |
| CSV 离线导入 | `csv_import` | 4 彩种 | 断网或官方改版时兜底 |

- 官方端点为 `www.cwl.gov.cn/.../findDrawNotice`，**必须带 `Referer: https://www.cwl.gov.cn/`**，否则 302 到 404 页；`name` 参数 3D 用 `3d`（`fc3d` / `fcsd` 都失败）。
- 官方源本身最早只到 2013-01，2003–2012 的期次来自 500.com 补录（补录模式只插缺期，绝不覆盖官方已有数据）。
- 服务器无法直连 `www.cwl.gov.cn` 时：填 `HTTP_PROXY`，或用同步页的 CSV 导入兜底。

---

## 13. 测试

```bash
cd backend && .venv/bin/python -m pytest -q     # 174 passed
cd web && pnpm test                              # 25 passed（Vitest）
```

全部离线（不联网、不启调度器、用临时 SQLite + 合成开奖数据），覆盖：彩种规则、开奖解析、分页与筛选、CSV 导出、统计指标、模型训练、预测注数、回测无未来信息泄漏、深历史补录只插缺期、供应商启停与鉴权、登录 / CSRF / 会话吊销 / 改密、管理后台用户与审计、AI 提交审核与降级（monkeypatch 大模型调用）。

---

## 14. 常见问题

**同步报 302 / 拿不到数据**：官方源要求 `Referer`，代码已内置；若服务器出口 IP 被限，配置 `HTTP_PROXY` 后重试。
**预测报错缺 libomp**：`gbdt` 会优先尝试 LightGBM，macOS 缺 libomp 时自动退到 sklearn，不影响使用；想用 LightGBM 就 `brew install libomp`。
**页面 404**：确认 `backend/app/static/index.html` 存在（`make build` 生成）；后端对非 `/api` 路径做 SPA 兜底。
**后台进不去**：确认 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 与库里账号一致；密码改了要重启服务并清空对应会话。
**忘记管理员密码**：停服后进 `backend` 执行
```bash
.venv/bin/python - <<'PY'
from app.db import session_scope
from app.models import User
from app.security import hash_password
with session_scope() as s:
    u = s.query(User).filter(User.role == "admin").first()
    u.password_hash = hash_password("新密码至少十位")
    print("已重置", u.username)
PY
```
**想彻底只读对外**：`READ_ONLY=true` + 只暴露 GET 接口给公网，写操作走内网或 VPN。
