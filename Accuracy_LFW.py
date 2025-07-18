import json
import subprocess
import ipfshttpclient
import numpy as np
import faiss
from tqdm import tqdm
from sklearn import metrics
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import os

# === CONFIG ===
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"
PLOT_DIR = "evaluation_plots"
os.makedirs(PLOT_DIR, exist_ok=True)

# === IPFS Connection ===
ipfs = ipfshttpclient.connect("/ip4/127.0.0.1/tcp/5001")

# === Load vectors from blockchain/IPFS ===
def load_vectors():
    print("📥 Downloading vectors from IPFS via blockchain records...")

    result = subprocess.run([
        "peer", "chaincode", "query",
        "-C", CHANNEL_NAME,
        "-n", CHAINCODE_NAME,
        "-c", json.dumps({
            "function": "GetAllCIDRecords",
            "Args": []
        })
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ Blockchain query failed:", result.stderr)
        return [], []

    try:
        cid_records = json.loads(result.stdout)
    except Exception as e:
        print("❌ Failed to parse CID records:", e)
        return [], []

    vectors, labels = [], []
    for record in tqdm(cid_records):
        try:
            cid = record["cid"]
            data = ipfs.cat(cid)
            obj = json.loads(data.decode("utf-8"))

            vector = obj["vector"]
            label = obj.get("label", None)
            if label is not None and len(vector) == 128:
                vectors.append(np.array(vector, dtype=np.float32))
                labels.append(label)
        except Exception as e:
            print(f"⚠ Failed for {record.get('id')}: {e}")

    return vectors, labels

# === Evaluation ===
def evaluate():
    vectors, labels = load_vectors()
    if len(vectors) == 0:
        print("❌ No valid vectors found.")
        return

    print(f"🔢 Loaded {len(vectors)} vectors")
    sims, y_true = [], []

    print("🔍 Computing pairwise similarity...")
    for i in tqdm(range(len(vectors))):
        for j in range(i + 1, len(vectors)):
            sim = 1 - np.linalg.norm(vectors[i] - vectors[j])**2 / 4
            sims.append(sim)
            y_true.append(1 if labels[i] == labels[j] else 0)

    y_scores = np.array(sims)
    y_true = np.array(y_true)

    # === ROC, AUC ===
    fpr, tpr, thresholds = metrics.roc_curve(y_true, y_scores)
    auc = metrics.auc(fpr, tpr)

    # === EER Calculation ===
    fnr = 1 - tpr
    eer_index = np.nanargmin(np.abs(fnr - fpr))
    eer = (fpr[eer_index] + fnr[eer_index]) / 2
    eer_threshold = thresholds[eer_index]

    # === Final Prediction ===
    y_pred = [1 if s >= eer_threshold else 0 for s in y_scores]

    acc = metrics.accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    far = fp / (fp + tn) if (fp + tn) else 0
    frr = fn / (fn + tp) if (fn + tp) else 0

    print("\n🎯 Evaluation Metrics:")
    print(f"Accuracy: {acc * 100:.2f}%")
    print(f"AUC: {auc:.4f}")
    print(f"EER: {eer:.4f} (at threshold {eer_threshold:.4f})")
    print(f"FAR: {far:.4f}")
    print(f"FRR: {frr:.4f}")
    print("Confusion Matrix:")
    print(cm)

    # === ROC Curve Plot ===
    plt.figure()
    plt.plot(fpr, tpr, label=f"AUC = {auc:.4f}")
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend(loc="lower right")
    plt.grid()
    plt.savefig(os.path.join(PLOT_DIR, "roc_curve.png"))
    plt.close()

    # === Accuracy vs Threshold Plot ===
    accs = []
    for th in thresholds:
        preds = [1 if s >= th else 0 for s in y_scores]
        accs.append(metrics.accuracy_score(y_true, preds))

    plt.figure()
    plt.plot(thresholds, accs, color='blue')
    plt.axvline(x=eer_threshold, color='red', linestyle='--', label=f"EER @ {eer_threshold:.4f}")
    plt.xlabel("Threshold")
    plt.ylabel("Accuracy")
    plt.title("Accuracy vs Threshold")
    plt.grid()
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, "accuracy_threshold.png"))
    plt.close()

    # === Confusion Matrix Heatmap ===
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['Pred 0', 'Pred 1'], yticklabels=['True 0', 'True 1'])
    plt.title("Confusion Matrix")
    plt.savefig(os.path.join(PLOT_DIR, "confusion_matrix_heatmap.png"))
    plt.close()

    print(f"\n📊 Graphs saved in ./{PLOT_DIR}/")

if _name_ == "_main_":
    evaluate()
