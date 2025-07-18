import os
import cv2
import dlib
import json
import hashlib
import subprocess
import numpy as np

# === CONFIG ===
IMAGE_PATH = "/home/biometric/1/person3.jpeg"
UNCONFIRMED_DIR = "unconfirmed_vectors"
os.makedirs(UNCONFIRMED_DIR, exist_ok=True)

# === Blockchain config ===
FABRIC_DIR = "/home/biometric/1/fabric-samples"
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"

# === Environment setup ===
os.environ.update({
    "PATH": os.environ["PATH"] + os.pathsep + f"{FABRIC_DIR}/bin",
    "FABRIC_CFG_PATH": f"{FABRIC_DIR}/config",
    "CORE_PEER_TLS_ENABLED": "true",
    "CORE_PEER_LOCALMSPID": "Org1MSP",
    "CORE_PEER_TLS_ROOTCERT_FILE": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt",
    "CORE_PEER_MSPCONFIGPATH": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp",
    "CORE_PEER_ADDRESS": "localhost:7051"
})

# === Dlib model loading ===
print("📦 Loading models...")
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("/home/biometric/1/notebooks/shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("/home/biometric/1/notebooks/dlib_face_recognition_resnet_model_v1.dat")

# === Load image and extract vector ===
print("🖼 Reading image...")
image = cv2.imread(IMAGE_PATH)
if image is None:
    print("❌ Could not read image.")
    exit(1)

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
faces = detector(gray, 1)
if len(faces) == 0:
    print("❌ No face detected.")
    exit(1)

shape = predictor(gray, faces[0])
vector = list(face_rec_model.compute_face_descriptor(image, shape))

# === Hash the vector using SHA-256 ===
vector_json = json.dumps(vector)
vector_bytes = vector_json.encode("utf-8")
vector_hash = hashlib.sha256(vector_bytes).hexdigest()
print(f"🔐 Vector SHA-256 Hash: {vector_hash}")

# === Check if hash exists on blockchain ===
print("🔍 Checking blockchain for duplicate hash...")
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
    print("❌ Duplicate face already registered on blockchain.")
    print(result.stdout)
    exit(0)

# === Emit RegisterHash event to blockchain ===
print("📡 Emitting RegisterHash event to blockchain...")
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
        "Args": [vector_hash, vector_json]  # ✅ Send 2 args: hash and vector
    })
]

result = subprocess.run(register_cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("❌ Failed to register hash on blockchain.")
    print(result.stderr)
    exit(1)

print("✅ RegisterHash event emitted successfully.")

# === Save vector to unconfirmed_vectors/<hash>.json for listener ===
vector_path = os.path.join(UNCONFIRMED_DIR, f"{vector_hash}.json")
with open(vector_path, "w") as f:
    json.dump({"hash": vector_hash, "vector": vector}, f, indent=2)

print(f"📥 Vector saved locally for listener: {vector_path}")
