# 1223c03 独立审查

实际fetch、检出及远端HEAD一致：1223c031eda86df648754c36e94c1373219c0632。a207aad已合入上一审查补丁。基线11条manifest hash/bytes全部匹配；实际恢复固定GameData源，main_08-01 level SHA-256为8819c9cab57bd85005416d6262f9d52d07237c9b2a1a044d0ca17f8e408881b6。本轮仅静态fixture构建、源检查及合成回归，真实关卡模拟0、Kimi0、新计划0、新候选0、搜索0。服务器全局预算只能按保存代码/artifacts与worker披露核对，不能凭checkout证明不存在未保存调用。

## 可以确认的进展

CONFIRMED_FROM_CODE：地图数组与场地坐标区分正确，路线端点及五路障源位置一致；MOVE/WAIT保留在公共Route中；新增distances_at能枚举重复经过。真实fixture四朝向改用bottom-left约定，synthetic维持y-down。旧B2六动作没有移动，Friston-3 [8,5]不在新源下路路线，Yato[5,1]反而属于route1/3/4。基本事实纠正确实有进展，但还不是完整运行时导航。

公共折线、源等待、无部署阻挡、model spawn policy下：route1在[8,1]到达461、route3为431、route4为941。它们是条件模型格中心到达值，不是客户端已验证建立硬期限。暂停旧坐标/漏WAIT失败经验仍正确。

## 重复经过尚未接入两个公共消费者（已最小修复）

目录已经记录route2：[3,3]到达147/442，[4,3]到达0/295/589。search/responsibility_feasibility.py::build_early_threat_model仍使用distance_at（首次经过），所以输出latest147@[3,3]；这是模型内部矛盾，不是不同游戏解释。

simulator.py::_advance_enemies也仍使用首次distance_at，干员较晚部署后无法阻挡回到同一格的敌人。两处现在均枚举distances_at，选择当前运动区间/最后机会，不写stage专属数值。两项行为回归旧代码FAIL，修后PASS。静态重建得到route2最后一个公共格中心到达589@[4,3]。这个589也不是部署最晚硬期限：等待同点期间是否能阻挡、实际阻挡半径及客户端导航未证实。未修改WAIT时阻挡优先级或猜测客户端机制。

构建脚本的旧失效说明把191说成route3绝对到达帧，也已修正：191是移动时长，spawn240后才是431。扩充输出limitation防止把旧latest_safe_blocker_frame字段自动硬化。

## 格中心检查不是连续通行验证

固定源和公共直连段内部点的反例：
- route2末段[4,3]→[9,1]在(6,2.2)处落入[6,2] FLY_ONLY，格中心不在路线。
- route6在(4,4)处落入[4,4] FLY_ONLY，目录已标出。
- route7在(6,5.3333)处落入[6,5] FLY_ONLY，格中心不在路线；原目录还记录中心[5,5] FLY_ONLY，worker总结仅突出route6并不完整。
- route8在(4,5.3333)处落入[4,5] FLY_ONLY，格中心不在路线。

这些是当前直连折线与地块通行掩码的矛盾，不是GameData真实路线穿墙。客户端可能导航绕行；尚未恢复导航。原EXACT_TILE_CENTERS_PASSABLE仅证明有限中心查询，不证明连续段可走；route2、route8不能因此放行。

因此route6/7/8“无可部署地面拦截格”仅为当前失效直连模型与精确中心相交集合为空，不能推为真实不可阻挡、没有候选或必须让路。不能将这些结论用于拒绝Kimi战略。实际阻挡半径、路障与导航、corner规则仍需源证据，不能随意套A*或猜机制以过关。

## 验证及下一阶段

原7项新断言复验通过；本轮修后定向64项与静态adapter5项共69项通过，compileall、diff --check通过。静态adapter检查不调用Simulator.run；合成测试不使用真实关卡。历史output artifacts无变更；更正早期模型、连续段反例和源核验另存在本目录。非全量测试/真实游戏确认。

不批准Kimi修订或真实关卡再跑。唯一下一里程碑：以GameData及可核实机制补充，补齐route2/6/7/8的共享WALK导航/通行事实，route3作控制；证据充分才实现公共导航并静态校验，不另建审计层。详NEXT_MILESTONE。若不足，明确列证据缺口和影响，不伪造新精确deadline。
