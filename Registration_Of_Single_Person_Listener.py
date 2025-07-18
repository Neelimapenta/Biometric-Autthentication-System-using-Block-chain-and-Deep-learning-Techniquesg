import os
import json
import time
import subprocess

# === CONFIG ===
UNCONFIRMED_DIR = "unconfirmed_vectors"
PROCESSED_DIR = "processed_vectors"
POLL_INTERVAL = 5  # seconds

FABRIC_DIR = "/home/biometric/1/fabric-samples"
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"
ORDERER_CA = f"{FABRIC_DIR}/test-network/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

# === Setup Fabric environment ===
os.environ.update({
    "PATH": os.environ["PATH"] + os.pathsep + f"{FABRIC_DIR}/bin",
    "FABRIC_CFG_PATH": f"{FABRIC_DIR}/config",
    "CORE_PEER_TLS_ENABLED": "true",
    "CORE_PEER_LOCALMSPID": "Org1MSP",
    "CORE_PEER_TLS_ROOTCERT_FILE": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt",
    "CORE_PEER_MSPCONFIGPATH": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp",
    "CORE_PEER_ADDRESS": "localhost:7051"
})

# === Ensure directories exist ===
os.makedirs(UNCONFIRMED_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# === Upload vector to IPFS ===
def upload_to_ipfs(file_path):
    try:
        result = subprocess.run(["ipfs", "add", "-Q", file_path], capture_output=True, text=True, check=True)
        cid = result.stdout.strip()
        print(f"🌀 Uploaded to IPFS: {cid}")
        return cid
    except subprocess.CalledProcessError as e:
        print("❌ IPFS upload failed:", e.stderr)
        return None

# === Confirm vector hash and CID on blockchain ===
def confirm_on_blockchain(vector_hash, cid):
    print(f"🔗 Confirming on blockchain: {vector_hash} → {cid}")
    cmd = [
        "peer", "chaincode", "invoke",
        "-o", "localhost:7050",
        "--ordererTLSHostnameOverride", "orderer.example.com",
        "--tls",
        "--cafile", ORDERER_CA,
        "-C", CHANNEL_NAME,
        "-n", CHAINCODE_NAME,
        "--peerAddresses", "localhost:7051",
        "--tlsRootCertFiles", os.environ["CORE_PEER_TLS_ROOTCERT_FILE"],
        "--peerAddresses", "localhost:9051",
        "--tlsRootCertFiles", f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt",
        "-c", json.dumps({
            "function": "ConfirmCIDUpload",
            "Args": [vector_hash, cid]
        })
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Confirmed {vector_hash} on blockchain.\n")
        return True
    else:
        print(f"❌ Confirmation failed: {result.stderr}")
        return False

# === Main Loop ===
def main():
    print("🛰 Starting blockchain listener...")
    while True:
        files = [f for f in os.listdir(UNCONFIRMED_DIR) if f.endswith(".json")]
        for filename in files:
            path = os.path.join(UNCONFIRMED_DIR, filename)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    vector = data["vector"]
                    vector_hash = data["hash"]
            except Exception as e:
                print(f"⚠ Failed to read {filename}: {e}")
                continue

            # Save temp file for IPFS
            temp_path = f"{vector_hash}_vector.json"
            with open(temp_path, "w") as f:
                json.dump({"vector": vector}, f)

            cid = upload_to_ipfs(temp_path)
            os.remove(temp_path)

            if cid and confirm_on_blockchain(vector_hash, cid):
                os.rename(path, os.path.join(PROCESSED_DIR, filename))
            else:
                print(f"⏳ Will retry {vector_hash} later.")

        time.sleep(POLL_INTERVAL)

# === Entry Point ===
if _name_ == "_main_":
    main()
