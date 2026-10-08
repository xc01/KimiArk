# KimiArk / Arknights Auto Planner 完整研发交接

记录时间：2026-10-09（Asia/Shanghai）。来源：本轮用户完整交接。此记录在获取源码前建立。
证据状态：目标与授权为用户明确要求；所有历史代码、实验与提交报告均为 REPORTED_BY_PREVIOUS_WORKER，尚未独立核实。CONFIRMED_FROM_CODE 只能在获取真实源码并检查相应证据后使用；推测标为 HYPOTHESIS。

## 一、项目目标
GitHub：https://github.com/xc01/KimiArk
先前报告的最新提交：5d31ce04693837b5909537a4fcb7c68ea4a2fbd8。必须实际获取仓库并核实最新 commit，不能将此报告视为已核实。
最终目标：让大语言模型真正理解《明日方舟》的关卡，利用游戏事实和模拟器不断修正战术，最终自动生成能够通关的操作方案：
DEPLOY(operator, tile, direction, frame)
ACTIVATE_SKILL(operator, frame)
RETREAT(operator, frame)
部署必须包含方向。WIN 是硬性目标。仅在获得 WIN 后依次优化：干员数量、干员星级总和、时间安排的脆弱性、外部操作数量、可选通关时间。模拟器 WIN 不等于真实游戏通关。

## 二、最重要的设计理念与角色
我们要培养能够从失败中修正战术的自动规划系统，不是不断增加硬编码、只会证明方案不可行的程序，也不是内置大量固定打法的脚本。
Kimi-K3 是战术大脑：理解关卡、提出战术假设、选择战略结构、安排阶段职责，根据失败证据主动改变打法。
Deterministic System 负责事实、计算与执行验证：GameData、精确数值、部署经济、路线、攻击范围、阻挡、时间、几何、合法性、候选生成和模拟器。不能代替 Kimi 决定战术。
GPT / Work 负责研发管理与技术审查：读代码、识别架构问题、审查实验、修复确认的程序缺陷、决定下一研发阶段。
原开发 GLM-5.3 主要负责代码实现，不能擅自替代 Kimi-K3 的战术决策角色。

## 三、确定的架构
Arknights GameData → Mechanics / Stage Facts → Deterministic Battlefield Analysis → Affordance Catalog → Kimi-K3 StageUnderstanding → Kimi-K3 TacticalRequirements → Kimi-K3 StrategicHypotheses → Kimi-K3 OperationalPlans → OperationalPlanCompilerContract → Deterministic Feasibility Verification → Roster / Assignment / Geometry / Timing → Operational Fidelity Certificates → Simulator → Failure Evidence / Counterexamples → Kimi-K3 Tactical Revision。
OperationalPlan 中间层必须保留开局结构、路线职责、压力窗口、阵型演化、技能意图、临时阻挡、火力共享、治疗、撤退和移交的具体战术决策。
不同 OperationalPlans 若被编译成相同通用部署策略而丢失原战术含义，属于错误。动作合法不代表完整执行了战术。

## 四、不可行也是资产
允许 Kimi 起初不理解游戏，希望它通过失败反例持续修正理解。例如计划要求 frame 729 前建立指定防线，但 Required minimum DP 45、Available DP upper bound 40.3，结果 INFEASIBLE。
此结果不能仅用于拒绝方案，应保存为条件性的失败经验反馈 Kimi：哪些职责必须同时成立？哪个截止时间引起冲突？是否错误假设独立部署？能否通过阶段变化重排职责？是否需改变开局经济结构？哪些战术思想仍值得保留？
Python 提供可验证约束与反例，不指定新战术；Kimi 自己理解原因并决定如何调整。
维护可复用 FeasibilityExperienceMemory，每条包括适用条件、证据、约束来源、失败原因及局限性。不能把某份方案的不可行推广成整个战略不可行。

