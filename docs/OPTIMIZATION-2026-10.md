# 2026-10 优化记录：从「能跑」到「可信」

> 这一轮改动的核心不是加功能，而是**修复文档与实现之间的落差**，以及**一个一直算错的核心业务逻辑**。

---

## 一、为什么要做这轮

项目本身代码质量不差：6024 行后端、4615 行前端、133 个离线测试全绿、部署踩坑记录详细。

但把代码完整读一遍后发现三类问题：

| 类型 | 数量 | 举例 |
| --- | --- | --- |
| README 承诺但没实现 | 3 | 期号搜索、SSE 同步进度、蓝球统计 |
| 计算错误 | 3 | 快乐8 奖金恒 0、3D 组选恒 0、星期索引错位 |
| 数据/样式缺陷 | 3 | 3D 空奖级脏数据、`fog-500` token 缺失、首页写死文案 |

**为什么这些能活这么久**：兑奖逻辑（`settle.py`）和前端纯函数（`format.ts`）此前**零测试覆盖**。没有测试的地方，bug 不会自己暴露。

---

## 二、逐项修复

### 2.1 快乐8 兑奖永远 0 元（最严重）

```python
# 修复前 —— backend/app/engine/settle.py
table = {
    "ssq": {...},
    "qlc": {...},
    "3d": {(3, 0): 1040.0},
    "kl8": {},          # ← 空字典，永远查不到
}
```

快乐8 有 80 种玩法组合（选一到选十 × 中零到中十），写死表要维护 80 行。而官方数据的 `prize_grades.type` 已经存成了 `x10z10`（选十中十）这种结构化编码——**规则就在数据里**。

```python
# 修复后
def _kl8_prize(picked, draw_red, draw):
    pick = len(picked)          # 选几由票的号码数决定
    hit = len(picked & draw_red)  # 中几由开奖号决定
    code = f"x{pick}z{hit}"     # 拼出官方编码
    money = _grade_money(draw, code)   # 直接查该期官方奖级
```

实测：造一张选十中十的票，兑奖结果 `5,000,000 元`。

### 2.2 3D 组选中奖算 0

原表只有 `(3, 0): 1040.0`（直选 3 个全中）。买组选的人即使中了，奖金也是 0。

新规则的关键在于**判定顺序**和**形态归属**：

```python
def _sd_prize(ticket_ordered, draw_ordered):
    if ticket_ordered == draw_ordered:
        return 1040.0, "direct"        # 先判直选
    if sorted(ticket_ordered) != sorted(draw_ordered):
        return 0.0, "none"
    counts = Counter(draw_ordered)     # 组选奖金看【开奖号形态】
    if len(counts) == 3:
        return 173.0, "group6"         # 三位互不相同
    if len(counts) == 2:
        return 346.0, "group3"         # 有且仅有一对
    return 0.0, "none"                 # 豹子号组选不设奖
```

**易错点**：组选奖金取决于开奖号码形态，不是投注形态。开奖 `7-9-1` 时买 `1-7-9` 是组六 173；开奖 `5-5-8` 时买 `5-8-5` 是组三 346。判定顺序反了会把直选票误判成组六（少给 867 元）。

### 2.3 星期显示错一天

| | 定义 |
| --- | --- |
| 后端 `games.py` | `draw_weekdays=(1,3,6)` 注释写 `0=周一`，即周二/四/日 |
| 前端 `format.ts` | `WEEKDAY_CN = ["日","一","二","三","四","五","六"]`（JS `getDay()` 习惯） |

两边各自「看起来对」，拼起来错一位。双色球页面一直显示「周一/三/六」。

**这个 bug 是写前端测试时当场抓出来的**——`weekdayLabel([1,3,6])` 期望「周二、周四、周日」，实际返回「周一、周三、周六」。

### 2.4 分析页期望值硬编码

```tsx
// 修复前
"理论期望 " + (total_draws * 6 / 33).toFixed(2) + " 次/号"
```

只有双色球成立。其他彩种全错：

| 彩种 | 正确口径 | 旧代码算成 |
| --- | --- | --- |
| 福彩3D | 3/10 | 6/33（偏小 39%） |
| 七乐彩 | 7/30 | 6/33 |
| 快乐8 | 20/80 | 6/33 |

