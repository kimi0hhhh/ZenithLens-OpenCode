// 四态文案与错误码文案（07 §4；09 §3）
// R2 升级：本文是**文案字典实现层**（03-ui-design-v3 §7 / U-12）——新增文案必须先入字典再进组件；
// 组件不得硬编码枚举中文（conf_reason 五值 / verify_status 五值 / shadow_status 四值等）。
export const ERROR_COPY = {
  E_IO: '读写本地数据失败',
  E_PARSE: '数据格式错误',
  E_SOURCE_TIMEOUT: '数据源暂时不可用',
  E_ENGINE_OFFLINE: '引擎未运行',
  E_VALIDATION: '参数不合法',
  E_NOT_FOUND: '未找到',
  E_CONFLICT: '已存在',
  E_TIMEOUT: '请求超时',
  E_NETWORK: '无法连接本地服务',
  E_UNKNOWN: '发生未知错误'
};

export function errorText(error) {
  if (!error) return '发生未知错误';
  const prefix = ERROR_COPY[error.code] || '发生未知错误';
  if (error.code === 'E_UNKNOWN' && error.message) return prefix + '：' + error.message;
  if (error.code === 'E_NETWORK') return prefix + '（请经 http://127.0.0.1 访问）';
  return prefix;
}

export function errorDetail(error) {
  if (!error) return '';
  return error.message || '';
}

// 各视图四态文案（空/加载/错误）——R2 空态必须含「为什么空 + 下一步」（03-ui-design-v3 §4）
// empty.action：空态主行动按钮文案（有值才渲染按钮）
export const STATE_COPY = {
  holdings: {
    empty: {
      big: '还没有录入任何持仓',
      sub: '为什么空：持仓列表为 0 条。数据源：data/holdings.json（产品自持主源）。下一步：录入第一只基金，这里会显示组合总览与实时估值。',
      action: '录入第一只基金'
    },
    loading: { big: '正在读取持仓与估值…', sub: '首次加载会同时拉取行情与官方净值' },
    error: { big: '读取持仓失败', sub: '无法读取持仓数据：文件不存在或格式错误。已保留上次缓存数据，不回落示例数据。' }
  },
  analyze: {
    empty: {
      big: '今日没有触发开口的资产',
      sub: '为什么空：今日没有可展示的预测记录（/predictions 行为 0）。下一步：满足触发门（E1/E3）并穿过双否决的资产才会进入预测 —— 低频是常态，多数交易日不开口。'
    },
    empty_no_monitor: {
      big: '今日没有触发开口的资产',
      sub: '为什么空：当前没有纳入监控（A/B 档）的资产。下一步：先在「持仓」页录入基金并纳入监控，之后这里会显示三窗口预测与参与预测的持仓。'
    },
    empty_no_prediction: {
      big: '今日没有触发开口的资产',
      sub: '为什么空：今日没有可展示的预测记录（/predictions 行为 0）。下一步：满足触发门（E1/E3）并穿过双否决的资产才会进入预测 —— 低频是常态，多数交易日不开口。'
    },
    loading: { big: '正在计算三窗口预测…', sub: '按开口仓位市值加权，并计算覆盖市值占比' },
    error: { big: '预测服务暂不可用', sub: '引擎未响应或数据缺失。历史成绩仍可查看（标注时间）。' }
  },
  signals: {
    empty: {
      big: '今日无信号',
      sub: '为什么空：窗口内监控资产均未触发开门条件。这是常态，不是故障 —— 低频期望见下方说明。'
    },
    empty_never: {
      big: '影子盘尚未开始记录',
      sub: '为什么空：信号台账为空（从未记录）。下一步：先运行台账维护任务产生当日记录；之后本页显示逐笔信号与时间线。'
    },
    loading: { big: '正在读取信号台账…', sub: '按日期倒序加载近 60 天记录' },
    error: { big: '读取信号台账失败', sub: '台账文件不可读或损坏。' }
  },
  factors: {
    empty: {
      big: '因子库为空，等待首次扫描',
      sub: '为什么空：四盘均无因子记录。下一步：引擎每周扫描并提名 ≤3 个候选，冷却 90 天防多重检验。'
    },
    loading: { big: '正在读取因子账本…', sub: '加载四盘与账本记录' },
    error: { big: '因子账本读取失败', sub: '至少一个账本文件缺失或格式错误。' }
  },
  review: {
    empty: {
      big: '尚无成绩记录，引擎未产出回测',
      sub: '为什么空：无成绩缓存或全窗口未接通。纪律：「待填充」≠ 0，此处留空而非填估计值。'
    },
    loading: { big: '正在汇总历史成绩…', sub: '计算命中率、基线与 Δ（走前 CV）' },
    error: { big: '读取成绩失败', sub: '成绩文件不可读。' }
  },
  engine: {
    empty: {
      big: '引擎离线',
      sub: '为什么空：未检测到本地引擎心跳。下一步：启动 python app.py 后本页显示只读观测面板。'
    },
    loading: { big: '正在连接本地引擎…', sub: '等待心跳与台账状态' },
    error: { big: '引擎无响应', sub: '心跳超时。可查看已缓存的只读数据。' }
  },
  settings: {
    empty: {
      big: '尚未检测数据源',
      sub: '为什么空：四源均无检测记录。下一步：点击「立即检测」逐一探测连通性与响应时间。',
      action: '立即检测'
    },
    loading: { big: '正在检测数据源…', sub: '逐一探测连通性与响应时间' },
    error: { big: '配置读写失败', sub: '本地配置不可写。已填内容不会丢失。' }
  }
};

