from flask import Flask, request, jsonify
import cv2
import numpy as np
from tensorflow.keras.models import load_model
import os
import base64
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load the deepfake detection model
model_path = 'models/deepfake-detection-model.h5'
if not os.path.exists(model_path):
    logger.error(f"Model file not found at {model_path}")
    raise FileNotFoundError(f"Model file not found at {model_path}")
model = load_model(model_path)
logger.info("Deepfake model loaded successfully")

@app.route('/detect_deepfake', methods=['POST'])
def detect_deepfake():
    try:
        # Expect a JSON payload with a base64-encoded image
        data = request.get_json()
        if not data or 'image' not in data:
            logger.warning("No image provided in request")
            return jsonify({'error': 'No image provided'}), 400

        # Decode the base64 image
        img_base64 = data['image']
        img_data = base64.b64decode(img_base64)
        npimg = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

        if img is None:
            logger.warning("Failed to decode image")
            return jsonify({'error': 'Failed to decode image'}), 400

        # Preprocess the image
        img = cv2.resize(img, (200, 200))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img / 255.0
        img = np.expand_dims(img, axis=0)

        # Make prediction
        prediction = model.predict(img)[0][0]
        label = 'Fake' if prediction <= 0.5 else 'Real'
        confidence = float(prediction) if label == 'Real' else float(1 - prediction)

        logger.info(f"Prediction: {label}, Confidence: {confidence}")
        return jsonify({
            'label': label,
            'confidence': confidence
        })
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)