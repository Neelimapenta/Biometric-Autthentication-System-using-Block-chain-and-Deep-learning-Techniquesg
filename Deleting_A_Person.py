import os
import cv2
import dlib
import json
import hashlib
import subprocess

# === CONFIG ===
IMAGE_PATH = "/home/biometric/1/person5.jpeg"
FABRIC_DIR = "/home/biometric/1/fabric-samples"
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"

# === Fabric ENV ===
os.environ.update({
    "PATH": os.environ["PATH"] + os.pathsep + f"{FABRIC_DIR}/bin",
    "FABRIC_CFG_PATH": f"{FABRIC_DIR}/config",
    "CORE_PEER_TLS_ENABLED": "true",
    "CORE_PEER_LOCALMSPID": "Org1MSP",
    "CORE_PEER_TLS_ROOTCERT_FILE": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt",
    "CORE_PEER_MSPCONFIGPATH": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp",
    "CORE_PEER_ADDRESS": "localhost:7051"
})

# === Load Dlib Models ===
print("📦 Loading Dlib models...")
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("/home/biometric/1/notebooks/shape_predictor_68_face_landmarks.dat")
face_rec_model = dlib.face_recognition_model_v1("/home/biometric/1/notebooks/dlib_face_recognition_resnet_model_v1.dat")

# === Read Image and Extract Vector ===
print("🖼 Reading image...")
image = cv2.imread(IMAGE_PATH)
if image is None:
    print("❌ Could not load image.")
    exit()

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
faces = detector(gray, 1)
if len(faces) == 0:
    print("❌ No face detected.")
    exit()

shape = predictor(gray, faces[0])
vector = list(face_rec_model.compute_face_descriptor(image, shape))

# === Compute Vector Hash ===
vector_bytes = json.dumps(vector).encode("utf-8")
vector_hash = hashlib.sha256(vector_bytes).hexdigest()
print(f"🔐 Face vector hash: {vector_hash}")

# === Check if Record Exists on Blockchain ===
print("🔍 Checking if record exists on blockchain...")
query_cmd = [
    "peer", "chaincode", "query",
    "-C", CHANNEL_NAME,
    "-n", CHAINCODE_NAME,
    "-c", json.dumps({
        "function": "ReadCIDRecord",
        "Args": [vector_hash]
    })
]
query_result = subprocess.run(query_cmd, capture_output=True, text=True)
if "does not exist" in query_result.stdout or query_result.returncode != 0:
    print("⚠ Record does not exist on blockchain.")
    exit()

print("✅ Record exists. Proceeding with deletion...")

# === Delete Record from Blockchain ===
delete_cmd = [
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
        "function": "DeleteCIDRecord",
        "Args": [vector_hash]
    })
]

result = subprocess.run(delete_cmd, capture_output=True, text=True)
if result.returncode == 0:
    print("🗑 Deleted face vector record successfully from blockchain.")
else:
    print("❌ Failed to delete face record.")
    print(result.stderr)
