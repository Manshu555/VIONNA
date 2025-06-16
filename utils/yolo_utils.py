from ultralytics import YOLO

model = YOLO("models/yolov8n.pt")

def detect_people(frame):
    results = model(frame)[0]
    boxes = []
    for r in results.boxes.data.tolist():
        x1, y1, x2, y2, conf, cls = r
        if int(cls) == 0:
            boxes.append((int(x1), int(y1), int(x2), int(y2)))
    return boxes
