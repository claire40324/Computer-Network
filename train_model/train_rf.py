#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
import matplotlib.pyplot as plt
import joblib

# ====== 設定：改成你 build_features.py 產生的 CSV 檔名 ======
CSV_PATH = "features_no_cond.csv"   # 目前看起來有欄位: algo, run, ss_*, ip_*

# ====== 讀取資料 ======
df = pd.read_csv(CSV_PATH)

print(f"Total samples: {len(df)}")
print(df.head())

# ====== 分拆 train / val / test ======
train_df = df[df["run"].isin([1, 2, 3])].reset_index(drop=True)
val_df   = df[df["run"] == 4].reset_index(drop=True)
test_df  = df[df["run"] == 5].reset_index(drop=True)

print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

# ====== feature 選取（不含 rtt_setting / bw_setting）=====
feature_cols = [
    "ss_rtt_ms",        # ms
    "ss_rtt_var_ms",    # ms
    "ss_cwnd_bytes",    # bytes
    "ss_pacing_mbps",   # Mbps
    "ip_tp_mbps",       # Mbps
    "ip_mean_rtt_ms",   # ms
]

X_train = train_df[feature_cols]
X_val   = val_df[feature_cols]
X_test  = test_df[feature_cols]

# ====== label encoding (algo) ======
le = LabelEncoder()
y_train = le.fit_transform(train_df["algo"])
y_val   = le.transform(val_df["algo"])
y_test  = le.transform(test_df["algo"])

print("Classes:", le.classes_)

# ====== 訓練 Random Forest ======
rf = RandomForestClassifier(
    n_estimators=300,
    max_depth=None,
    n_jobs=-1,
    random_state=42,
)
rf.fit(X_train, y_train)

# ====== 小工具：畫 & 存 confusion matrix ======
def plot_confusion(cm, classes, title, filename):
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    ax.figure.colorbar(im, ax=ax)

    ax.set(
        xticks=np.arange(len(classes)),
        yticks=np.arange(len(classes)),
        xticklabels=classes,
        yticklabels=classes,
        title=title,
        ylabel='True label',
        xlabel='Predicted label',
    )

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right",
             rotation_mode="anchor")

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, format(cm[i, j], 'd'),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black"
            )

    fig.tight_layout()
    plt.savefig(filename, dpi=250)
    plt.close()
    print(f"Saved confusion matrix: {filename}")

# ====== 畫 classification report 表格 ======
def plot_classification_report(report_dict, title, filename_png, filename_csv=None):
    """
    report_dict: classification_report(..., output_dict=True) 的結果
    會畫成一張 table 圖，另外可選擇存成 CSV
    """
    df_rep = pd.DataFrame(report_dict).T

    # 存 CSV（可選）
    if filename_csv is not None:
        df_rep.to_csv(filename_csv)
        print(f"Saved classification report table: {filename_csv}")

    # 畫表格圖
    fig, ax = plt.subplots(figsize=(6, 0.5 * len(df_rep) + 1.5))
    ax.axis('off')

    display_df = df_rep.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].map(
            lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x
        )

    table = ax.table(
        cellText=display_df.values,
        rowLabels=display_df.index,
        colLabels=display_df.columns,
        loc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.3)

    ax.set_title(title, pad=10)
    plt.tight_layout()
    plt.savefig(filename_png, dpi=250)
    plt.close()
    print(f"Saved classification report figure: {filename_png}")


def evaluate_split(name, X, y_true, filename_prefix):
    y_pred = rf.predict(X)
    print(f"\n=== {name} Result ===")

    # 文字版
    report_text = classification_report(y_true, y_pred, target_names=le.classes_)
    print(report_text)

    # dict 版 → 用來畫圖 & 存表
    report_dict = classification_report(
        y_true, y_pred, target_names=le.classes_,
        output_dict=True
    )

    cm = confusion_matrix(y_true, y_pred)
    print("Confusion matrix:\n", cm)

    # 畫 confusion matrix
    plot_confusion(
        cm, le.classes_,
        f"{name} Confusion Matrix",
        f"{filename_prefix}_cm.png"
    )

    # 畫 classification report table + 存 CSV
    plot_classification_report(
        report_dict,
        f"{name} Classification Report",
        f"{filename_prefix}_report.png",
        f"{filename_prefix}_report.csv"
    )

    return y_pred

# ====== 驗證：Run 4 & Run 5 ======
y_val_pred  = evaluate_split("VALIDATION (Run 4)", X_val,  y_val,  "val_run4")
y_test_pred = evaluate_split("TEST (Run 5)",       X_test, y_test, "test_run5")

# ====== 輸出預測結果表格 ======
val_out = val_df.copy()
val_out["pred_algo"] = le.inverse_transform(y_val_pred)
#val_out.to_csv("rf_val_predictions.csv", index=False)

test_out = test_df.copy()
test_out["pred_algo"] = le.inverse_transform(y_test_pred)
#test_out.to_csv("rf_test_predictions.csv", index=False)

print("\nSaved CSV:")
print("  rf_val_predictions.csv")
print("  rf_test_predictions.csv")

# ====== 顯示 + 畫 feature importance ======
importances = rf.feature_importances_
fi_pairs = list(zip(feature_cols, importances))
fi_pairs.sort(key=lambda x: x[1], reverse=True)

print("\n=== Feature Importance ===")
for name, score in fi_pairs:
    print(f"{name:20s} : {score:.4f}")

sorted_features = [x[0] for x in fi_pairs]
sorted_scores   = [x[1] for x in fi_pairs]

plt.figure(figsize=(7, 4.5))
y_pos = np.arange(len(sorted_features))
plt.barh(y_pos, sorted_scores)
plt.yticks(y_pos, sorted_features)
plt.gca().invert_yaxis()  # 重要的在上面
plt.xlabel("Feature importance")
plt.title("Random Forest Feature Importance")
plt.tight_layout()
plt.savefig("rf_feature_importance.png", dpi=250)
plt.close()
print("Saved feature importance: rf_feature_importance.png")

# ====== 存 model ======
bundle = {
    "model": rf,
    "label_encoder": le,
    "feature_cols": feature_cols,
}
joblib.dump(bundle, "rf_congctrl.pkl")
print("Saved model to rf_congctrl.pkl")
