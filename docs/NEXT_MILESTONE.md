# Work review gate: terrain WALK navigation restored; roadblock navigation UNKNOWN

CONFIRMED_FROM_CODE：公共共享 `WalkNavigator` 已按客户端语义恢复地形级 WALK 导航：四方向 SPFA、严格改进、UP/RIGHT/DOWN/LEFT 顺序、Bresenham/Segment 平滑和对角侧格检查。adapter 读取 `motionMode` 和 `allowDiagonalMove`，不再把 WALK MOVE 点直连。route-3 控制仍为 `(1,1)→(9,1)`。静态证据显示 route-2/6/7/8 的地形路径不穿 `FLY_ONLY` 格内部，route-2 重复经过仍保留。

UNKNOWN：活跃 `trap_020_roadblock` 对普通 WALK 敌人的 SPFA/移动影响、客户端运行时精确取整、阻挡半径和等待期阻挡规则仍未证明。`conditional_roadblock_as_full_obstacle_routes` 只是没有依据的假设变体，不能反馈 Kimi 为客户端事实。

普通模式1～3星、排除模式专属预备干员的约束继续有效。本轮 Kimi 0、真实关卡模拟 0、新 OperationalPlan 0、新动作候选 0、战术搜索扩展 0。原 B2 六动作未修改。

关键证据：

- `output/r8_1_walk_navigation_facts_v1/walk_navigation_facts.json`
- `output/r8_1_walk_navigation_facts_v1/source_evidence.json`
- `output/r8_1_walk_navigation_facts_v1/adapter_conversion_check.json`

下一步由 Work 审查代码与 artifacts。若确认地形事实充分，再决定是否需要一次有界 Kimi-K3 修订；不要自动启动。
