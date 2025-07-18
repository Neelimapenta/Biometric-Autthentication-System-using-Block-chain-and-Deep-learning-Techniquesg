import json
import asyncio
import hashlib
import time
import ipfshttpclient
import numpy as np
import faiss
import os
import subprocess

# === CONFIG ===
CHANNEL_NAME = "mychannel"
CHAINCODE_NAME = "cidrecord"
AUTH_FILE = "auth_requests.json"
SIMILARITY_THRESHOLD = 0.95

# === Connect to IPFS ===
ipfs = ipfshttpclient.connect("/ip4/127.0.0.1/tcp/5001")

# === FAISS setup ===
dimension = 128
index = faiss.IndexFlatL2(dimension)
hash_list = []

# === Load all registered vectors from blockchain/IPFS ===
def load_registered_vectors():
    print("📡 Querying blockchain for all registered vectors...")

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
        print("❌ Blockchain query failed.")
        print(result.stderr)
        return [], []

    try:
        cid_records = json.loads(result.stdout)
    except Exception as e:
        print("❌ Failed to parse CID records:", e)
        return [], []

    vectors = []
    hashes = []

    for record in cid_records:
        try:
            cid = record["cid"]
            fid = record["id"]
            data = ipfs.cat(cid)
            obj = json.loads(data.decode("utf-8"))

            if isinstance(obj, dict) and "vector" in obj:
                vector = np.array(obj["vector"], dtype=np.float32)
            else:
                vector = np.array(obj, dtype=np.float32)

            if len(vector) == 128:
                vectors.append(vector)
                hashes.append(fid)
            else:
                print(f"⚠ Invalid vector length for {fid}")
        except Exception as e:
            print(f"⚠ Failed to load from IPFS for {record.get('id')}: {e}")

    return vectors, hashes

# === Handle authentication events ===
async def listen_for_auth_events():
    print("👂 Listening for authentication requests...")

    while True:
        try:
            if not os.path.exists(AUTH_FILE):
                await asyncio.sleep(2)
                continue

            with open(AUTH_FILE, "r") as f:
                requests = json.load(f)

            if not requests:
                await asyncio.sleep(2)
                continue

            vectors, known_hashes = load_registered_vectors()

            if not vectors:
                print("⚠ No vectors found on blockchain/IPFS.")
                await asyncio.sleep(2)
                continue

            index.reset()
            hash_list.clear()
            for vec, h in zip(vectors, known_hashes):
                index.add(np.array([vec], dtype=np.float32))
                hash_list.append(h)

            updated_requests = []
            for req in requests:
                vec = np.array(req["vector"], dtype=np.float32)
                vec_hash = req["hash"]
                print(f"🔐 Authenticating vector with hash: {vec_hash}")

                D, I = index.search(np.array([vec]), k=1)
                sim = 1 - D[0][0] / 4  # cosine approximation from L2
                sim = round(sim, 4)

                if sim >= SIMILARITY_THRESHOLD:
                    matched_hash = hash_list[I[0][0]]
                    print(f"✅ Match found: {matched_hash} (Similarity: {sim})")
                else:
                    print(f"❌ No match found (Similarity: {sim})")

                # After processing, don't reprocess same request
                # So we don't add it to updated_requests

            # Clear the auth file after processing all
            with open(AUTH_FILE, "w") as f:
                json.dump([], f, indent=2)

        except Exception as e:
            print("❌ Error:", e)

        await asyncio.sleep(3)

# === Start ===
if _name_ == "_main_":
    asyncio.run(listen_for_auth_events())
