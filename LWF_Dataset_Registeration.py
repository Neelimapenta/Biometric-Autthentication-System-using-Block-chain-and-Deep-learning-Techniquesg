import os
import cv2
import dlib
import json
import hashlib
import subprocess
import numpy as np
from sklearn.datasets import fetch_lfw_people
from tqdm import tqdm

# === CONFIG ===
UNCONFIRMED_DIR = "unconfirmed_vectors"
FABRIC_DIR = "/home/biometric/1/fabric-samples"
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"

# === Fabric environment ===
os.environ.update({
    "PATH": os.environ["PATH"] + os.pathsep + f"{FABRIC_DIR}/bin",
    "FABRIC_CFG_PATH": f"{FABRIC_DIR}/config",
    "CORE_PEER_TLS_ENABLED": "true",
    "CORE_PEER_LOCALMSPID": "Org1MSP",
    "CORE_PEER_TLS_ROOTCERT_FILE": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt",
    "CORE_PEER_MSPCONFIGPATH": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp",
    "CORE_PEER_ADDRESS": "localhost:7051"
})
os.makedirs(UNCONFIRMED_DIR, exist_ok=True)

# === Dlib models ===
print("📦 Loading models...")
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("/home/biometric/1/notebooks/shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("/home/biometric/1/notebooks/dlib_face_recognition_resnet_model_v1.dat")

# === Load LFW dataset ===
print("📥 Loading LFW...")
lfw = fetch_lfw_people(min_faces_per_person=10, color=True, resize=1.0, funneled=True)

images = lfw.images
labels = lfw.target
label_names = lfw.target_names

print("🔐 Registering all LFW vectors to IPFS + Blockchain...")

# === Extract and register face vectors ===
def extract_vector(img):
    if img.dtype != np.uint8:
        img = (img * 255).astype(np.uint8)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.shape[-1] == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    img_resized = cv2.resize(img_rgb, (150, 150))  # Resize consistently
    dets = detector(img_resized, 1)
    if len(dets) == 0:
        return None
    shape = predictor(img_resized, dets[0])
    vec = face_rec_model.compute_face_descriptor(img_resized, shape)
    return list(vec)

for i in tqdm(range(len(images))):
    vec = extract_vector(images[i])
    if vec is None:
        continue

    label = int(labels[i])
    vector_json = json.dumps({"vector": vec, "label": label})
    vector_hash = hashlib.sha256(vector_json.encode("utf-8")).hexdigest()

    # Check if already registered
    check_cmd = [
        "peer", "chaincode", "query",
        "-C", CHANNEL_NAME,
        "-n", CHAINCODE_NAME,
        "-c", json.dumps({
            "function": "GetCID",
            "Args": [vector_hash]
        })
    ]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    if "CID" in result.stdout:
        continue  # Already registered

    # Emit RegisterHash event
    register_cmd = [
        "peer", "chaincode", "invoke",
        "-o", "localhost:7050",
        "--ordererTLSHostnameOverride", "orderer.example.com",
        "--tls",
        "--cafile", f"{FABRIC_DIR}/test-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem",
        "-C", CHANNEL_NAME,
        "-n", CHAINCODE_NAME,
        "--peerAddresses", "localhost:7051",
        "--tlsRootCertFiles", os.environ["CORE_PEER_TLS_ROOTCERT_FILE"],
        "--peerAddresses", "localhost:9051",
        "--tlsRootCertFiles", f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt",
        "-c", json.dumps({
            "function": "RegisterHash",
            "Args": [vector_hash, vector_json]
        })
    ]
    result = subprocess.run(register_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Blockchain error: {result.stderr}")
        continue

    # Save vector for listener
    with open(f"{UNCONFIRMED_DIR}/{vector_hash}.json", "w") as f:
        json.dump({"hash": vector_hash, "vector": vec, "label": label}, f)