// 组合窗口未表态原因（09 §5.7 direction_reason）
export const DIRECTION_REASON = {
  ok: '',
  no_open: '今日无开口',
  insufficient_coverage: '覆盖不足，不构成组合结论',
  window_unvalidated: '该窗口未验证，仅观察'
};

// 覆盖度失效类型（09 §1.3 coverage_invalidation）
export const INVALIDATION_LABEL = {
  definition_failure: '定义失效',
  data_failure: '数据失效',
  framework_failure: '框架失效'
};

// ==================== R2 枚举字典（09 v9.1；组件不得硬编码） ====================

// 估值置信度中文（09 §5.2 confidence_label）
export const CONF_LABEL = { high: '误差达标', mid: '误差中等', low: '误差偏大', unknown: '无可信估算' };
// 置信度描边 class（第二层：准不准；沿用 R1 confidence_color_class）
export const CONF_CLASS = { high: 'ch', mid: 'cm', low: 'cl', unknown: 'cu' };

// 来源档底色（第一层：是什么）——07-frontend-arch-r2 §2.1：official/intraday=绿系、holdings=金、proxy=灰、unknown=虚线灰
export const SOURCE_LAYER = { official: 'l1', intraday: 'l1', holdings: 'l2', proxy: 'l3', unknown: 'l0' };

// conf_reason 五值（09 v9.1 §2.1/R-4；仅 confidence=unknown 时非 null）
export const CONF_REASON = {
  no_samples: '样本不足',
  nav_missing: '缺净值',
  valuation_missing: '缺估值',
  mode_unknown: '无估值来源',
  budget_exceeded: '估值预算用尽'
};
export function confReasonText(code) {
  if (!code) return '';
  return CONF_REASON[code] || String(code);
}

// verify_status 五值（09 v9.1 §2.1/R-3；中文标签以后端 verify_status_label 优先）
export const VERIFY_STATUS = {
  pending_validation: { label: '待验证', kind: 'gray' },
  validating: { label: '验证中', kind: 'warn' },
  validated: { label: '已验证', kind: 'ok' },
  validation_failed: { label: '验证未通过', kind: 'red' },
  not_applicable: { label: '暴露待定', kind: 'gray' }
};
export function verifyStatusText(code, backendLabel) {
  if (backendLabel) return backendLabel;
  const m = VERIFY_STATUS[code];
  return m ? m.label : (code ? String(code) : '待验证');
}
export function verifyStatusKind(code) {
  const m = VERIFY_STATUS[code];
  return m ? m.kind : 'gray';
}

