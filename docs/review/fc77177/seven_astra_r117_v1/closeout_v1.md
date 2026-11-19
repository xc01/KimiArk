R117因唯一战术CLI在本地配置加载阶段退出而阻塞，未进入战术模型生成。实际计数：CLI进程启动1/1，已观察模型生成0，生产check0/500、合法冻结候选0/100、真实模拟0/100，完成战术轮数0/5。按授权不重启、不换模型、余额不自动转移。没有新战术结论。

实时正式模型目录确认gpt-6.2-astra存在且支持low。新R117三项生产账本均为0，MCP initialize/initialized/tools/list/status握手以及隔离fake计数预检通过。三条父方案完整计划、原始事件路径和hash已保存；用户补充“炮兵后输出/上路医疗只是待检验假设，可修四漏父项或恢复22杀后期，也可第三条路”已逐字表达在tactical_prompt.txt中。Astra没有进入生成，因此没有实际读取回放、选择父项或做出战术决定。

直接原始错误：

    Error loading config.toml: model_providers contains reserved built-in provider IDs: openai.
    Built-in providers cannot be overridden.

退出码1，codex_exec.jsonl为0字节，无thread.started、turn.started或战术工具请求。新CLI实际进程已启动并立即退出，计数保持1，不以没有生成为由回滚。内部CLI请求数保守记UNKNOWN_CLI_INTERNAL；模型usage因配置加载先失败而不适用。不能推断额度耗尽或Astra服务不可用，也不能保证正常生成与余额可用。

根因是执行端准备脚本为禁止内部自动重试加入了以下两条覆盖：

    model_providers.openai.request_max_retries=0
    model_providers.openai.stream_max_retries=0

两条键使Codex解析出model_providers.openai自定义配置，而当前版本禁止覆盖保留的内置openai provider。标准MCP零生成握手不加载Codex的provider配置；命令授权校验只核对参数与冻结allowlist一致，未覆盖这一Codex语义限制。因此这是执行端引入并漏检的本地启动配置问题，不是战术模型没遵守指令，不是战术LOSS或服务额度错误。

startup_blocker_v1.json保存原始错误、时间/进程记录引用、无生成边界及纯静态TOML展开结果。session/codex_cli/中保留完整原始argv、冻结输入hash、进程PID、stderr、空stdout和退出记录。preflight.py和model_authorization_v1.json保留原状作为失败证据。proposed_authorization_correction_NOT_EXECUTED.json仅移除这两项错误覆盖，模型和low不变；它是未执行的派生建议，不能把它当已通过的正式启动，也没有因修复提议而再次调用CLI。

后续如另行授权新CLI尝试，最小前置是采用受支持的provider配置，先做无生成配置解析兼容检查，再用真实command/args/cwd/environment核对MCP；只读目录存在及MCP正常都不证明模型生成/额度正常。若需要严格禁止CLI内部自动请求重试，应查明实际版本支持的正式配置方式；不能再次用保留provider覆盖、吞掉错误或伪造已通过。该准备和重新启动未在本批执行。

R115/R116的账本、模拟预算和封存状态hash已逐一与启动前比对相同；两条29杀四漏、22杀局部联合分支及M70均保持。R117仅含启动与协议证据，没有候选、模拟或经验负奖励。当前固定模拟器结论未变：M70八人完整WIN最佳，七人及更少完整WIN仍UNKNOWN。未推送。
