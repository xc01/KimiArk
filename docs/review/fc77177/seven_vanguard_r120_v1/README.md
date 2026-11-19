# R120 其他先锋确定性对照

从已独立复验R119香草29/4出发，翎羽/夜刀各一版，模型0、CLI0、check2、PASS候选2、完整模拟2，未独立复验。翎羽14/19、夜刀20/13，均无新最佳。

入口：RESULT_TO_COPY.txt简短交付；closeout_v1.md详细结项；comparison_v1.json机器结果；key_event_index_v1.json原始事件索引；parent_identity.json与sealed_ledger_hashes.json原件/旧账本；derived/两版精确输入及自然DP联动；session/原生产检查和全战斗。

experiment.py是本次实际执行程序，禁止重跑prepare/execute续开已结束任务。finalize.py只解析核验，不战斗。archive_batch.py / verify_archive.py仅无损归档核验。大型原始JSON以gzip存储，逻辑路径对应gzip_archive_v1.json；双hash及完整文件索引见artifact_manifest_v1.json。模型/usage不适用，legacy配置名不构成模型来源声明。无推送，旧原件/账本/无关文件/.lock保持。