// accuracy_window_phase 三值（09 v9.1 §2.1/D-2）
export const WINDOW_PHASE = {
  warming: '累计中（未满 5 个可配对日）',
  first_verdict: '首判就绪',
  mature: '终判就绪'
};

// shadow_status 四值（进度，09 §4.1/B1）+ shadow_audit_status 三值（偏差审查）
export const SHADOW_STATUS = {
  not_started: ['未启动', 'gray'],
  recording: ['记录中', 'warn'],
  // v9.5（滚动窗口由 20 扩至 60 + 启动回填）：qualified 立即可达；只陈述窗口完整度，不宣称上线资格（PM 补记）
  qualified: ['60 日回算覆盖达成', 'ok'],
  gap: ['有缺口', 'red']
};
export const SHADOW_AUDIT = {
  idle: ['未评估', 'gray'],
  ok: ['达标', 'ok'],
  bad: ['降级', 'red']
};

// qdii_fallback_reason 三值（09 §2.1；仅 tooltip 兜底，长文以后端 note 为准）
export const QDII_FALLBACK_REASON = {
  overseas_unavailable: '隔夜源不可得',
  alignment_conflict: '时间对齐校验失败',
  first_test_failed: '40 日窗首测不达标，回退单段'
};

// 固定口径词条（09 v9.1 §9.1；新增文案先入字典）
export const OFFICIAL_FACT_NOTE = '官方档为既成事实（非估计），不参与估算档主指标';
// v9.5（滚动窗口由 20 扩至 60 + 启动回填 · 10-arch-review-r2 §13 / 19-pm-acceptance-r2 补记）：
// 统一口径标注 / 达成文案（不得暗示上线资格）/ 偏差审查与前向·实盘语义分离
export const SHADOW_WINDOW_NOTE = '滚动 60 日 · 回算口径（启动回填）';
export const SHADOW_QUALIFIED_TEXT = '60 日回算覆盖达成（启动回填口径）';
export const SHADOW_AUDIT_NOTE = '回算口径（启动回填）· 与前向/实盘语义分离';
export const ARCHIVE_FALLBACK_NOTE = '按主文件计算（归档不可读）';
export const BACKFILL_METHOD_FALLBACK = '命中判定 = 代理 ETF 日线涨跌方向';
export const PENDING_FILL = '待填充';
export const BACKFILL_PENDING = '待回填';
export const LOW_FREQ_FALLBACK = '多数交易日不开口是常态';

