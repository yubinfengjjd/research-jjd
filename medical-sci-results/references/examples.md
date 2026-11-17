# 判断示例

以下数据与图号均为虚构。只学习证据组织，不迁移数值、术语、panel 大小写或固定表达。

## 分析组声明与直接发现

> The following sensitivity analyses used one trained model on the held-out test set. Removing the auxiliary score changed sensitivity by −0.02 (95% CI, −0.05 to 0.01), with no clear evidence of a difference (Fig. 2a). Specificity was 0.91 with the score and 0.90 without it (Table 2).
>
> The largest sensitivity loss occurred in the low-quality subgroup (−0.08; 95% CI, −0.13 to −0.03) (Fig. 2b). The corresponding loss was −0.01 in the remaining examinations (95% CI, −0.04 to 0.02).

开头声明支配两段中的同组结果，后句不重复单模型范围。第二段保留重要不利亚组；与第一段不同 panel 的证据仍就近标示。读者可判断该声明指向哪些分析，内部记录映射其位置。若后文换成三模型平均，必须重新声明，不能继承单模型范围。

## 明确的阴性结论

> The analysis did not establish a reduction in readmission. The risk difference was −1.1 percentage points (95% CI, −3.2 to 1.0) (Table 3).

否定句承担实际推断结论，可以保留。区间跨零不是等效证据；若存在事后检验，其事后性质和结果如实报告，不改称 non-inferential。未做检验、没有预设阈值和检验未显著分别核对。

## 分母、例外与极值

> Of 500 examinations with reference class B, 75 were assigned to class A (15.0%) (Fig. 3c). Agreement was lowest in Hospital C (0.74); Hospital D had the next-lowest value (0.76) (Table 4).

15.0% 的分母是真值 B 检查，不是模型预测为 B 的检查。不同值不都称最低，不能省去已知更差队列。

## 图表引用与文本结果

成图 panel 只显示误差，源记录另有经过执行核实的违例计数时，计数可以作为相关文本结果报告，并在数字出处表定位到记录和字段；不能把该计数引到未显示它的 panel。内部 provenance 不能替代读者需要的图表或文献引用。同一关键图表支持不同论点时可复引，不按次数强制合并。

## 描述性定位

> Discrimination was 0.88 at the intermediate representation and 0.72 at the final output in Hospital B (Fig. 4a).

这组量可以支持关于测得差距位置的描述，不能单凭这两个值声称最后一个组件造成全部总体损失。定位须核对完整比较链及例外，因果结论另需适当设计。
