# face_utils.py
import insightface
from insightface.app import FaceAnalysis
import os
import numpy as np
import pickle
import cv2

def encode_faces(dataset_path='dataset/'):
    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=-1)  # use -1 for CPU fallback if needed

    known_encodings = []
    known_names = []

    print("[INFO] Starting face encoding...")

    for person_name in os.listdir(dataset_path):
        person_folder = os.path.join(dataset_path, person_name)
        if not os.path.isdir(person_folder):
            continue

        print(f"[INFO] Processing: {person_name}")

        for img_file in os.listdir(person_folder):
            img_path = os.path.join(person_folder, img_file)
            print(f"  → Reading: {img_path}")
            img = cv2.imread(img_path)

            if img is None:
                print(f"  [WARNING] Could not load image: {img_path}")
                continue

            faces = app.get(img)
            if not faces:
                print(f"  [SKIP] No face found in {img_file}")
                continue

            known_encodings.append(faces[0].embedding)
            known_names.append(person_name)
            print(f"  [✓] Face encoded for {img_file}")

    if known_encodings:
        os.makedirs("encodings", exist_ok=True)
        with open("encodings/face_encodings.pkl", "wb") as f:
            pickle.dump((known_encodings, known_names), f)
        print(f"[✅] Encoded {len(known_encodings)} faces.")
    else:
        print("[❌] No faces encoded.")

if __name__ == "__main__":
    encode_faces()
