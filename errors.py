# -*- coding: utf-8 -*-
"""错误码常量与异常包装。

错误码口径来源：docs/01-architecture/09-api-contract.md §3（穷举 10 个）。
统一信封 {ok, data, error, as_of} 由 app.py 组装；本模块只定义错误与映射。
"""

# --- 契约 §3 错误码（穷举，禁止新增） ---
E_IO = "E_IO"                      # 本地文件读写失败
E_PARSE = "E_PARSE"                # 数据/文件解析失败
E_SOURCE_TIMEOUT = "E_SOURCE_TIMEOUT"  # 外部行情/净值源超时
E_ENGINE_OFFLINE = "E_ENGINE_OFFLINE"  # 引擎未运行/无快照
E_VALIDATION = "E_VALIDATION"      # 请求参数不合法
E_NOT_FOUND = "E_NOT_FOUND"        # 资源不存在
E_CONFLICT = "E_CONFLICT"          # 唯一性冲突
E_PORT = "E_PORT"                  # 端口全部占用（仅启动日志）
E_VERSION = "E_VERSION"            # Python 版本不满足（仅启动）
E_UNKNOWN = "E_UNKNOWN"            # 未归类错误

ALL_CODES = (E_IO, E_PARSE, E_SOURCE_TIMEOUT, E_ENGINE_OFFLINE, E_VALIDATION,
             E_NOT_FOUND, E_CONFLICT, E_PORT, E_VERSION, E_UNKNOWN)

# 错误码 -> 典型 HTTP 状态（契约 §3）
HTTP_OF_CODE = {
    E_IO: 500,
    E_PARSE: 500,
    E_SOURCE_TIMEOUT: 503,
    E_ENGINE_OFFLINE: 503,
    E_VALIDATION: 400,
    E_NOT_FOUND: 404,
    E_CONFLICT: 409,
    E_UNKNOWN: 500,
}

# 错误码 -> 面向用户的可读前缀（契约 §3「前端文案前缀」）
MESSAGE_OF_CODE = {
    E_IO: "读写本地数据失败",
    E_PARSE: "数据格式错误",
    E_SOURCE_TIMEOUT: "数据源暂时不可用",
    E_ENGINE_OFFLINE: "引擎未运行",
    E_VALIDATION: "参数不合法",
    E_NOT_FOUND: "未找到",
    E_CONFLICT: "已存在",
    E_PORT: "端口全部占用",
    E_VERSION: "Python 版本不满足",
    E_UNKNOWN: "发生未知错误",
}


class ApiError(Exception):
    """业务异常。msg 为面向用户的可读原因（已脱敏）。"""

    def __init__(self, code, message=None, detail=None, http_status=None):
        if code not in HTTP_OF_CODE:
            code = E_UNKNOWN
        self.code = code
        self.message = message or MESSAGE_OF_CODE.get(code, MESSAGE_OF_CODE[E_UNKNOWN])
        self.detail = detail
        self.http_status = http_status or HTTP_OF_CODE.get(code, 500)
        super(ApiError, self).__init__(self.message)

    def envelope(self):
        err = {"code": self.code, "message": self.message}
        if self.detail is not None:
            err["detail"] = self.detail
        else:
            err["detail"] = None
        return err