## 五、历史报告（均待实际代码及 artifacts 核实）
1. 静态战术与搜索阶段产生数百条方案，未获 R8-1 WIN；增加搜索数量不能解决战术结构问题。
2. 引入 Kimi TacticalRequirements 与 StrategicHypotheses；高层假说直接到动作会丢失语义，因此引入 OperationalPlans。
3. 曾有 667 条被当时验证器认为 faithful 的方案、无 WIN；后发现 fidelity 不完整，旧结果不能当作严格验证过的战术失败。
4. Kimi-K3 调用已证实可行；Codex 自动续接可能使用不兼容 assistant-message prefill，改为 direct streaming Responses 后完成大规模结构化战术输出。
5. 曾报告 111 个 numeric hallucinations，逐项审计全部是旧校验器错误分类。必须区分游戏数值事实、确定性推导值、合法战术设计数量、标识符、非关键描述。
6. 保真度曾发现并修复 OP-05 route-specific triage/concession 语义丢失、OP-04 干员技能检查过严、EARLIEST_PHASE 未影响部署时间、关键职责 deadline 未正确检查。重验原 170 条 faithful 执行记录均存在 deadline 问题。
7. 五份修订计划在各自硬约束下发生经济冲突：
OP-01 deadline 941，Minimum DP 49，Available DP 47.367；
OP-02 deadline 805，Minimum DP 47，Available DP 42.833；
OP-03 deadline 941，Minimum DP 49，Available DP 47.367；
OP-04 deadline 729，Minimum DP 45，Available DP 40.300；
OP-05 deadline 941，Minimum DP 49，Available DP 47.367。
这是有证据支持的冲突约束集合，未证明是最小 UNSAT Core。
8. Constraint-Informed Tactical Revision V3：Kimi 收到上述证据，恰好一次 Kimi-K3 调用产生三个新 OperationalPlans。旧职责组合改变，但三个计划均在 frame 295 产生新 DP 冲突，未进入战术模拟，学习进度报告 PARTIAL。

## 六、当前必须审查的核心
不是直接让 Kimi 再想三个方案，而是查明为什么三个不同的新计划均在 frame 295 冲突：
- frame 295 是否来自真实关卡压力 deadline？
- 是否共享一条被错误硬化的编译约束？
- 是否要求开局职责过早同时建立？
- 经济下界是否考虑真实干员选择、职责共享及合法技能？
- Kimi 是否真正理解并改变旧不可行假设？
- 新 OperationalPlans 是否被忠实编译？
不能预设是 Kimi 或编译器问题；读实际代码、测试、实验 artifacts 后判断。

## 七、机制与证据纪律
主要关卡 main_08-01 / R8-1；机制版本 m18.9-stage-device-runtime-v1。
GameData 是主要事实源，PRTS、客户端及其他可核实机制证据作补充。禁止猜测修改机制以使战术通过。
R8-1 曾有两种具证据支持的 roadblock targeting 解释。若获得模拟器 WIN，必须用完全相同动作时间线在两种解释下重验，才能声称 robust WIN。真实游戏验证独立处理。

## 八、长期工作方式
每完成重大里程碑，GPT / Work 必须审查真实代码后再决定下一轮：
Worker 完成 → 检查 GitHub 最新 commit → 读实际代码和 diff → 读测试及 artifacts → 核实报告 → 有 bug 则最小修复加回归测试 → 重评瓶颈 → 决定下一个有界里程碑。
不要仅凭 worker 总结生成下一份大型指令，避免无限增设审计层、验证器、工程指标而没有可执行战术。
真正进展包括：消化旧反例、消除旧经济冲突、生成新合法战术结构、忠实编译后进入模拟、战斗失败原因有意义地改变、最终 WIN。
失败需说明新增知识以及它如何改变下一次战术决策。

## 九、长期项目资料
先建立本交接的上下文记录，再获取 GitHub；接管仓库后优先检查已有文档并合并维护，避免重复创建：
PROJECT_CHARTER：目标、用户理念及不可变约束。
ARCHITECTURE_DECISIONS：Kimi、编译器、模拟器职责边界与重大决策。
EXPERIMENT_LEDGER：里程碑输入、代码版本、结果和失效结论。
FAILURE_EXPERIENCE_MEMORY：具有证据和适用范围的可复用失败经验。
CURRENT_PROJECT_STATE：最新已验证进展、未证实假设和当前阻塞。
NEXT_MILESTONE：审查后确定的唯一下一项有界工作及验收条件。
全部记录区分 CONFIRMED_FROM_CODE、REPORTED_BY_PREVIOUS_WORKER、HYPOTHESIS。未核实历史报告不能标为独立确认事实。

## 十、现在执行的第一项任务
1. 实际获取 GitHub 仓库并核对最新提交。
2. 阅读已有项目文档、V3 实现及关键依赖。
3. 建立并维护上述长期上下文，保留全部关键理念和证据状态。
4. 审查三个计划共享的 frame 295 冲突，给出可定位的代码和 artifacts 证据。
5. 若确认通用编译器 bug，做最小修复与回归测试。
6. 判断现有反例能否直接反馈 Kimi，还是应先修复确定性系统。
7. 给出唯一一个有界下一阶段研发计划及验收条件。
完成审查前不得启动 V4 战术推理或扩大模拟搜索。

迁移前状态：项目目标、理念、架构与历史经验已整理；Work 交接曾尝试但尚未成功，GitHub 获取与审查尚未执行。请实际开展上述接管与首轮审查，不只回复确认收到。