修复方式：后端 `FrequencyOut` 补 `per_draw_count` 与 `domain_size` 两个字段，前端据此计算，不再猜。

### 2.5 期号搜索不存在

README 功能表写着「分页列表（可切彩种/日期区间/**期号搜索**）」，但 `draws.py` 的 `list_draws` 只有 `start_date` / `end_date`。

补上 `?issue=` 参数，用 `LIKE %needle%` 匹配。这样输 `121` 能同时命中 `2026121`、`2025121`，输 `2026` 能查整年。

### 2.6 SSE 同步进度前端零使用

后端 `/api/sync/stream` 实现完整（含 keep-alive、订阅队列、事件发布），但前端 `grep EventSource` 零命中。用户点「增量同步」后只有一个静止的 Spinner，长同步时以为卡死。

新增 `lib/sse.ts` + `lib/useSyncProgress.ts`：

- 按彩种覆盖状态（不是追加数组），4 彩种恒定 4 条，与同步页数无关
- 只有正在同步时才 `import()` 该模块，构建成独立 chunk（0.43 KB）
- `sync_done` 触发 `status.reload()`，期数统计自动刷新

### 2.7 分析页看不了蓝球

`api.frequency(game, window)` 没传 `ball` 参数，虽然后端 `analytics.py` 第 24 行支持 `ball=blue`。

补上红/蓝球切换（仅双色球、七乐彩显示）。蓝球是 16 个号码域、每期 1 个，与红球统计口径完全不同。

### 2.8 3D 空奖级脏数据

官方源对 3D 返回：

```json
"prizegrades": [
  {"type": 1, "typenum": "", "typemoney": ""},
  ... 共 7 个
]
```

`_to_int("")` 返回 `None`，写库后变 `0`。期次详情页显示一排「0 注 / —」，看起来像 bug。

两层修复：

1. **解析层**：`if not type_num and not type_money: continue`，空奖级不入库
2. **清理脚本**：`clean_zero_prizes.py` 删除历史脏数据

**清理时的关键判断**（差点犯错）：

初次判据是「`type_num=0 AND type_money=0`」，dry-run 显示 5,130 条。但抽样一看，其中 5,121 条是真实数据：

- 双色球 18 条：一等奖空缺（奖金滚存）
- 快乐8 1,335 条：`x10z10` 无人中
- 七乐彩 640 条：同上

改成「**整期所有奖级全为 0**」后只剩 9 期（3D），删除 27 条记录。UI 上也区分处理：单档 0 显示「空缺」，整期缺失显示降级提示。

### 2.9 `--color-fog-500` 未定义

12 个文件用了 `text-fog-500`，但 `index.css` 的 `@theme` 里只有 `fog-100/200/300/400`。

**Tailwind v4 对未定义的 token 静默不生成规则**——构建产物里 `grep text-fog-500` 返回 0 匹配，但浏览器也不报错，只是这 12 处文字颜色回退成继承值。

补上 token 后实测 `getComputedStyle` 返回 `rgb(89, 101, 122)`。

### 2.10 首页统计卡写死

```tsx
<div className="text-2xl font-semibold text-jade">官方</div>
<div className="text-2xl font-semibold">开奖后 12 分钟</div>
```

改成实时数据：最近同步状态、下次调度时间，都从 `api.syncStatus()` 读。

---

## 三、新增：普通用户账号

### 问题

票夹靠 `X-Device-Id` 隔离（`localStorage` 里的随机串）。换设备、清缓存、换浏览器——票全丢。

### 方案

复用现有 `users` 表，靠 `role` 区分：

- `admin` / `owner`：进后台
- `user`：只用前台功能

**关键改动是 `/api/auth/me`**：

```python
# 修复前
if not who.is_admin:
    return MeOut(authenticated=False)   # 普通用户被当成游客

# 修复后
if who.kind == "anonymous":
    return MeOut(authenticated=False)
```

这行代码的隐含假设是「只有管理员需要身份」。不改它，普通用户登录后前端 `isAuthed` 永远是 false，账号菜单永远不出现。

### 迁移流程

```
游客建票（d:xxx）→ 注册/登录 → 自动 POST /api/tickets/claim → 票归属改成 u:123
```

注册后**自动**迁移（`auth.tsx` 的 `register()` 里调 `claimTickets()`），用户不需要知道有这回事。

`claim` 只迁移本设备的票，不动别人的——`test_claim_only_moves_own_device` 用两个独立 TestClient 验证。

---

## 四、工程化

### git

项目此前**不是 git 仓库**（`git status` 报 `not a git repository`）。建立仓库后补全 `.gitignore`：

```
data/*.db          # 数据库
data/*.data-secret.key  # 会话密钥
backup/            # 备份
web/dist/          # 构建产物
.venv/ node_modules/
```

**推公开仓库前发现并处理了凭据泄露**：

- 默认管理员账号 `t479842598` = GitHub 用户名
- 默认密码明文写在 `config.py` / `main.py` / `.env.example`

改法：默认用户名改 `admin`，密码留空时**自动生成 20 位随机密码并打印到日志**（只在首次创建时显示一次）。代码里不存在任何可用默认口令。

因为 git 历史里也有这两项，用 `git filter-branch` 重写全部 7 个提交，`git gc --prune=now` 清理，复查 `git log --all -p | grep t479842598` 返回 0。

### 前端测试

`npm install` 在受限环境下会因 `~/.cache` 写入被拦，改用 `pnpm add -D`。最终选定 Vitest + Testing Library：

```bash
cd web && pnpm test     # 或 ./node_modules/.bin/vitest run
```

25 个断言，只测纯逻辑和简单渲染。**第一天就抓到了星期索引 bug**。

---

## 五、验证方式

### 自动化

```bash
cd backend && .venv/bin/python -m pytest -q    # 174 passed
cd web && pnpm test                            # 25 passed
cd web && ./node_modules/.bin/tsc -b           # 无输出 = 类型通过
```

### 端到端（实测记录）

| 项 | 验证方式 | 结果 |
| --- | --- | --- |
| 期号搜索 | `GET /api/draws/ssq?issue=121` | 77 条匹配，首条 2026121 |
| 彩种期望值 | `GET /api/analytics/{g}/frequency` | 3D 3/10→2336，七乐彩 7/30→700，快乐8 20/80→526 |
| 蓝球统计 | `?ball=blue` | 16 个号码域，每期 1 个 |
| SSE | `curl -N /api/sync/stream` | `data: {"type": "hello"}` |
| 快乐8 兑奖 | 造选十中十票 → settle | **5,000,000 元** |
| 3D 兑奖 | 直选/组六 | 1040 / 173 |
| 星期显示 | 浏览器读 header | 「周二、周四、周日」 |
| 账号同步 | 清 localStorage → 换设备号 → 重登 | 票还在 |
| fog-500 | `getComputedStyle` | `rgb(89, 101, 122)` |

### 未执行

- 生产服务器部署验证（本轮只在本机跑）
- Docker / systemd 启动验证

---

## 六、遗留事项

| 项 | 说明 |
| --- | --- |
| 清理脚本 | 已执行，删除 9 期 27 条 3D 脏奖级，备份在 `backup/lottery-before-clean3d-*.db` |
| 体彩接入 | 大乐透/排列三需要新数据源，未做 |
| 3D 奖级覆盖 | 7788 期中 3080 期有奖级，其余官方不提供 |
| 复式/胆拖 | `generator.py` 只支持单式，复式是彩民主流购彩方式 |

---

## 七、复盘：三条可复用的经验

**1. 文档承诺要能用命令验证**

README 写「期号搜索」但接口没有——这类落差不会自己暴露。以后加功能，README 的接口清单应该从 OpenAPI 生成，或者至少在 CI 里跑一遍示例请求。

**2. 「0」和「缺失」是两回事**

清理脏数据时，如果只看计数（5,130 条）就执行，会删掉 5,121 条真实业务数据。**dry-run 必须抽样看内容**，不能只看数量。

**3. 测试的价值在于暴露契约，不在覆盖率**

25 个前端断言覆盖不到 10% 的代码，但第一天就抓到星期索引 bug——因为那个测试比较的是**两端的约定**，而不是「跑通即过」。
