# Codex 配置与图片路由

规范：[relay-config-images](../openspec/specs/relay-config-images/spec.md)。

## 一键配置

在 API 页选择“一键配置到 Codex”和对应 Key。已保存 token 时默认直接复用，
可勾选重新生成；历史 Key 尚无 token 时，首次导出必须确认重置。部署本身不会
重置任何旧 Key。API Key 原有的“重新生成”操作也会同步更新 token 池。

选择 macOS/Linux 的 Bash 或 Windows 的 PowerShell 命令后复制执行。
需要 Python 3.11+，无需安装 Python 库。命令使用当前网站地址，更新当前自定义
Provider（没有则创建 `openai_https`），把 token 直接写进 config.toml，启用
`api_key_model_discovery`，并设置模型目录与 actor header。执行后完全重启 Codex。

修改前会生成 `config.toml.bak.<时间戳>`；无变化时不重复备份。无效 TOML 会中止，
不会覆盖原文件。恢复按钮可恢复最近备份，但无法恢复已被服务端重置的旧 Key。
原先的 `codex-lb.key` 文件不再用于新配置，不会被自动删除。

管理员与访客均可使用；访客仅能导出分配给自己的有效 Key。普通 Key 列表不会
泄露 token。token 按要求明文保存在服务数据库和客户端配置内，因此应限制数据库、
备份、配置文件及命令的访问权限，公网部署请使用 HTTPS。

## 图片模型与宿主

`gpt-image-2` 不再固定跳到 `gpt-5.5`。实体账号仍需要一个 Responses 模型承载
图片工具，但它与公开图片模型独立：设置页“图片模型路由”可以指定宿主，留空
则按当前模型目录自动选择。日志分别显示公开图片模型和 Image host model，
图片 token/费用按图片模型记录，不拿宿主文本 token 冒充。

Model Source 在模型列表中启用 `gpt-image-2` 后，会参与与实体账号相同的
优先级、权重、额度降级和 Key 分配选择。被选中后直接调用上游 Images API，
不经实体账号宿主。图片编辑会转发图片及 mask；source-only Key 无需实体账号。
流式请求仍需在 source 的该模型条目启用 streaming。

source 上游必须实现对应 `/images/generations`、`/images/edits` 接口。
有限额 Key 若缺少最终 usage，会报错并释放预留，不交付无法结算的最终图片。
图片价格继续采用账号池现有费率；当前的统一输入费率不是供应商按文本/图片
输入分别收费的精确账单。此轮不重算历史费用。
