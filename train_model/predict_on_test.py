#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import matplotlib.pyplot as plt

TEST_CSV = "features_no_cond_test.csv"

# Load test features
df_test = pd.read_csv(TEST_CSV)
print("Test samples:", len(df_test))
print(df_test.head())

# Load the previously trained model bundle
bundle = joblib.load("rf_congctrl.pkl")

rf = bundle["model"]
le = bundle["label_encoder"]
feature_cols = bundle["feature_cols"]

print("Loaded model, encoder, and features from rf_congctrl.pkl")

X_test = df_test[feature_cols]
y_true = le.transform(df_test["algo"])   # Algorithm from filename is the ground truth

# Run prediction
y_pred = rf.predict(X_test)

print("\n=== TEST on NEW RTT/BW ===")
print(classification_report(y_true, y_pred, target_names=le.classes_))

cm = confusion_matrix(y_true, y_pred)
print("Confusion matrix:\n", cm)

# ========================
# 1) Plot Confusion Matrix
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
# 2) Plot classification metrics table
# ============================

# Get classification_report as a dictionary
report_dict = classification_report(
    y_true, y_pred,
    target_names=le.classes_,
    output_dict=True
)

# Convert to DataFrame (includes accuracy / macro avg / weighted avg)
df_report = pd.DataFrame(report_dict).transpose()

# Round values for cleaner display
df_show = df_report.round(2)

# Print to terminal for quick inspection
print("\n=== NEW RTT/BW TEST METRICS TABLE ===\n")
print(df_show)

# Visualize metrics as a table image
fig, ax = plt.subplots(figsize=(8, 4))  # Increase size for readability
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

