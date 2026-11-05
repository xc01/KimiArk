# KimiArk Tactical Battle Replay V1

`scripts/tactical_battle_replay_v1.py` 是只读的本地终端回放器。它读取已有 diagnostic 事件、action/plan snapshot、manifest、final status 与 facts，不导入或调用模拟器，不生成新战斗，也不改变预算、冻结方案或事件原件。

## 命令

```bash
.venv/bin/python scripts/tactical_battle_replay_v1.py \
  docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic/diagnostic_events.json.gz

.venv/bin/python scripts/tactical_battle_replay_v1.py \
  docs/review/fc77177/m70_full_roster_reassessment_v1/evidence/attempts/attempt_01_diagnostic/diagnostic_events.json.gz \
  --dump-frame 2053

.venv/bin/python scripts/tactical_battle_replay_v1.py \
  docs/review/fc77177/m76_open_reduction_v1/evidence/candidate_v1_raw/diagnostic/diagnostic_events.json.gz \
  --dump-frame 2053
```

`replay` 可以是事件文件，也可以是只有一个 `diagnostic_events.json` 或 `.json.gz` 的目录。facts 会优先从事件目录/上级目录查找；M70 归档也会通过 manifest 的 source 路径查找。路径有歧义时明确报错，不会自动挑选其他地图或阶段。支持 `.json` 与 `.json.gz`。

非 TTY 模式：

- `--dump-frame FRAME`：输出重建到该帧后的静态文本帧。
- `--timeline`：输出关键事件紧凑时间线；`--max-events N` 可限制输出。
- 非 TTY 且未带上述参数时返回 2，不会挂住 CI。
- 交互启动默认从第 0 帧开始，播放速度默认 `0.25x`。

## 终端键位

- 空格：暂停/继续；`n`：下一事件；`N`：下一关键事件；`s`：回退到上一关键事件。
- 左/右或 `-`/`+`：速度 `0.25x / 0.5x / 1x / 2x / 4x`。
- `g`：跳转帧；`0`：回到开头；`Tab`：切换选中单位。
- `/`：按真实 ID 过滤；`c`：清除过滤；`f`：切换关键/完整事件流。
- `1`：首干员死亡；`2`：首漏；`3`：下一个炮兵/固定弹事件；`k`：下一个炮兵击杀；`4`：下一个保护到达/装置破坏；`5`：选中单位下一次索敌、锁定或受击。
- `h`：帮助；`l`：低动画；`a`：ASCII；`q`：退出。

命令行还支持 `--jump-frame`、`--no-color`、`--ascii` 和 `--low-motion`。

## 图例与语义

- 地图坐标显示为 `col,row`，每格使用 5 字符宽度。facts 中 `*_col_row` 数组、DEPLOY details 文本和 locked position 按 `[col,row]`；plan/action snapshot 的 `[row,col]` 需要另外转换。
- `.` 是路线 waypoint；`+` 是可部署地面；`^` 是可部署高台；`#` 是装置/路障。
- 干员显示“ID 后缀首字母 + 冲突序号”，例如 Fang 是 `F`，同首字母的 Friston 是 `F1`。
- 已知敌人格显示数量：`E1` 普通敌人，`A1` 炮兵，`K1` 实例号 `#34` 的关键怪。若多个敌人叠在同一已知格，数字是该格总数。
- `@` 选中单位、`R` 在途风险、`!` 最近实际受击。
- `?` 是施法/目标点证据，不等同于弹体已锁定。
- `X` 是 `locked_position` 固定落点；`*` 是按 `radius` 和运行时平面欧氏距离画的在途覆盖提示；`R` 是已知位置干员进入风险范围。
- `o` 是无固定落点的跟踪弹。固定点与跟踪弹在侧栏分别显示 `LOCKED_POINT` 和 `TRACKING`。
- `TARGET_SELECTION` 只显示为索敌，不显示为攻击承诺或必命中。
- 固定落点在目标撤退后继续显示；后续部署进入半径只显示 `IN_FLIGHT_RISK`，只有 `ENEMY_ABILITY_HIT`/DAMAGE 才记录实际伤害。

关键事件流默认折叠普通小怪连续伤害和普通跟踪弹；`f` 可展开完整事件。

## 已知边界

- 第一版不重建敌人连续轨迹。SPAWN 后默认位置是 `UNKNOWN`；只有 BLOCK/UNBLOCK 事件给出确定位置变化。因此敌人数量只统计已知位置的敌人，不会把未知位置硬塞进格子里。缺失值显示 `?`，不用 0 或直线插值冒充原始事实。
- 生命、敌人 HP、未发出的 DP、地图/facts 缺失时显示 `?` 或 UNKNOWN。
- 回放依赖当前归档的诊断事件和 facts。若旧归档缺少字段，会降级为事件准确状态动画；不会为视觉效果虚构轨迹、锁点、取消或打空。
- 风险范围使用固定弹 `locked_position`、`radius` 和运行时 `col,row` 的欧氏距离。它只是几何提示，不能代替实际命中事件。
- 演示使用 M70/M76 已归档事件；本工具不评价新战术 WIN，也不宣称实机、faithful、robust 或概率结论。
