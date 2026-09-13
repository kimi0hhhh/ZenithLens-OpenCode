// 四态文案与错误码文案（07 §4；09 §3）
// 静态框架文案；事实卡数字由各视图用后端字段填充。
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

// 各视图四态文案（空/加载/错误）
export const STATE_COPY = {
  holdings: {
    empty: { big: '还没有录入任何持仓', sub: '录入第一只基金后，这里会显示组合总览与实时估值。' },
    loading: { big: '正在读取持仓与估值…', sub: '首次加载会同时拉取行情与官方净值' },
    error: { big: '读取持仓失败', sub: '无法读取持仓数据：文件不存在或格式错误。已保留上次缓存数据。' }
  },
  analyze: {
    empty: { big: '今日没有触发开口的资产', sub: '这是常态。只有满足触发门并穿过双否决的资产才会进入预测。' },
    loading: { big: '正在计算三窗口预测…', sub: '按开口仓位市值加权，并计算覆盖市值占比' },
    error: { big: '预测服务暂不可用', sub: '引擎未响应或数据缺失。历史成绩仍可查看（标注时间）。' }
  },
  signals: {
    empty: { big: '今日无信号', sub: '监控中，今日均未触发开门条件 —— 这是常态，不是故障。' },
    loading: { big: '正在读取信号台账…', sub: '按日期倒序加载近 60 天记录' },
    error: { big: '读取信号台账失败', sub: '台账文件不可读或损坏。' }
  },
  factors: {
    empty: { big: '因子库为空，等待首次扫描', sub: '每周提名 ≤3 个候选，冷却 90 天防多重检验。' },
    loading: { big: '正在读取因子账本…', sub: '加载四盘与账本记录' },
    error: { big: '因子账本读取失败', sub: '至少一个账本文件缺失或格式错误。' }
  },
  review: {
    empty: { big: '尚无成绩记录', sub: '引擎尚未产出回测结果，或成绩文件缺失。' },
    loading: { big: '正在汇总历史成绩…', sub: '计算命中率、基线与 Δ（走前 CV）' },
    error: { big: '读取成绩失败', sub: '成绩文件不可读。' }
  },
  engine: {
    empty: { big: '引擎离线', sub: '未检测到本地引擎心跳。启动后本页显示只读观测面板。' },
    loading: { big: '正在连接本地引擎…', sub: '等待心跳与台账状态' },
    error: { big: '引擎无响应', sub: '心跳超时。可查看已缓存的只读数据。' }
  },
  settings: {
    empty: { big: '尚未检测数据源', sub: '点击下方检测，确认行情/估值接口连通性。' },
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

// 估值置信度中文（09 §5.2 confidence_label）：precision groups 尚无 label 时统一映射
export const CONF_LABEL = { high: '误差达标', mid: '误差中等', low: '误差偏大', unknown: '无可信估算' };
