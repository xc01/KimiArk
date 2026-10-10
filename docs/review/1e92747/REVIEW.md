# 1e92747 独立源码审查

基线：1e92747d298e9fb060c0965e4f2f2990a723f46e；实际 fetch、检出及 git ls-remote origin HEAD 一致。未调用 Kimi，未执行关卡模拟。

## 核实结果

CONFIRMED_FROM_CODE：34名普通获取元数据下的1～3星干员与固定character_table逐项ID匹配；包括全部17名三星。事实目录完整不等于运行时机制完整：AoE、概率及若干天赋仍未支持。不能宣称已补齐全部三星运行时机制。

CONFIRMED_FROM_CODE：原始SSE重放44724事件，response.completed，最终文本与structured JSON一致。基线milestone manifest 27条、source input manifest 7条hash/bytes匹配。可确认一份成功保存的响应；服务器全局总调用次数仍是worker报告。源表character/skill/range实际取得且hash与manifest匹配。

CONFIRMED_FROM_CODE：六个方向完整部署与Kimi计划deployment_positions一致；它们只是局部部署合法候选，不是faithful witness。测试通过不会改变这一点。复验原定向集合本环境48项通过，加3项行为回归后51项通过；worker报告47项是其日志计数。compileall及git diff --check通过。

## 确认的验证器缺陷与最小修复

1. scripts/compile_r8_1_normal_low_star_plan_v1.py::dp_ledger / semantic_certificate：原账本停在630，拿630的0 DP比较计划941的约17 DP。六次部署成本合计37，计划声称30也算错。在原有自然回复及芬570获得6 DP、持续存活的条件下，941余额应为10.3666667，而非0或17。修复推进账本到941并记录比较帧及存活收入条件。仍有叙事误算，不能把0 DP旧结论反馈为941事实。
2. counterexample_avoidance：仅凭catalog存在和计划写“No unsupported mechanic”就认证不承重，这是自述循环。现改为null/UNKNOWN。GALLUS²部署20秒内优先攻击未受其减抗效果的敌人，不能将忽略它简单视为少算伤害。Friston-3减伤与克洛丝概率效果同样需限定证据范围，不整体排除普通合法干员。
3. semantic_certificate分类：原三元表达式会让叙事差异遮盖部署冲突。现先判断结构/合法性冲突，随后分类叙事差异。增加行为回归。

历史output artifacts未覆盖；本次更正单独保存在docs/review/1e92747/corrected_dp_and_certificate.json。未修改公共机制、战术、动作或选择。

## 应补回已有事实

固定enemy_database中enemy_1107_uoffcr level0 baseAttackTime=2.0、attackSpeed=100；enemy_1108_uterer level0 baseAttackTime=1.5、attackSpeed=100，均applyWay=MELEE。level_main_08-01引用这两个level0且overwrittenData=null。不是未知游戏事实；本次Kimi输入遗漏它们。客户端攻击前摇/离散取整仍独立UNKNOWN。代码现有source读取和公共runtime应复用，禁止继续凭attack_range=null推断攻击方式。

## 判断与唯一下一阶段

Kimi确实改了开局结构、经济人选与让路集合；还没有执行层学习证据。先补确定性输入，沿用已保存B2六动作开展一次固定0–941模型诊断，Kimi0次、新计划0个、搜索0。不支持天赋的省略必须显式标记，并禁止把模型结果升格faithful、真实战术不可行或WIN。若公共入口需要猜测关键事实或改战术才能运行，停止并保存具体阻塞。详docs/NEXT_MILESTONE.md。
