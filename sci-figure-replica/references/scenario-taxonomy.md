# 场景与标签

assets/scenario_taxonomy.yaml 使用 JSON兼容YAML（标准库可读），是主场景与别名的单一受控词表：主场景规范键、标签和别名以该文件当前内容为准，本说明不复制固定清单或数量。主场景选1–2个规范键；primary 不能为空；不确定先 other 并待作者确认分类。别名帮助agent分类（如"SHAP/特征重要性"→model-explanation-shap，"毒性预测"→chem-informatics-qsar）；传 init_entry --scenario 时使用规范键，不将自由标签混进枚举。

secondary 是补充受控场景，free 用模型名（LightGBM）、方法名、数据集和图型细类；去除首尾空格及重复，保持原名。post01 推荐 primary=model-explanation-shap，secondary=chem-informatics-qsar，free=[LightGBM,CatBoost,feature-importance]，需读图后确认而非在 init 中硬编码样例。

imaging-radiomics 只接纳影像组学统计数据图；分割影像或CAM叠图转合适的医学影像技能，不因标签存在而越界。词表扩展只声明领域词汇，不意味着对应领域已有实现或已验证的方法。

若需新增主场景，同步 taxonomy、metadata schema 与相应用例；索引从元数据动态生成筛选项。自由标签不能取代主场景，也不应自动推断数据的临床有效性。