// ==================== S5 修复轮（15-code-review-r2 §8.10；新增文案先入字典） ====================
// R2-D4 · history_days 口径后缀（与 archive_merged 联动）
export const HISTORY_SUFFIX_MERGED = '（含归档）';
export const HISTORY_SUFFIX_MAIN = '（主文件）';
// BLOCK-A3 · 事件链不可复现（前端按 chain_available=false 明示，不空壳）
export const CHAIN_UNAVAILABLE = '该行链路不可复现（代理日线缺失/超窗）';
// S-a · bootstrap 分位来源标注
export const BOOTSTRAP_MEASURED_LABEL = 'bootstrap 500 实测';
export const BOOTSTRAP_FALLBACK_LABEL = '兼容常量（未实测）';
// F-3 · judges 值缺失标注（不渲染空 value）
export const NOT_WIRED_LABEL = '待接入';
// BLOCK-A1 · 「测试连接」诚实降级为本地校验（不发起网络请求）
export const LLM_CHECK_MISSING = '请先填写 Base URL / 模型 / Key（未发起网络请求）';
export const LLM_CHECK_BAD_URL = 'Base URL 格式无效（应为 http(s) 链接）；未发起网络请求';
export const LLM_CHECK_OK = '本地校验通过（格式有效）；连通性测试未接入，不会发起网络请求';
export const LLM_CHECK_BUTTON_TITLE = '本地校验（仅检查配置格式，不会发起网络请求）';
// BLOCK-A2 · 副开关 toast（主开关沿用原文案）
export const PRIVACY_SUB_ON = '已隐藏明细行金额（汇总保留）';
export const PRIVACY_SUB_OFF = '已显示明细行金额';
// C2 裁定（10-arch-review-r2 §11.2）· 注册表三态诚实标注降级：
// 保留组件与三态规则长文，但不呈现「三态已运作」；显式标注单版本现实与预留态
export const REGISTRY_PROVISIONAL_NOTE = '当前单版本运行；shadow/retired 为预留态（版本过渡机制未接入）';
// C0/E-2：持仓卡副标题口径词（R2-25 四层覆盖之「估值覆盖」= change_rate ≠ null 只数；
// 旧字段文本「可信估值覆盖」与四层口径冲突，展示层不再直出该口径词）
export const COVERAGE_VALUATION_LABEL = '估值覆盖';
// C0/E-4：影子盘降级条样本数（数据源 /review/scores?data_kind=shadow_live.hero.open_count；不可得则不显示，不编造）
export const SAMPLE_COUNT_LABEL = '样本';
export const SAMPLE_INSUFFICIENT_NOTE = '，样本不足（<20 笔），偏差仅供参考';

// ==================== C1 增量 · 四本账本人话记录（U-12 字典；组件不硬编码） ====================
// 字段名 → 中文（账本摘要用标签；值缺失一律留白，不编造）
export const BOOK_FIELD_LABEL = {
  factor_id: '因子ID', name: '名称', role: '角色', role_label: '角色', status: '状态',
  license: '牌照', license_label: '牌照', total_score: '总分',
  independent_trigger_days: '独立触发日', open_count: '开口数', death_condition: '死亡条件',
  added_at: '采纳日期', adopted_at: '采纳日期',
  scan_date: '扫描日期', nomination_week: '周次', candidate: '候选因子',
  f1_result: 'F1 有效性', f2_result: 'F2 独立性', f3_result: 'F3 增量',
  f1_detail: 'F1 细节', f2_detail: 'F2 细节', f3_detail: 'F3 细节',
  verdict: '判定', verdict_text: '判定', cooldown_until: '冷却至', created_at: '记录时间',
  date: '日期', loo_delta_pp: '留一法 Δ', red_line: '红线', regime: '环境',
  delta_after_removal_pp: '移除后组合 Δ', conclusion: '结论'
};
// 枚举 → 中文（值域同 09 契约 §2.1；未收录值原样回显，不编造）
export const DIG_RESULT_LABEL = { pass: '通过', fail: '未过', not_run: '未执行', na: '不适用' };
export const DIG_VERDICT_LABEL = {
  candidate_pool: '回落候选池',
  admitted_to_arena: '进入竞技场影子盘',
  rejected_f1: '未过 F1（有效性）',
  rejected_f2: '未过 F2（独立性）',
  rejected_f3: '未过 F3（增量）'
};
export const FACTOR_STATUS_LABEL = { active: '现役', probation: '观察', cooling: '冷却', frozen: '冷冻', retired: '退役' };
export const FACTOR_LICENSE_LABEL = { candidate: '候补', probation: '试用', renew_t2: '续聘 T2', full_t3: '正式 T3', none: '未达线' };
export const RED_LINE_ON = '红线触发';
export const RED_LINE_OFF = '红线未触发';
export const BOOK_BACKTEST_LABEL = '回测';
export const BOOK_WRITE_PENDING = '待写入';
export const BOOK_RAW_TOGGLE_ON = '查看原始数据';
export const BOOK_RAW_TOGGLE_OFF = '返回人话视图';
export const BOOK_READONLY_NOTE = '只读台账 · 无编辑/删除入口；原始数据视图仅供审计';

