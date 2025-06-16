from flask import Flask, request, jsonify
import cv2
import numpy as np
from tensorflow.keras.models import load_model
import os

app = Flask(__name__)

model_path = 'models/deepfake-detection-model.h5'
if not os.path.exists(model_path):
    raise FileNotFoundError(f"Model file not found at {model_path}")
model = load_model(model_path)

@app.route('/detect_deepfake', methods=['POST'])
def detect_deepfake():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    try:

        filestr = file.read()
        npimg = np.frombuffer(filestr, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        img = cv2.resize(img, (200, 200))  
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  
        img = img / 255.0 
        img = np.expand_dims(img, axis=0)  

        prediction = model.predict(img)[0][0]
        label = 'Fake' if prediction <= 0.5 else 'Real'
        confidence = float(prediction) if label == 'Real' else float(1 - prediction)

        return jsonify({
            'label': label,
            'confidence': confidence
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)


