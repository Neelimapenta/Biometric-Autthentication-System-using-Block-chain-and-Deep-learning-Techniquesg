import dlib
import cv2
import json
import hashlib
import numpy as np
from datetime import datetime, timezone
import os

# === Paths ===
SHAPE_PREDICTOR_PATH = "/home/biometric/1/notebooks/shape_predictor_68_face_landmarks.dat"
FACE_RECOGNITION_MODEL_PATH = "/home/biometric/1/notebooks/dlib_face_recognition_resnet_model_v1.dat"
IMAGE_PATH = "/home/biometric/1/person8.jpeg"
AUTH_FILE = "auth_requests.json"

# === Load models ===
print("📦 Loading models...")
detector = dlib.get_frontal_face_detector()
shape_predictor = dlib.shape_predictor(SHAPE_PREDICTOR_PATH)
face_rec_model = dlib.face_recognition_model_v1(FACE_RECOGNITION_MODEL_PATH)

# === Read Image ===
print("🖼 Reading image...")
img = cv2.imread(IMAGE_PATH)
if img is None:
    print(f"❌ Failed to read image at {IMAGE_PATH}")
    exit(1)

rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
faces = detector(rgb_img)

if len(faces) == 0:
    print("❌ No face detected.")
    exit(1)

# === Extract Vector ===
shape = shape_predictor(rgb_img, faces[0])
face_vector = np.array(face_rec_model.compute_face_descriptor(rgb_img, shape), dtype=np.float32)

# === Hash the vector ===
vector_hash = hashlib.sha256(face_vector.tobytes()).hexdigest()
print(f"🔐 Vector hash: {vector_hash}")

# === Append to auth_requests.json ===
request = {
    "hash": vector_hash,
    "vector": face_vector.tolist(),
    "timestamp": datetime.now(timezone.utc).isoformat()
}

if os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, "r") as f:
        data = json.load(f)
else:
    data = []

data.append(request)

with open(AUTH_FILE, "w") as f:
    json.dump(data, f, indent=2)

print("✅ Authentication request recorded.")
