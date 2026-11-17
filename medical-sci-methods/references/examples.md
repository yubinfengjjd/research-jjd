# 判断示例

以下均为虚构材料及数据，只说明决策方式。正式写作须回到本项目证据，不迁移示例数值、对象或固定句式。

## 先交代问题，再写实际操作

> We evaluated whether the score retained its calibration after transfer to another hospital. A logistic recalibration model was fitted in the external calibration partition and evaluated in a separate test partition. Uncertainty was estimated by resampling patients, keeping all examinations from each patient together.

目的、拟合/评估分区及重采样单位都来自实际调用；第三句不再重复第一句的医院范围。若实际是在同一分区拟合和评估，必须写明同集关系，不能照搬本例的独立评估。

## 分母与单位

> We first reserved 20% of participants for testing, then selected 25% of the remaining participants for validation. The evaluable annotation set comprised 180 image–region pairs from 60 images.

先后比例分别对应其真实分母；180 不改写为图像数。样本数、单位和步骤不能为精简而混在一起。

## 未完成分析与写作范围

内部备选的可选访谈未承诺、未执行且不影响结论，可以留在过程记录。注册或正文承诺的读者研究未完成时，须公开披露缺失及其对相应结论的影响，不能只删除执行状态句，也不能让核查说明代替必要公开信息。探索性状态只限定实际事后分析；若一组分析共享该状态，可准确统一声明。

大纲想突出双信号分析，而运行回执显示已报告结果用了三信号时，写作重点只能决定是否纳入这项分析，不能授权写成双信号。先核实图表与执行范围；冲突影响核心方法时记录并解决受影响部分，其余独立编辑继续。

## 实现记录与科学事实

哈希排序的代码细节通常留在过程文件，但若其结果是预测独立的确定性抽样，应保留这一设计事实。代码具备某功能不证明运行过；实际调用与回执支持“已执行”。transport 若指真实的可迁移性问题可用，不能统一改成 recalibration。

## 中文对应

> 阈值在验证分区确定后应用于测试分区。采用患者层面的重采样，同一患者的全部检查始终归为一组。

中文按学术语序重组；保留数据角色和分析单位，不因英文拆成三句而要求中文句数相同。
