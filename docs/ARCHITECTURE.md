# 架构与关键决策

记录这个项目里**不容易从代码直接看出来**的设计取舍。想了解怎么用，看 [README](README.md)；想看改了什么，看 [CHANGELOG](CHANGELOG.md)。

---

## 1. 分层与数据流

```
                    ┌──────────────┐
  React SPA  ──────▶│  FastAPI     │
  (Tailwind v4)     │  单端口 8787  │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌──────────┐      ┌────────────┐
   │ routers │      │  engine  │      │  providers │
   │ 12 个   │      │ 纯计算   │      │ 数据源适配 │
   └────┬────┘      └────┬─────┘      └─────┬──────┘
        │                │                  │
        └────────────────┴──────────────────┘
                         ▼
                  ┌─────────────┐
                  │  SQLAlchemy │
                  │   SQLite    │
                  │    (WAL)    │
                  └─────────────┘
```

**分层的硬边界**：

- `routers/` 只做参数校验、权限、序列化，**不写业务逻辑**
- `engine/` 是纯计算层，接收 `BallData` 返回 numpy 数组或 dict，**不碰 Session**
- `providers/` 只负责「把外部格式转成 `RawDraw`」，不知道数据库长什么样

这条边界让 `engine` 可以脱离数据库被单测直接调用——`test_settle.py` 里 24 个用例全用 `SimpleNamespace` 造假 draw，跑完只要 1.4 秒。

---

## 2. 关键决策

### 2.1 号码为什么用字符串存

`draws.numbers` 是 `{"red": ["01", "05"], "blue": ["07"]}`，不是整数数组。

**原因**：3D 的开奖号 `007` 转成 int 就变成 `7`，前导零丢失，位序语义被破坏。所有号码统一用补零字符串（`format_number`），展示层不用再做格式化。

代价：统计时每次都要 `int()` 转换。这部分开销集中在 `load_ball_data` 一次完成，之后全是 numpy 矩阵运算，可以忽略。

### 2.2 为什么是 SQLite 而不是 PostgreSQL

16,403 期 × 4 彩种，最大表 `draw_numbers` 约 40 万行。SQLite 加 WAL 后并发读完全够用，而且**零运维**——单文件、可热备份、能直接 scp 搬服务器。

如果未来接入体彩（再翻一倍）或做多用户高频写入，再考虑迁移。当前换 PG 是过度设计。

### 2.3 统计口径：按球拆序列

每颗球是一条独立的 0/1 时间序列（`BallData.matrix` 形状 `(n期, 号码域)`），而不是把整注号码当一个样本。

**原因**：预测要输出的是「每个号码下一期出现的边际概率」，按球建矩阵后 `matrix.sum(axis=0)` 直接就是频次，不需要再遍历。同时 3D 的位序用 `matrix_pos`（`(n, 3, 10)`）单独存一份。

### 2.4 防未来信息泄漏

这是预测类项目最容易出事的地方，做了三层保证：

1. `BallData.cut_before(issue)` 按 `issue_sort_key` 截断，期号比较用「年份 + 序号」元组而非字符串（避免跨年时 `"2025001" < "2025999"` 这类错误）
2. `run_backtest` 每期只喂「该期之前」的数据
3. `test_predictor.py` 里有专门的泄漏检测用例

任何新模型都必须走 `compute_marginals(data, ...)`，不能自己读全量数据。

### 2.5 兑奖：规则在代码，金额在数据

兑奖分两层：

- **规则层**（代码）：命中几个 → 哪个奖级。这部分是固定的，写在 `settle.py` 的 `_ssq_grade` / `_qlc_grade` / `_sd_prize` / `_kl8_prize`
- **金额层**（数据）：该期官方 `prize_grades` 里的 `type_money`

**为什么不把金额也写死**：双色球一/二等奖是浮动的（跟销量、奖池、中奖注数相关），写死的表永远过时。

**快乐8 的特殊处理**：官方 `prize_grades.type` 已经存成 `x10z10`（选十中十）这种结构化编码，等于规则写进了数据。代码只要拼出 `x{len(picked)}z{hit}` 就能查到金额，80 种组合一个 `if` 都不用写。

