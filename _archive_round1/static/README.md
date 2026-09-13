# 极境 ZenithLens · 前端产品壳（OpenCode 独立实现）

纯静态、零第三方依赖、无构建步骤。对接 `09-api-contract.md` v3。

## 启动

```bash
# 本地静态托管（Python 3.8+，无需第三方库）
cd static
python -m http.server 8787 --bind 127.0.0.1
# 浏览器打开 http://127.0.0.1:8787/index.html
```

> 必须经 `http://127.0.0.1` 访问；ES module 在 `file://` 下会被浏览器拦截（不要双击 HTML）。
> 正式运行由后端 `server/` 同源托管 `static/`，接口前缀 `/api/v1/`。

## 演示模式（mock，默认关闭）

- 开启：URL 加 `?mock=1`，或 `localStorage.setItem('zl_mock','1')` 后刷新。
- 关闭：去掉 `?mock`，或 `localStorage.removeItem('zl_mock')`。
- 假数据仅位于 `js/mock/`，生产路径不加载；后端就绪后无需改视图层。

## 接口运用规范（硬约束）

1. 所有请求经 `js/api.js`（唯一 fetch 出口）；页面层禁止直接 `fetch`。
2. 加载/空/错误/成功四态由 `js/components.js#mountState` 统一渲染，不散落各页。
3. 失败一律可重试，错误文案按 `error.code` 映射（`js/copy.js`），未知 code 不吞 `error.message`。
4. 数字格式化唯一入口 `js/format.js`（金额/概率/比率/Δpp/lift/z/日期）；组件不得自行拼百分比。
5. 前端**不做业务计算**（组合加权、命中率、评分、Δ 等一律取后端）；仅做展示连接与格式化。
6. 未知口径：`null` 渲染「未知/—」，禁止 `+0.00%`；未知行金额走独立 `fallback_value`，不混入市值。
7. 估值徽章文案/配色由后端 `valuation_mode→mode_label`、`confidence→confidence_color_class` 驱动。
8. 隐私打码只作用于展示（`body.masked .amt`），不改变 store 数值、不影响计算/导出。

## 目录

```
static/
  index.html          单页外壳（7 视图 + 3 dialog + popover + toast）
  css/app.css         设计 token + 布局 + 组件样式
  js/
    api.js            ★ 唯一 fetch 出口（超时/信封/ApiError/mock 注入）
    store.js          单一 store + 订阅，切片自带四态
    format.js         ★ 数字唯一格式化出口
    copy.js           四态/错误码/枚举文案
    components.js     四态容器 + 命脉组件 + 通用件
    main.js           入口（路由/顶栏/livebar/SW 注销/隐私/四态演示）
    views/            7 个视图
    mock/             mock 后端替身（默认关闭）
```

字段口径以 `docs/01-architecture/09-api-contract.md` v3 为唯一法律；契约缺口见
`docs/02-frontend/12-interface-request.md` §3。
