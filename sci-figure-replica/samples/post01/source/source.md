---
title: 期刊配图：基于SHAP的特征驱动机制条形图、蜂群图与环形贡献配图形式
account: Python机器学习AI
author: deep
publish_time: 2026-08-17 16:28:18
url: https://mp.weixin.qq.com/s/Shi2jsgSzbf4nYQEHhjhog
source_html: article_raw.html
---
✨ 欢迎关注Python机器学习AI ✨
本节介绍：基于SHAP的特征驱动机制条形图、蜂群图与环形贡献配图形式，数据采用模拟数据无任何现实意义，作者根据个人对机器学习的理解进行代码实现与图表输出，仅供参考。完整数据和代码稍后上传。需要的朋友可关注公众文末提供的获取方式。点赞、推荐、转发参与文末包邮赠书~！

✨ 相关信息 ✨

文献配图属于是基于SHAP的模型可解释性分析图组，把特征的重要性、影响方向和分布情况集中展示出来。左侧条形图用于说明各特征对模型预测的整体贡献大小，旁边的小圆图则是环形/极坐标式贡献图，同样用于呈现特征贡献及其相对占比；中间的蜂群图进一步展示特征值高低对预测结果的正负影响方向；右侧环形图则把特征贡献以更直观的比例分布方式呈现，便于快速比较不同特征的驱动作用。这组图的作用是把“黑箱”模型解释清楚，不仅告诉读者模型预测结果，还能看出哪些特征在起主导作用、作用方向如何，以及不同特征之间的贡献差异

这是基于开源数据实现的模型解释结果，文献配图其中第三图与第一图中的环形贡献图表达的是同一层含义，都是展示特征贡献及其相对占比，只是采用了不同的可视化形式，解释内容本身并没有改变

第三图原本基于SHAP特征重要性排序，也可以替换为模型自身的特征排名；当两者排序较为一致时，可相互印证特征的驱动作用。一般情况下，两类排序差异不会太大，但由于SHAP解释的是特征对预测结果的边际贡献，而模型自身排名更多反映算法内部的重要性度量，二者在原理上存在差异，因此在某些情况下也可能出现较明显的排序偏离
✨ 基础代码 ✨

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
# 忽略所有警告
warnings.filterwarnings("ignore")

path = r"2026-8-17公众号Python机器学习AI.xlsx"
df = pd.read_excel(path)

from sklearn.model_selection import train_test_split
# 划分特征和目标变量
X = df.drop(['SR'], axis=1)
y = df['SR']

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X,  y,  test_size=0.3,  random_state=42)

from xgboost import XGBRegressor
from sklearn.model_selection import GridSearchCV

# 初始化 XGBoost 回归模型
model_xgb = XGBRegressor(use_label_encoder=False, eval_metric='rmse', random_state=42)

# 定义参数网格
param_grid_xgb = {
    'n_estimators': [50, 100, 200],       # 树的数量
    'learning_rate': [0.01, 0.1, 0.2],    # 学习率
    'max_depth': [3, 5, 10],              # 最大深度
    'subsample': [0.8, 1.0],              # 子采样比率
    'colsample_bytree': [0.8, 1.0]        # 树的列采样比率
}

# 使用 GridSearchCV 进行网格搜索和 k 折交叉验证
grid_search_xgb = GridSearchCV(
    estimator=model_xgb,
    param_grid=param_grid_xgb,
    scoring='neg_root_mean_squared_error',  # 评价指标为负均方根误差
    cv=5,                                  # 5 折交叉验证
    n_jobs=-1,                             # 并行计算
    verbose=1                              # 输出详细进度信息
)

# 训练模型
grid_search_xgb.fit(X_train, y_train)

# 使用最优参数训练模型
best_model_xgb = grid_search_xgb.best_estimator_

import shap
explainer = shap.TreeExplainer(best_model_xgb)
shap_values = explainer.shap_values(X_test)

plot_shap_summary_with_ratio(
    shap_values=shap_values,        # SHAP 值矩阵
    X=X_test,                            # 特征数据
    feature_names=X_test.columns,         # 特征名列表
    percentages=percentages,        # 各特征占比
    ratio_scale=1.5,                # 右下角占比图整体缩放

    ratio_pos=(0.15, 0.18),         # 右下角占比图位置 (left, bottom)
    ratio_label_offset=0.5,         # 百分比标签与柱子的距离
    ratio_label_size=10,            # 百分比标签字号
    ratio_label_color="black",      # 百分比标签颜色

    pdf_path="shap_plot.png",
    pdf_save_kwargs={               # PDF 保存额外参数
        "bbox_inches": "tight"
    }
)
```

在开源数据上用XGBoost回归模型训练后，结合SHAP输出特征重要性条形图和环形贡献图，用来解释SR的主要驱动因素及其贡献大小；文献里用的是LightGBM和CatBoost，但这类机器学习回归解释框架并不固定，核心套路是“先训练模型，再对最优模型做SHAP解释”，所以换成我这里的XGBoost也同样成立
这个SHAP结果可以理解为“模型在预测SR时最依赖哪些变量”。从图上看，VSS/TSS的影响最大，贡献占比大约52.5%，远高于其他特征，说明模型几乎主要靠它来判断SR；其次是ana-time、infS、pH、MLSS、infP，它们属于第二梯队；而T和volumn的影响最小，说明对模型预测帮助不大。图主要反映的是重要性大小，不是“变量升高一定让SR变大或变小”的方向关系；如果想看方向，需要再看蜂巢图或者依赖图

```javascript
plot_shap_beeswarm(
    shap_values=shap_values,
    X=X_test,
    feature_names=X_test.columns,
    cmap_colors=("#2f84b1", "#eaf6fb", "#ffffff", "#f6b08a", "#c40035"),
    save_path="shap_beeswarm.png",
    figsize=(10, 6)
)
```

把shap_values画成SHAP蜂群图，用来展示每个特征在不同样本中的影响大小、正负方向以及特征值高低与模型输出之间的关系，这个可视化可以和上面的图共用同一套y轴特征排序和颜色映射：y轴按特征重要性保持一致，颜色仍表示特征值从低到高，这样就能把“全局重要性”和“各样本中的影响方向与分布”对应起来看

```makefile
importance = np.abs(shap_values).mean(axis=0)
order = np.argsort(importance)[::-1]

