import time
import subprocess
import json
import os

FABRIC_DIR = "/home/biometric/1/fabric-samples"
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"

os.environ.update({
    "PATH": os.environ["PATH"] + os.pathsep + f"{FABRIC_DIR}/bin",
    "FABRIC_CFG_PATH": f"{FABRIC_DIR}/config",
    "CORE_PEER_TLS_ENABLED": "true",
    "CORE_PEER_LOCALMSPID": "Org1MSP",
    "CORE_PEER_TLS_ROOTCERT_FILE": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt",
    "CORE_PEER_MSPCONFIGPATH": f"{FABRIC_DIR}/test-network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp",
    "CORE_PEER_ADDRESS": "localhost:7051"
})

def get_all_records():
    cmd = [
        "peer", "chaincode", "query",
        "-C", CHANNEL_NAME,
        "-n", CHAINCODE_NAME,
        "-c", json.dumps({
            "function": "GetAllCIDRecords",
            "Args": []
        })
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return []

def delete_record(hash_id):
    print(f"🗑 Deleting hash from blockchain: {hash_id}")
    cmd = [
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
            "Args": [hash_id]
        })
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Deleted hash {hash_id} successfully.")
    else:
        print(f"❌ Failed to delete {hash_id}. Error:\n{result.stderr}")

print("👂 Listening for deletion requests via blockchain polling...")

previous_records = set(r["id"] for r in get_all_records())

while True:
    current_records = get_all_records()
    current_ids = set(r["id"] for r in current_records)

    deleted_ids = previous_records - current_ids
    if deleted_ids:
        print(f"ℹ These hashes were deleted already: {deleted_ids}")

    new_ids = current_ids - previous_records
    if new_ids:
        print(f"ℹ New hashes found: {new_ids}")

    for record in current_records:
        if record["id"] not in previous_records:
            # Check if this record was requested for deletion
            # You can add metadata to trigger deletion, or simulate via external signal
            continue  # We only handle deletion via event -> this avoids rechecking

    # Check for delete requests by reading records & finding ones with CID
    for rec in current_records:
        if rec["id"].endswith("_delete"):
            real_id = rec["id"].replace("_delete", "")
            print(f"⚠ Detected deletion candidate: {real_id}")
            delete_record(real_id)

    previous_records = current_ids
    time.sleep(5)
