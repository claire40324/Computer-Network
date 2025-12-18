#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import matplotlib.pyplot as plt

TEST_CSV = "features_no_cond_test.csv"

# 讀 test feature
df_test = pd.read_csv(TEST_CSV)
print("Test samples:", len(df_test))
print(df_test.head())

# 載入之前訓練好的模型
bundle = joblib.load("rf_congctrl.pkl")

rf = bundle["model"]
le = bundle["label_encoder"]
feature_cols = bundle["feature_cols"]

print("Loaded model, encoder, and features from rf_congctrl.pkl")

X_test = df_test[feature_cols]
y_true = le.transform(df_test["algo"])   # 檔名裡的 algo 就是 ground truth

# 做預測
y_pred = rf.predict(X_test)

print("\n=== TEST on NEW RTT/BW ===")
print(classification_report(y_true, y_pred, target_names=le.classes_))

cm = confusion_matrix(y_true, y_pred)
print("Confusion matrix:\n", cm)

# ========================
# 1) 畫 Confusion Matrix 圖
# ========================
def plot_confusion(cm, classes, filename):
    fig, ax = plt.subplots(figsize=(4, 4), dpi=150)
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    ax.figure.colorbar(im, ax=ax)

    ax.set(
        xticks=np.arange(len(classes)),
        yticks=np.arange(len(classes)),
        xticklabels=classes,
        yticklabels=classes,
        xlabel='Predicted',
        ylabel='True',
        title='Confusion Matrix (New RTT/BW)'
    )

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, format(cm[i, j], "d"),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black",
            )

    fig.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"Saved confusion matrix figure: {filename}")

plot_confusion(cm, le.classes_, "cm_new_rtt_bw.png")

# ============================
# 2) 畫 classification metrics 表
# ============================

# 取得 classification_report 的 dict
report_dict = classification_report(
    y_true, y_pred,
    target_names=le.classes_,
    output_dict=True
)

# 轉成 DataFrame（包含 accuracy / macro avg / weighted avg）
df_report = pd.DataFrame(report_dict).transpose()

# 四捨五入讓看起來比較乾淨
df_show = df_report.round(2)

# 印在 terminal 給自己確認
print("\n=== NEW RTT/BW TEST METRICS TABLE ===\n")
print(df_show)

# 視覺化成圖片 Table
fig, ax = plt.subplots(figsize=(8, 4))  # 放大一點比較清楚
ax.axis('tight')
ax.axis('off')

table = ax.table(
    cellText=df_show.values,
    colLabels=df_show.columns,
    rowLabels=df_show.index,
    cellLoc='center',
    loc='center'
)

table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.2, 1.6)

plt.title("Performance on NEW RTT/BW Testset (No RTT/BW Features)")
plt.tight_layout()

out_file = "test_new_rttbw_metrics_table.png"
plt.savefig(out_file, dpi=250)
plt.close()

print(f"\nSaved metrics table figure: {out_file}")
