# run with fastapi run model_api.py
# http://localhost:8000/result/
from fastapi import FastAPI, File
from typing import Annotated
from ultralytics import YOLO
from PIL import Image
import numpy as np
import threading
import time
import io

"""
Configurations
"""
YOLO_MODEL_PATH = "models\\best_detect.onnx"  # Path to the YOLO model

"""
Load YOLO model and warm up
"""
yolo_model = YOLO(YOLO_MODEL_PATH, task='detect')
width, height = 256, 256
random_info = yolo_model([Image.fromarray(np.random.randint(0, 256, (height, width, 3), dtype=np.uint8), 'RGB')])

"""
Images
"""
prediction = None
last_prediction_time = 0

new_img = False
predicting = False

img = None
img_buffer = None


def prediction_loop():
    global predicting, img_buffer, img, new_img, prediction, last_prediction_time
    while True:
        if new_img:
            predicting = True
            img = img_buffer
            img_buffer = None
            new_img = False

            # Perform prediction
            prediction = yolo_model(img)
            last_prediction_time = time.time()
            
            predicting = False
        time.sleep(0.1)  # Sleep briefly to avoid busy-waiting


# Start the prediction loop in a separate thread
threading.Thread(target=prediction_loop, daemon=True).start()


"""
API
"""
app = FastAPI()

@app.get("/")
async def root():
    if random_info[0].boxes is not None and len(random_info[0].boxes) > 0:
        # Get class indices, confidence scores, and class names
        classes = random_info[0].boxes.cls.int().cpu().numpy()
        confidences = random_info[0].boxes.conf.cpu().numpy()
        
        # Create list of detections with class names and confidence
        detections = []
        for cls_idx, conf in zip(classes, confidences):
            detections.append({
                "class_name": random_info[0].names[cls_idx.item()],
                "confidence": float(conf)
            })
        
        # Sort by confidence in descending order
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {"detections": detections}
    else:
        return {"detections": []}

@app.post("/predict/")
async def predict(image: Annotated[bytes, File()]):
    global predicting, img_buffer, new_img
    img_buffer = Image.open(io.BytesIO(image))
    new_img = True
    return {"status": "Image received for prediction"}

@app.get("/result/")
async def get_result():
    global prediction, last_prediction_time
    
    if prediction is None:
        return {
            "detections": [],
            "timestamp": None,
            "message": "No prediction available yet"
        }
    
    # Check if prediction has results
    if prediction[0].boxes is not None and len(prediction[0].boxes) > 0:
        # Get class indices, confidence scores, bounding boxes, and class names
        classes = prediction[0].boxes.cls.int().cpu().numpy()
        confidences = prediction[0].boxes.conf.cpu().numpy()
        bboxes = prediction[0].boxes.xyxy.cpu().numpy()
        
        # Create list of detections with class names, confidence, and bounding boxes
        detections = []
        for cls_idx, conf, bbox in zip(classes, confidences, bboxes):
            detections.append({
                "class_name": prediction[0].names[cls_idx.item()],
                "confidence": float(conf),
                "bbox": bbox.tolist()  # [x1, y1, x2, y2]
            })
        
        # Sort by confidence in descending order
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "detections": detections,
            "timestamp": last_prediction_time,
            "total_objects": len(detections)
        }
    else:
        return {
            "detections": [],
            "timestamp": last_prediction_time,
            "total_objects": 0,
            "message": "No objects detected in the image"
        }