// ==================== C1+ · 复盘逐笔对账：筛选与排序（纯视图层文案；入字典） ====================
export const RECON_FILTER_CLEAR = '清除筛选';
export const RECON_FUND_PLACEHOLDER = '基金代码或名称';
export const RECON_VETO_OPTIONS = [['all', '全部否决层'], ['crowd', '拥挤度'], ['klow2', 'KLOW2'], ['none', '双灯未亮'], ['missing', '数据缺失']];
export const RECON_SIGNAL_OPTIONS = [['all', '全部信号'], ['up', '涨'], ['gray', '灰'], ['abstain', '弃权']];
export const RECON_LOADED_NOTE = '作用于已载入 {n} 条';
export const RECON_LIMITED_NOTE = '接口限载（共 {total} 条，筛选仅作用已载入部分）';
export const RECON_EMPTY_MATCH = '当前筛选无匹配记录';
export const RECON_SORT_HINT = '点击切换：升序 / 降序 / 取消';
export const RECON_SORT_MARK = { asc: '▲', desc: '▼', none: '' };

// ==================== U-11 · 关键数字口径 tooltip（单一来源） ====================
// 文案模板 = 「分子/分母 · 样本/窗口 · 来源」（07-frontend-arch-r2 §2.10）
export const METRIC_TIP = {
  total_value: '总资产 = Σ 可信行市值（change_rate ≠ null 的行）；未知行按成本单列 fallback_value，不混入。来源 /holdings.summary',
  today_pnl: '今日预估盈亏 = Σ 可信行 [市值 − 市值/(1+涨跌)]。来源 /holdings.summary.today_pnl_amt',
  total_pnl: '累计收益 = Σ 可信行（市值 − 成本）。来源 /holdings.summary.total_pnl_amt',
  return_rate: '收益率 = 累计收益 ÷ 可信行成本合计。来源 /holdings.summary.return_rate',
  covered_count: '估值覆盖 = 当日 change_rate ≠ null 的持仓只数。来源 /holdings.summary.covered_count',
  weighted_p: '持仓加权 P(涨) = Σ(市值×P) ÷ Σ市值；仅开口仓位计入（灰从分子分母同剔）。来源 /portfolio/forecast.weighted_p',
  coverage_ratio: '覆盖占比 = 开口仓位市值 ÷ 组合总市值。来源 /portfolio/forecast.coverage_ratio',
  weighted_mae_est: '估算档市值加权 MAE = Σ(MAE×市值) ÷ Σ市值；样本 = intraday/holdings/proxy（官方档单列，不混入）。来源 /valuations/precision.estimate_quality',
  window_filled: '精度窗累计 = 40 日窗内已积累的可配对交易日数。来源 /valuations/precision.window_filled_days',
  delta_pp: 'Δ = 命中率 − 基线；基线 = max(恒涨率, 恒跌率)，同测试窗实测。来源 /review/scores',
  hit_rate: '命中率 = 独立触发日口径，命中数 ÷ 开口样本。来源 /review/scores',
  progress_shadow: '连续记录 = 主文件 ∪ 归档按 (date, code) 去重的连续交易日数（滚动 60 日；窗口记录为启动回填 + 到期回填的回算口径）。来源 /ledger/shadow.progress',
  baseline_rate: '基线 = max(恒涨率, 恒跌率)，按台账 universe 实测（旧冻结常量已退役，不再参与计算）。来源 /review/scores.baseline_rate',
  fail_window: '失败计数 = 近 7 日（自然日）窗口内失败次数，随窗口滚动自然衰减。来源 /data-sources/health.fail_window_7d'
};