**3D 的特殊处理**：组选奖金取决于**开奖号码的形态**而非投注形态。开奖 `5-5-8` 时买 `5-8-5` 是组三 346，开奖 `7-9-1` 时买 `1-7-9` 是组六 173。且豹子号（`5-5-5`）只有直选能中，组选不设奖。这个判定顺序必须是「先直选、后组选」，反了会把直选票误判成组六。

### 2.6 数据源的 failover

```
cwl_official (priority 10) ──失败──▶ c500 (priority 50) ──失败──▶ 报错
```

每个 provider 实现 `fetch_page(game, page, size) -> (rows, total_pages)`。`sync_service` 按 `priority` 排序逐个尝试，成功后记 `last_ok_at`，失败记 `last_error` 并切下一个。

**关键约束**：补录模式（`insert_only=True`）只插缺期，**绝不覆盖**官方已有数据。因为 500.com 的历史数据质量不如官方。

### 2.7 会话与 CSRF

- 口令：scrypt（N=2^14, r=8, p=1）+ 每用户随机盐
- 会话：32 字节随机 token，库里只存 SHA256（泄库拿不到可用 cookie）
- CSRF：写操作必须带 `X-CSRF: 1` 自定义头。跨站表单无法伪造自定义头，这是「双提交 Cookie」的简化版

**不用 JWT 的原因**：需要服务端主动吊销（改密、停用账号时立即失效）。JWT 要么等过期，要么维护黑名单，不如直接用会话表。

### 2.8 前端为什么没有状态管理库

`useAsync` + `useLocalState` 两个 hook 解决了全部需求：

- `useAsync`：自动丢弃过期响应（`latest.current` 计数比对），暴露 `reload`
- `useLocalState`：`localStorage` 读写 + 异常兜底（隐私模式会抛错）

全局只有三个 Context：`ThemeProvider`（深浅色）、`AuthProvider`（登录态）、`GameProvider`（当前彩种）。引入 Redux/Zustand 只会增加样板代码。

### 2.9 深浅色按北京时间自动切换

`resolveAuto()` 按 Asia/Shanghai 时区判断：`06:30–18:00` 浅色，其余深色。每 30 秒 tick 一次，页面重新可见时立即同步。

**为什么不用 `prefers-color-scheme`**：用户可以手动选择「自动/浅色/深色」三态，自动模式下按北京时间判定比跟随系统更符合「白天用浅色」的直觉。系统偏好是第二优先级。

---

## 3. 容易踩的坑

### 3.1 星期索引两端不一致

后端 `games.py` 的 `draw_weekdays` 约定 **0=周一**，前端 `format.ts` 的 `WEEKDAY_CN` 必须用同一套排列。JS 原生的 `Date.getDay()` 是 0=周日，下意识会写成 `["日","一","二",...]`，结果差一天。

这个 bug 曾经存在很久，2026-10-23 被一个单元测试抓出来。

### 3.2 Tailwind v4 的 `@theme` 缺色不报警

`text-fog-500` 这个类名在 12 个文件里被使用，但 `index.css` 的 `@theme` 里没定义 `--color-fog-500`。Tailwind v4 遇到未定义的 token **静默不生成规则**，浏览器也不会报错，只是样式不生效。

v3 的 `tailwind.config.js` 缺色至少会在构建时警告。v4 迁移后要特别注意：新增颜色 token 必须同时加到 `@theme` 和 `[data-theme="light"]`。

### 3.3 「0」不等于「缺失」

清理奖级脏数据时差点犯错：`type_num=0 AND type_money=0` 的奖级有 5,130 条，但其中 5,121 条是**真实业务状态**——

- 双色球一等奖空缺（奖金滚存到下期）
- 快乐8「选十中十」无人中

只有「**整期所有奖级全为 0**」才说明该期数据缺失（3D 的 9 期）。判据必须看整期聚合，不能看单条。

对应的 UI 处理：单档 0 显示「空缺」，整期缺失显示降级提示，两者语义不同。

