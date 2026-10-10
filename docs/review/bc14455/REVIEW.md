# bc14455 独立审查：固定B2前缀诊断

基线bc1445502ce98b1a0c26d04de1652a4e9949d2a7，实际fetch、检出、远端HEAD一致。23482f7已合入上一审查补丁。Work本轮Kimi0次、真实关卡模拟0次，只运行合成测试与静态源/事件核验。

## 预算与可复验范围

REPORTED_BY_PREVIOUS_WORKER：main_08-01总运行4次，其中3次未保存。bc14455在final_status、validation_results、parameters和长期文档明确记录FAIL预算。CONFIRMED_FROM_CODE：可读取1份完整事件，不能独立重建前三次参数、代码版本或结果，不能把它们算作通过验证，也不能补造运行记录。不能将一次保存等同于预算合规。现入口main仍写stage_simulations=1；披露修正为人工后处理，重新运行会覆盖原披露，故冻结现有artifacts并禁止重复调用。无需增设审计平台。

## 原事件账本核实

18条run_manifest基线hash/bytes全部匹配（从基线Git内容核实）；3563事件、7个出生、3个死亡、0漏怪、0干员死亡、6次成功部署、芬6DP收入。三击杀为route-2/1/3在576/691/881；DP条件余额10.3667与旧同窗纠正一致。返回边界time=31.3666666353，round到941，事件最大frame940；这是循环推进后的边界状态，并不是完整执行了941帧所有事件。敌人基础间隔及MELEE引用与固定源一致，干员资格仍为普通1～3星。

这些只能作为旧程序条件执行记录，不能称faithful、WIN或真实战术成功；以下通用缺陷影响其战术解释。

## 确认的公共缺陷与最小修复

### 1. 场地坐标被重复翻转

approximate_real.py::_map_tiles对serialized地图数组row翻转是必要的；_coordinate却把已是场地坐标的路线row再次翻转，_devices同样误翻predefines。固定main_08-01 route-3 start(row1,col1)/end(row1,col9)，按(x=col,y=row)正好对应tile_start/tile_end；旧转换变为[1,5]/[9,5]，终点是HIGHLAND/FLY_ONLY高台。route-6出生(row5,col0)直接映射红门[0,5]，旧映射[0,1]是forbidden；终点(row6,col8)直接映射蓝门[8,6]，旧映射[8,0]是forbidden。独立main_00-01 route-2的源start[8,2]/end[0,3]也匹配红蓝门，旧测试反而锁定翻转后的错误路径。

最小修复：路线/装置使用(col,row)，地图数组保持原翻转；同步0-1源派生测试。真实roadblock场地位置应为[5,3],[9,4],[7,2],[1,2],[3,5]，不是旧[5,3],[9,2],[7,4],[1,4],[3,1]。位置改正不解除真实活跃装置占格规则。

此前Work审查沿用了错误转换，未发现它，必须撤销受影响的位置及路线独立确认结论。历史经济源数值、干员获取与机制描述等独立事实不因此全部失效。受影响的旧计划及模拟结果必须按条件旧模型留存，不能反馈为真实战略失败。

### 2. 高台单位参与普通地面阻挡

simulator.py::_advance_enemies只看block_count与路线过tile中心，没有检查高台。保存的BLOCK887明确source=char_285_medic2，Lancet-2在[6,5]高台阻挡route-4；并非计划要求Friston-3移交。公共阻挡候选排除HIGH_GROUND，限现有普通地面阻挡模型，不扩展空中阻挡等未支持模式。GameData该格heightType=HIGHLAND、passableMask=FLY_ONLY；补充PRTS规则说明常规地面阻挡单位位于高地被视为无法阻挡：https://prts.wiki/w/斯托斯贝塔 （术语说明；特殊空中阻挡不属本次范围）。

### 3. 浮点时钟逐步舍入漂移

run中每步round(state.time+1/30,10)累积负误差，精确3秒动作已超过EPS判断，故原请求0/90/180/510/570/630实际部署0/91/181/511/571/631。修复以整数tick_index*dt派生时间，不改动作。复现合成frame90动作在旧max_time=3秒内未执行，修后正好3秒执行。

### 4. 旧deadline漏WAIT（下一阶段须重建）

search/responsibility_feasibility.py::build_early_threat_model用spawn+distance/speed导出contact/latest帧，不读取route.waits。源route-1三次3秒WAIT、route-2五次4秒WAIT、route-6/7/8各10/19/28秒WAIT；runtime显式执行这些等待。因此旧191/27及768/803等时刻不能视为完整源路线时序。这个缺陷不通过向截止时间随意加常数解决：须使用同一公共路径/等待表示，明确重复经过位置、阻挡与等待的条件。客户端等待/阻挡细节有不足证据时保留UNKNOWN。现阶段旧硬期限停用，禁止猜测修机制求通过。

## 同坐标约定下仍待核对的朝向

CONFIRMED_FROM_CODE：ApproximateRealRangeTransformer复用注明y向下的synthetic旋转，而真实fixture地图是bottom-left；raw前方(0,1)的UP输出y-1、DOWN输出y+1。本次B2关键火力都是LEFT/RIGHT，Friston-3范围只有本格，故不据此另外推断本次击杀变化。下一阶段需做四朝向同坐标静态一致性核对，synthetic自己的约定不应被顺手改动。

## 回归与状态

旧基线两项时钟/高台测试确实FAIL；路线/装置两项也FAIL。最小修复后定向55项PASS；compileall和diff --check PASS。未覆盖所有真实关卡回归，未重新运行main_08-01，也不预测修后B2结果。历史output文件未修改；更正证据在本目录。

当前不是让Kimi再战术修订或马上重跑：旧输入空间/时序必须先纠正。唯一下一里程碑见NEXT_MILESTONE：七条开局路线的公共源事实重建和静态一致性校验，Kimi0、真实关卡模拟0。不要补完所有机制或扩展搜索。
