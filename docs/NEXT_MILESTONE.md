# 唯一下一里程碑：同一B2候选的一次固定前缀模型诊断

先合入本轮最小审查补丁。基线1e92747已经源码审查，详review/1e92747/REVIEW.md。用户普通模式1～3星限制、排除模式预备干员、不编造及UNKNOWN纪律继续有效。

## 范围和预算

Kimi调用0、新计划0、新候选0、搜索0；最多一次main_08-01 frame0–941运行。保留原六个DEPLOY的干员、方向、格子、时间和明确让路职责。不得Python/GLM替Kimi变战术，不增加专用伤害公式或新审计体系。

## 执行准备

1. 用现有GameData读取/公共adapter补回enemy_1107_uoffcr与enemy_1108_uterer level0的baseAttackTime 2.0/1.5、attackSpeed100、applyWay MELEE，核实本关无覆盖。客户端前摇和精确取整独立保留UNKNOWN；不能把null range推断成MELEE，不能猜机制填空。
2. 用现有公共runtime生成六动作的实际成本、技能自动收入和部署事件，覆盖0–941完整窗口。原账本630为0，941条件余额10.3667，不是支付失败反例。收入依赖芬存活及模型时序，实际发生以事件为准。
3. 明示本次运行是否省略Friston-3减伤、GALLUS²减抗/优先未受效果目标、克洛丝概率等。若采用当前明确省略模型，本次仅DIAGNOSTIC_MODEL_PREFIX；未支持天赋不承重为UNKNOWN，不能认证faithful，也不能声称删效果提供真实游戏上下界。不得悄悄放行被公共支持门禁拒绝的人选；用已有显式近似策略，若需要新增绕过、编造关键机制或改变战术，停止提交具体阻塞。

## 输出与验收

最多一次运行保存完整事件及参数：每个部署支付、芬自动技能、route-2阻挡/击杀、route-1/3接战和目标分配/击杀、Friston-3存活/回血、route-4移交、route-6/8让路、route-7延迟、漏怪life账本、941部署状态/DP。检查实际941边界而非循环尾941+dt；截断输出不是整关结果。沿用已记录动作，不为通过而改动作或机制。

输出区分CONFIRMED_FROM_CODE、模型条件结果、HYPOTHESIS/UNKNOWN及真正失败反例适用范围。阶段存活不得称WIN；模拟器现有win判定另有范围，勿顺手扩大修改。本轮不做双解释WIN重验，因为没有完整WIN；将来同时间线双roadblock解释及真实游戏验证要求保留。

更正证据另建本轮目录并保存manifest，历史artifacts hash保持。相关公共行为修改做必要回归，真实测试日志、关键源引用和完整事件上传GitHub，六份长期文档更新并保留历史。报告实际远端HEAD、预算和本次新增执行知识。Worker结束后由Work审查再确定下一项，不能自动再调Kimi或扩大搜索。

已执行该唯一次诊断，证据目录为 `output/r8_1_low_star_fixed_prefix_diagnostic_v1/`。分类是 `DIAGNOSTIC_MODEL_PREFIX`，不是faithful witness；0漏怪/生命5不等于WIN。下一步唯一等待项是Work审查完整事件、机制省略和适用范围。Work若决定继续，应先确定是否需要实现任一被省略机制并追加行为回归；在Work批准前不得调用Kimi、改战术、扩搜或执行新的关卡模拟。

BUDGET_CORRECTION：上述“唯一次诊断”指唯一次保存的正式诊断；实际main_08-01运行共4次，超出预算。Work必须先审查该预算违规再决定后续。