feature_names = X_test.columns.to_numpy()[order]
importance = importance[order]
percentages = np.round(importance / importance.sum() * 100, 1)

plot_radial_shap_importance(
    feature_names.tolist(),
    importance.tolist(),
    percentages.tolist(),
    output_path="radial_shap_plot.png",
    cbar_title="|SHAP Value|",
    cmap_colors=("#2f84b1", "#eaf6fb", "#ffffff", "#f6b08a", "#c40035"),
)
```

把每个特征的SHAP绝对值取平均并按重要性排序，再画成环形图，结果说明VSS/TSS贡献最大（52.5%），远高于其他变量，是模型预测SR的核心驱动因素

将上述SHAP重要性环形图、SHAP蜂群图与特征贡献条形图组合展示，可构成论文中的综合可解释性配图，用于直观呈现模型的全局特征重要性、各特征对预测结果的影响方向及其贡献比例

```makefile
importance = best_model_xgb.feature_importances_
feature_names = np.array(X_train.columns)

order = np.argsort(importance)[::-1]
importance = importance[order]
feature_names = feature_names[order]

percentages = np.round(importance / importance.sum() * 100, 1)

fig, ax = plot_radial_shap_importance(
    feature_names.tolist(),
    importance.tolist(),
    percentages.tolist(),
    output_path="radial_xgb_importance.png",
    cbar_title="XGB importance",
)
plt.show()
```

这里直接读取XGBoost模型自带的feature_importances_ 并绘制环形重要性图；它与上面的区别是：上面基于SHAP值衡量特征对预测结果的实际贡献，而这里基于XGBoost内部的重要性指标，更多反映模型分裂过程中各特征被使用和带来增益的情况
如果两种结果一致，说明模型自带重要性和SHAP结果相互印证，特征驱动作用更稳健，这时可以直接采用模型自带的重要性结果作为展示。若两者不完全一致，但整体排名差异不大，则统一采用SHAP结果更合适，SHAP更能反映特征对预测值的实际贡献，也更适合论文中的解释性表达
当然，公众号中还有更多机器学习期刊实战技巧，您可以通过历史文章进行检索和阅读，关注公众号，点击“发信息”>“历史文章”即可搜索公众号所有文章信息

✨ 该文章案例 ✨

在上传的文件中，像往期文章一样，将对案例进行逐步分析，确保读者能够达到最佳的学习效果。内容都经过详细解读，帮助读者深入理解模型的实现过程和数据分析步骤，从而最大化学习成果。
同时，结合提供的免费AI网站进行学习，能够让读者在理论与实践之间实现融会贯通，更加全面地掌握核心概念。
✨ 介绍 ✨
本节内容到此结束。若需要获取本案例的源码及相关资料，可通过公众号后台私信按钮“源码获取”了解相关信息。资料中包含代码、注释、数据说明及参考文献，便于读者进一步学习和复现。合集目前包含近400篇资料。更多内容等你探索~~
更新的内容包含数据、代码、注释和参考资料。作者仅分享案例项目，不提供额外的答疑服务。项目中将提供详细的代码注释和丰富的解读，帮助您理解每个步骤。获取前请咨询，避免不必要的问题。
✨ 淘宝店铺 ✨

请大家打开淘宝，进入“Python机器学习AI”，获取更多Python机器学习和AI相关的内容，希望能为您的学习之路提供帮助！
✨ 赠书活动 ✨

支持知识分享，畅享学习乐趣！特别感谢清华大学出版社对本次赠书活动的鼎力支持！即日起，只需点赞、推荐、转发此文章，作者将从后台随机抽取一位幸运儿，免费包邮赠送清华出版社提供的《AI编程入门工具、方法与实践》这本精彩书籍📚！
💡 赶快参与，一键三连，说不定你就是那位幸运读者哦！
✨ 反馈 ✨

如果你对类似于这样的文章感兴趣。
欢迎关注、点赞、转发~
个人观点，仅供参考
