# V3 frame 295 首轮有界审查

审查日期：2026-10-09（Asia/Shanghai）。审查基线：`5d31ce04693837b5909537a4fcb7c68ea4a2fbd8`。

## 结论与范围

实际 clone `https://github.com/xc01/KimiArk.git` 成功；随后 `git ls-remote origin HEAD` 与本地 HEAD 均为上述提交，默认分支为 master。该远端状态是本次获取时的快照，不保证之后不再更新。所有可见源码、23 个 tracked 文件及 18 份 JSON artifacts 已检查。仓库无 AGENTS.md，也没有既有 PROJECT_CHARTER、ARCHITECTURE_DECISIONS、EXPERIMENT_LEDGER、FAILURE_EXPERIENCE_MEMORY、CURRENT_PROJECT_STATE、NEXT_MILESTONE 或 README，因此建立上述长期文档；交接原文完整保存在 PROJECT_CHARTER。

**CONFIRMED_FROM_CODE：三份 artifacts 的 frame 295 冲突共享 route-3:FIRE 输入和相同 V3 编译路径，但尚不足以证明三份 Kimi 战术不可行。** 确认的程序缺陷是将不完整的前缀分析升级为已证明战术失败、unknown deadline 硬化、退款待验证条件漏报及后处理失败前覆盖历史文件，已作最小修复。没有确认 295 本身错误，也没有恢复真实 plan-specific deadline 或完整战术编译器。

**阻塞：当前 GitHub 是局部交付。** 关键 repair 模块、GameData、src/ 模拟器、关卡 context、affordance catalog、旧 DP ledger、旧计划、原始 Kimi response 等均未交付。完整缺项和源文件 SHA-256 见 `evidence_index.json`。源码曾引用另一仓库 `BasicallyKawaii/arknights-auto-planner`；尝试只读 ls-remote 返回需要认证，未恢复任何依赖，不能把它视为已获取的源码。

审查没有调用 Kimi，没有 V4，没有生成动作或运行模拟，没有修改游戏机制，没有更改 18 份历史 JSON artifacts。当前 WIN、robust WIN、真实游戏通关均未建立。

## 三个共同冲突的可定位证据

源码证据：基线 `scripts/run_r8_1_constraint_informed_tactical_revision_v3.py` 的 `feasibility_analysis()`，L923–930 仅把 `route` 与 `kind` 交给 `repair.establishment_deadline(route, kind)`；缺少返回值时 L926–927 改用最早 spawn frame。L937 调用候选池，L939 用 `10 + deadline/30` 作为可用 DP，L966–968 把 first_conflict 升为 INFEASIBLE_WITH_PROVEN_CONFLICT。确切 295 没有在此 V3 脚本硬编码。其来源可能是缺失 repair 的 FIRE 推导，也可能是 spawn fallback；缺失 callee 与 route input，不能确定走了哪个分支。

计划证据：`output/r8_1_constraint_informed_revision_v3/llm_structured_output.json`，JSON pointers `/revised_operational_plans/0`、`/1`、`/2`。冲突证据：同目录 `feasibility_certificates.json`，`/records/0/first_conflict`、`/1/first_conflict`、`/2/first_conflict`。

|计划|冲突火力槽|统一 deadline_basis|历史 minimum DP|历史自然 DP|历史缺口|
|---|---|---|---:|---:|---:|
|A：MERGED-ANCHOR-REFUND-LATTICE|A03_MERGED_ANCHOR|route-3:FIRE|22|19.833333|2.166667|
|B：UPSTREAM-DAM-AND-RELAY|B04_POCKET_FIRE|route-3:FIRE|21|19.833333|1.166667|
|C：DELAYED-KILLING-BLOCK-EVOLUTION|C03_MERGED_ANCHOR|route-3:FIRE|22|19.833333|2.166667|

以上算术在假设下成立；干员 cost、自然 DP 规则、deadline 真实性仍缺原事实输入，表格不是重新完成的真实关卡复验。

A 的 `changed_conflicting_assumptions` 描述把三处火力合并为约 400–500 建立的 anchor；mandatory invariant 要求根据实际 eDPS 测得最新建立时间，并在 805/941 前完成队列清除。B 明确把两个阻挡职责分到上下游，要求 pocket fire 约 600 建立、route-3 在 941 前死亡。C 复用 A 的 merged anchor，延后 ground killing-block 升级。三者早期 fire 的 compiler slot 仍都选择 route-3:FIRE，这构成需要消歧的计划内契约问题；不能擅自只取叙述中的较晚时间，也不能未经证明只取统一 295。

V3 调用没有传递新 blocker、阻挡位置、block count、伤害能力、queue-clear objective 或 phase 来推导 FIRE 时间。HYPOTHESIS：通用 deadline 沿用了旧 blocker 的接敌/生存时间，使新结构被过早硬化；也可能该 deadline 来自真实且不可放宽的威胁。恢复函数和事实输入后才能区分。

## 经济下界与忠实性审查

