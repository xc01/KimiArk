# f1a1c7d 独立审查

日期 2026-10-09；实际 fetch + ls-remote 核实 master HEAD `f1a1c7db72f7912b30ca7edae7fc5a239d98d386`。本次读取真实 diff、恢复源码、manifest、历史 artifacts、测试，不使用 worker 总结替代证据。不存在 AGENTS.md。

## 判定

**接受 295 重分类；不接受“完整依赖已恢复、可进入完整 witness”的无条件表述。** 目前事实来源和旧原始模型输出已可独立确认，但 fidelity 候选边界与 fresh checkout 的测试复现仍有缺项。没有 Kimi 调用、计划新增、阶段计划模拟或 WIN。

## 已核实事实：CONFIRMED_FROM_CODE

- patch 内容已合入：远端 `5204b65` 与本地原 `3ddde67` 是不同 SHA 的应用提交；代码中诊断分类、unknown→spawn fallback 删除、退款条件检测及后处理顺序修复均保留。不要把重应用产生的 SHA 差异误认为补丁未合入。
- `run_r8_1_operational_semantic_preservation_repair_v1.py::establishment_deadline` 在 FIRE 分支直接返回 earliest_operator_contact_frame。该通用假设解释了三个 route-3:FIRE 槽共同得到 295，不是 spawn fallback。本 helper 仍存在，不把它当成已经具备 plan-specific deadline 的编译器。
- 从 GameData 固定 commit `0ef7f952dfd018392200157a5c79a6511ba69122` 实际取得 level 和 enemy_database。level 字节 SHA-256 与交付副本完全一致，目标 enemy entry 与数据库语义一致。
- stage 0/fragment 1 的 preDelay 5 秒 + spawn action preDelay 3 秒 = 8 秒/frame 240。地图 y 变换后 route-3 是 [1,5]→[9,5]，两块 MELEE road [3,5]/[8,5] 距离分别 2/7，speed=1.1，在当前 30fps 时钟下得到 295/431。真实原生成器使用 floor(seconds*fps+0.5)，这两点与 ceil 恰好一致；不得因此宣称所有未来边界都用 ceil。
- 295 是模型中最早合法近战拦截格的无阻挡到达事件；431 是最晚合法近战格的无阻挡到达事实。431 也不能无条件套到不同位置：B 的 upstream dam 在 [3,5] 与 [8,5] 是不同职责/地点，必须分别推导。
- 三份 fire 的建立 deadline 仍 UNKNOWN；杀死 route-3 before 941、A/C route-1 before 805 等是计划目标，须结合选定干员、技能、朝向、射程、阻挡、队列与技能帧序推导，不能直接用 295 或 600 替换。
- source manifest 12 个文件的 bytes/hash 全匹配；gzip 原始 SSE 解压 23,871,994 bytes，hash 匹配；解析 95,471 个 events，terminal=response.completed，无 parser error，重放 envelope 和最终 structured JSON 均与保存副本相同。
- prompt fingerprint 匹配；按源码原始键序和 output_schema 重建请求后，request fingerprint 也匹配。直接对已 sort_keys 写盘的 JSON 再 dumps 键序不同，不是请求被篡改。
- 这验证了一条完整保存的 Kimi 响应；不能仅凭保存文件证明历史上绝对没有额外调用。

## 确认的新缺陷与最小修复

`load_fidelity_tables()` 条件式加载两张表，缺文件时静默保留空字典；fresh checkout 不含 `output/operator_runtime_fidelity_v1/all_operator_fidelity.json` 和 `all_operator_census.json`。selected_usage_pool 在空表下跳过部分 talent/trait 检查。

实证：worker 保存三份 pool 各 21 个候选；fresh checkout 的相同 build 各变成 22 个，新增 `char_4211_snhunt`，而测试只检查 pool 非空，仍 29/29 PASS。该干员恰好是 A/B/C 提出的示例 anchor，候选边界变化足以影响后续 witness，不是无关统计差异。context 中它 planner_safe_for_selected_skills=false / NEEDS_SMALL_RUNTIME_EXTENSION，是否能合法承担当前职责须依真实表和 selected skill 检查，不由审查模型擅自决定排除或放行。

最小补丁只修改本轮 source-reverification 脚本及其测试：显式列两张表的 presence/count/hash，缺表时 candidate pool 状态为 UNKNOWN_MISSING_FIDELITY_INPUTS、整体 BLOCKED_MISSING_FIDELITY_INPUTS，禁止生成看似真实的候选列表。新增 write_artifacts=False，使只读测试不覆盖历史输出。测试通过表示软件明确报阻塞，不表示证据已齐或战术可行。没有把原 21 候选伪造到代码中，没有放宽任何能力门槛。

## 测试结果与局限

- 原 worker 定向 29/29 PASS 在本环境重现；最小修复后 31/31 PASS（新增缺表与只读保护回归），compileall/diff-check PASS。
- 原环境无 pytest，在独立 review venv 安装仓库已声明的 pytest 8.4.2 后完成 pytest collection；不是七个 import failure 必须永久阻塞。
- fresh 基线 unittest 实际 Ran 67、32 PASS、1 failure、34 errors，部分 setUpClass 故障不能计为被执行的全部方法；不能拿这组与 worker 94 简单逐项相减。缺真实 GameData 与若干未交付历史 artifacts、fidelity 表造成多数错误；OP04 的 <=9 assertion 在空表时重算成 12，进一步印证 fidelity 输入影响结果。
- worker 的 87/94 可能来自其带 GameData/额外 output 的服务器工作区，本次没有证据说其伪报；但“只有缺 pytest”不是 fresh clone 的完整故障说明。原始日志独立保存于本目录，不篡改旧 validation。
- 没有扩大模拟搜索；没有调用任何 plan simulator。只重放保存的响应并执行相关回归。完整 GameData 树未下载，所用两个 pinned 原始文件是最小事实核查。

## 下一阶段决定

选一个现有计划 A，验证 opening 至 frame 941 的局部 constructive witness；先把真正影响干员筛选的两张源表和其版本交付，再固定 A 的职责契约。不要先把三份计划都写成新的通用模板，也不要先让 Kimi V4 再生成计划。

本阶段要得到方向完整的开局时间线及每条 mandatory responsibility 的建立/击杀证据，或有来源和适用条件的具体阻塞。退款、技能或 trait 支持缺少事实即 UNKNOWN；不能编造 DP，不能偷偷把 merged anchor 拆成多个不被计划许可的角色。已发现的缺表修复用于维护证据边界，不作为新增审核层无限扩展。详细预算及验收见 docs/NEXT_MILESTONE.md。
