# 唯一下一里程碑：恢复 V3 源证据并忠实复验现有 A/B/C

状态：READY_FOR_INPUT_RECOVERY，关键源文件缺失；这是审查后的单一有界工作，不是 Kimi V4。

## 范围

恢复 review/evidence_index.json 列出的原始 repair/依赖闭包、关卡 context/catalog、GameData/模拟器的确切版本、旧 ledger/trace 与原 Kimi request/response/completion；记录源 commit、hash、机制版本。原工作目录或完整归档是当前缺件的必要来源。不能用测试 stub、旧摘要或新模型调用替代。

只复验既有三份 OperationalPlans，保持原结构和用户职责边界。不生成新计划，不调用 Kimi，不扩大候选/模拟搜索，不猜改机制。

## 验收条件

1. fresh checkout/明确版本的依赖包可独立运行相关测试及离线复验；缺失清单逐项有真实文件和可追溯版本。原调用证据缺失则继续保留 REPORTED，不造一次调用证明。
2. 对三个 fire 槽逐一列出 295 的真实来源、route event、所用位置/干员/队列假设及推导；区分接敌、必须阻挡、必须开火、必须击杀，解决计划叙述与 deadline_basis 的冲突。任何放宽均需可复算事实，不把 400–600 叙述直接设为 deadline。
3. 现有计划分别检查真实候选能力/选定技能/朝向/覆盖、共享职责、条件让路、分期替换、完整自然与技能 DP、合法退款/再部署时机，建立每条约束来源。退款在发生前不可使用；额外收入不可凭猜测计入。
4. 每份输出一个确定结果：具范围和来源的冲突证据，或明确 UNKNOWN 及缺项，或完整 faithful witness。不能只因 cutoff<=729 无冲突就判可行；不称 minimal UNSAT core，除非另有最小性证明。
5. faithful witness 必须包含 DEPLOY(operator,tile,direction,frame)、ACTIVATE_SKILL、RETREAT 及责任/phase/skill/transition fidelity。最多每份既有计划一条时间线、总计不超过三条；没有 witness 则模拟零次。若可执行，模拟后记录有意义的首因，不增加搜索。若 WIN，以相同时间线重验两种已知 roadblock targeting，才记录 robust WIN；真实游戏单独验证。
6. 审查真实 diff、测试和 artifacts 后更新六份长期文档，再决定后续阶段。未满足条件不启动 Kimi V4。

停止条件：依赖恢复失败或合法经济/机制仍无法证明，则以 UNKNOWN 交付精确缺项和下一决策所需证据；不得用 blanket proven 拒绝继续学习，也不得合成成功验证。