1. **CONFIRMED_FROM_CODE：自然收入算术不是完整经济上界。** V3 只用 10 + frame/30，忽略技能 DP、退款、再部署成本与时间。若证明某前缀在 295 前没有合法额外收入，可以保留自然-only 上界，但当前源码没有该证明。计划 A 的退款叙述约 390，不能把这笔退款提前挪到 295 来消除冲突，也不能凭该叙述宣布每种合法经济机制在 295 前都无贡献。
2. **CONFIRMED_FROM_CODE：固定不同干员指派。** walk() 的 used 集合禁止一个干员占多个槽；不读取 may_share_live_operator、条件职责、replacement_group、phase 和撤退移交。A/C 的三路共享已写进同一个 fire 槽，本项不证明其 295 前缀被重复收费；它只说明分析器不能普遍证明共享/时序计划的 fidelity。
3. **CONFIRMED_FROM_CODE：角色池没有完整能力验证。** RANGED_DPS/KILLING_BLOCK/RELAY/PIONEER_BLOCK 走 generic selected_usage_pool；V3 只另外检查 max_cost_design_choice，没有验证槽的 eDPS、auto-cycle、目标防御和多路几何要求。历史 minimum_assignment 选了 char_124_kroos，并未证明它满足 merged anchor。放宽候选池可能给出更乐观的成本下界，不能仅凭放宽就说算术下界错误；但该 assignment 绝不是 faithful witness。
4. **CONFIRMED_FROM_CODE：只分析 deadline <=729。** 中后期、条件让路、升级、技能周期和 win/life budget 都未验，前缀无冲突也不证明全计划可行。
5. **CONFIRMED_FROM_CODE：unknown timing 被硬化。** None deadline 原先被 spawn_frames 最小值代替，没有依据证明出生就是必须建立职责的期限。已去除此 fallback；未知保持未知。
6. **CONFIRMED_FROM_CODE：退款条件漏报。** 原先仅找大写字面串 RETREAT，但三份真实 slot 的 retreat_basis 使用小写 single retreat，导致历史 certificates 的 required_unverified_conditions 全空。已改成依据非空 retreat_basis 或 must_vacate_slot 标记待验证条件；不改变退款金额或时机。
7. 跨计划 shorthand 通过 all_plan_slots 一次引用展开；部分字符串还有进一步引用。该行为未完成可靠契约解析，但不能无证据断言它是本次共同 295 的原因，本轮没有扩大到重写自然语言约束解析器。

## Kimi 是否消化旧经验

CONFIRMED_FROM_CODE：保存的结构化输出逐项提到 EXP-001…006，提出去除开局 pioneer/mandatory medic、合并 anchor、上下游分流、cheap body 到 killing-block 的分期升级，显然不是只有 roster 微调。REPORTED_BY_PREVIOUS_WORKER：这确实由恰好一次成功 Kimi-K3 调用产生。原 response、envelope、completion validation 与实际 request 缺失，fingerprint 和保存的 KIMI_CALL_COUNT=1 只证明报告写了这个数字，不能独立认证调用次数、成功或 response 完整性。

未证明这些战术假设正确、消除旧经济冲突或已进入 fidelity-certified execution。原 learning_progress 把遇到新的 first_conflict 自动计为 OLD_CONFLICT_REPLACED_BY_NEW_CONFLICT，没有比较旧职责冲突集合，不能据此确认学习进度。不同叙述具有价值，但真实战术学习必须以消除旧约束/忠实执行/新的战斗失败证据验证。

## 最小修复与验证

修复只涉及 V3 证据纪律，不发明新打法或游戏机制：
- 将此简化分析固定输出 FEASIBILITY_UNKNOWN，保留诊断算术及 proof_limitations；prefix 名称改为 diagnostic conflict/no conflict，空池单独分类。
- 删除 None → spawn deadline fallback；修复退款条件发现。
- 学习和战斗反馈只接受真正 proven 的 classification，当前诊断不计为新证明或已替换旧冲突。
- postprocess 先计算必需验证，再写历史 artifacts，依赖失败不会留下部分更新。

五项新回归使用明确标为 synthetic 的 adapter/pool fixtures，验证软件分类与数据保护，不冒充恢复 GameData、实际经济或可行战术。对基线源码运行相同五项测试：5 failures，0 errors；补丁后：5/5 PASS。传输测试 10/10 PASS；compileall 与 git diff --check PASS。

完整当前测试为 23 项：20 PASS、1 failure、2 errors。原八项 V3 测试中 5 PASS，另外三项仍因未交付旧 audit input、response_completion_validation.json 和 llm_raw_response.txt 失败。没有跳过或改写这些缺项测试。历史 validation_results.json 的 18/18 PASS 只能作为旧报告，不能声称该 fresh clone 通过。完整输出见 validation.json。

## 反例反馈与唯一下一里程碑

**先修复并恢复确定性链。** 可以把“共享 route-3:FIRE、计划叙述与 slot 契约待消歧”反馈作为编译问题；不能把“295 时 DP 不够”作为不可更改的游戏事实要求 Kimi 再想三份计划。旧五份经验仍保存，证据状态为历史报告，其 applicability/limitations 必须保持。

唯一下一阶段为 **恢复 V3 必需源证据，并只对现有 A/B/C 做忠实编译复验**。完整范围和验收条件见 NEXT_MILESTONE：不调用 Kimi、不新增计划或扩大搜索；恢复精确源版本，解释 295 的可复算来历；按现有战术契约推导 queue/kill deadline，检查完整经济及角色、几何、分期和移交；每份给出可复验的条件冲突、未知原因或方向完整的可执行 witness。若依赖仍缺失，应停止在明确 UNKNOWN，不伪造验证。只有 faithful witness 可进入固定时间线模拟，最多每个现有计划一条，不做新搜索。若出现 WIN，再用相同动作时间线重验两种 roadblock targeting 解释；真实游戏验证独立。