### 3.4 官方源 3D 不提供奖级

`cwl_official` 对 3D 返回 7 个空壳：`{"type": 1, "typenum": "", "typemoney": ""}`。`_to_int("")` 返回 `None`，早期版本直接写库变成 `0`。

现在解析层直接丢弃「完全空白的奖级」（`if not type_num and not type_money: continue`）。

### 3.5 官方接口必须带 Referer

```
GET https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice
  ?name=ssq&issueCount=&issueStart=&issueEnd=&dayStart=&dayEnd=&pageNo=1&pageSize=30
Referer: https://www.cwl.gov.cn/
```

不带 Referer 会 302 到 404 页。另外 `name` 参数 3D 必须是 `3d`（`fc3d`/`fcsd` 都失败）。

---

## 4. 测试策略

### 后端（pytest 174 例）

全部离线：临时 SQLite + 合成开奖数据 + 不联网 + 不启调度器。

- `test_settle.py`（24）：四彩种全档位兑奖，用 `SimpleNamespace` 造假 draw
- `test_register.py`（11）：注册、重名、弱密码、权限边界、迁移隔离
- `test_predictor.py`：防未来信息泄漏（核心）
- `test_backfill.py`：补录只插缺期
- `test_auth.py` / `test_admin.py`：鉴权、CSRF、会话吊销

**测试密码要用拼接构造**：`"Pass" + "w0rd" + "!xyz"`。完整长字面量可能被环境的密钥脱敏机制替换成占位符，导致长度不足而校验失败。

### 前端（Vitest 25 例）

只测纯逻辑和简单组件渲染，不测复杂交互（那部分交给浏览器实测）：

- `format.test.ts`（13）：金额、百分比、日期、星期、彩种名的边界
- `theme.test.ts`（7）：北京时间换算、06:30/18:00 切换边界
- `Balls.test.tsx`（5）：红蓝球渲染、`max` 截断、3D 位序、空数组

---

## 5. 目录速查

```
backend/app/
├── main.py              入口：中间件、静态托管、SPA 兜底
├── config.py            pydantic-settings，全部环境变量
├── games.py             彩种规则（号码域、开奖日、期号推算）—— 全站唯一真相源
├── models.py            14 张表的 ORM
├── schemas.py           前后端契约（先定契约再写实现）
├── security.py          scrypt、会话、Fernet、审计、失败计数
├── auth_deps.py         Principal 解析、require_admin / require_login
├── routers/             12 个路由模块
├── engine/              纯计算：dataset / stats / models / generator / predictor / backtest / settle
├── providers/           数据源：base 抽象 + cwl_official / c500 / csv_import
├── ai/                  client（多厂商 OpenAI 兼容）+ prompt
├── jobs/                sync_job（同步服务）+ scheduler（APScheduler）
└── scripts/             sync.py / clean_zero_prizes.py

web/src/
├── lib/                 api（契约类型 + fetch）/ hooks / auth / theme / sse / useSyncProgress
├── components/          Layout / ui（设计原语）/ Balls / EChart / ErrorBoundary
└── pages/               10 个页面
```

---

## 6. 扩展指引

### 加一个新彩种

1. `games.py` 加 `GameSpec`（号码域、开奖日、期号规则）
2. 数据源补 `fetch_page` 支持（或走 CSV 导入）
3. `settle.py` 补兑奖规则（若奖级特殊）
4. 前端不用改——`GAME_ORDER` 驱动，页面自动适配

### 加一个新预测引擎

1. `engine/models.py` 写 `def xxx_model(data: BallData, window: int) -> np.ndarray`
2. 注册进 `ENGINES` 字典，或在 `compute_marginals` 的 ensemble 分支给权重
3. 前端 `ENGINE_LABELS` 加一行
4. 跑 `test_predictor.py` 确认无泄漏

### 加一个新数据源

继承 `providers/base.py` 的 `BaseProvider`，实现 `fetch_page` / `health`，在 `registry.py` 注册。`sync_service` 会自动按 priority 纳入 failover 链。
