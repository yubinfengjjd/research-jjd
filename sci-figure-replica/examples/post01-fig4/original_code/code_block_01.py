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
