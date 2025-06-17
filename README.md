# VIONNA

> **Vision-Integrated Observation Network for Neural-based Attendance**

---

### 💡 What does V.I.O.N.N.A. stand for?

| Letter | Meaning      | Description                                                                                  |
|--------|--------------|----------------------------------------------------------------------------------------------|
| **V**  | **Vision**   | Computer Vision technologies (YOLOv8, OpenCV, face detection, etc.)                          |
| **I**  | **Integrated** | Seamless integration of camera systems, email, Google Sheets, and more                      |
| **O**  | **Observation** | Real-time tracking of faces, liveliness, and classroom behavior                            |
| **N**  | **Network**  | Multi-device setup, Google Sheets synchronization, Gmail alerts                              |
| **N**  | **Neural-based** | Utilizes CNNs, transfer learning, liveness models, and a self-healing AI agent            |
| **A**  | **Attendance** | The core goal: intelligent, automated attendance management                                 |

---
VIONNA is an automated attendance system that integrates advanced computer vision and neural network technologies for reliable, real-time attendance management. It uses YOLO for person detection, InsightFace for face recognition, a deepfake detection server, and liveliness checks to ensure accuracy. The system records daily attendance, sends absence alerts, generates summaries, and provides comprehensive weekly reports—all with seamless integration across devices and services.

## Prerequisites

- Python 3.8+
- Webcam for video capture
- Gmail account (with app password for SMTP)

## Project Structure

```
AUTOATTENDANCEYOLO/
├── main.py                     # Main script for daily attendance
├── weekly_report.py            # Sends weekly attendance reports
├── deepfake_server.py          # Flask server for deepfake detection
├── utils/
│   ├── yolo_utils.py           # YOLO utilities
│   └── liveliness.py           # Liveliness check utilities
├── data/
│   ├── students.csv            # Student list and emails
│   ├── teachers.csv            # Teacher/class details
│   ├── sender_credentials.csv  # Email credentials (not in repo)
│   └── encodings/
│       └── face_encodings.pkl  # Precomputed face encodings
└── models/
    ├── yolov8n.pt              # YOLOv8 Nano model (download separately)
    └── deepfake-detection-model.h5 # Deepfake detection model (download separately)
```

**Note**: The `data/` directory is not included in this repository due to its size and sensitive contents. You’ll need to create it manually as described in the setup instructions.

## Setup Instructions

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/AutoAttendanceYOLO.git
   cd AutoAttendanceYOLO
## Setup Instructions

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/AutoAttendanceYOLO.git
   cd AutoAttendanceYOLO
   ```

2. **Install Dependencies** (using two virtual environments):

This project uses two Python versions to avoid dependency conflicts:
- **Python 3.11** for attendance and reporting scripts (`main.py`, `weekly_report.py`)
- **Python 3.12** for the deepfake detection server (`deepfake_server.py`)

#### a. Set Up Attendance Environment (Python 3.11)
```bash
python3.11 -m venv attendance-env
source attendance-env/bin/activate
pip install insightface==0.7.3 onnxruntime numpy requests opencv-python ultralytics
deactivate
```

#### b. Set Up Deepfake Environment (Python 3.12)
```bash
python3.12 -m venv deepfake-env
source deepfake-env/bin/activate
pip install tensorflow flask numpy opencv-python
deactivate
```

3. **Download Model Files**:
   - Download `yolov8n.pt` from the [Ultralytics YOLOv8 releases](https://github.com/ultralytics/ultralytics/releases) and place it in `models/`.
   - Download `deepfake-detection-model.h5` (provide your own link if hosted elsewhere) and place it in `models/`.

4. **Prepare Data Files**:
   - Create `data/students.csv`:
     ```
     Name,Email
     student1,student1@example.com
     student2,student2@example.com
     ```
   - Create `data/teachers.csv`:
     ```
     Name,Department,Email,Class Timing,Max Classes
     Prof. Sharma,Computer Science,teacher@example.com,07:10:00,5
     ```
   - Create `data/sender_credentials.csv`:
     ```
     Email,AppPassword
     your.email@gmail.com,your-app-password
     ```
     > To generate an app password, enable 2-Step Verification in your Google Account and create an app password for "Mail".

   - Ensure `data/encodings/face_encodings.pkl` exists with precomputed face encodings (generate using InsightFace as needed).

## Usage

### 1. Start the Deepfake Server (`deepfake-env`)

Open a terminal and run:
```bash
cd /path/to/VIONNA
source deepfake-env/bin/activate
python deepfake_server.py
```
**Expected output:**
```
* Running on http://0.0.0.0:5001/
```

### 2. Run Main Attendance Script (`attendance-env`)

Open a second terminal and run:
```bash
cd /path/to/VIONNA
source attendance-env/bin/activate
python main.py
```
- Ensure the `Class Timing` in `teachers.csv` is set to a future time (e.g., `08:30:00` if it’s before 08:30 AM IST).
- The script will wait until the class starts, then begin capturing video and marking attendance.
- Students should be in front of the webcam.
- Press `x` to end early or wait for the session to finish.

### 3. Run Weekly Report Script (`attendance-env`)

Open a third terminal and run:
```bash
cd /path/to/VIONNA
source attendance-env/bin/activate
python weekly_report.py
```
- This script sends weekly attendance reports every Sunday at 22:40 IST.


## Outputs

- **Daily:**
  - `data/attendance.csv`: Daily attendance
  - `data/weekly_attendance.csv`: Appends daily records for weekly tracking
  - `data/attendance_summary.txt`: Human-readable summary
  - `data/attendance_report.csv`: Report emailed to teacher
  - Absence alerts sent to students

- **Weekly:**
  - On Sundays at 22:40 IST, `weekly_report.py` emails weekly reports and resets `weekly_attendance.csv`.


## Data Analyst Agent

- **Data_analyst_agent.ipynb** (Backend-focused)

The Data Analyst Agent allows anyone to upload a document (`.doc`, `.txt`, `.xlsx`, `.csv`, `.pdf`, or image file). The agent can analyze the uploaded data, answer questions and follow-up queries, and create visualization graphs based on the content.

**Features:**
- Supports multiple file formats for upload and analysis.
- Provides data insights and answers to user questions.
- Generates visualizations to help interpret the data.

To use, open `data_analyst_agent.ipynb` and follow the instructions in the notebook.

1. **Paste your Together API key**:  
  In the notebook, enter your Together API key when prompted. This is required for data analysis and visualization features.

2. **Store your documents locally**:  
  Save the files you want to analyze (such as `.doc`, `.txt`, `.xlsx`, `.csv`, `.pdf`, or image files) on your computer.

3. **Upload documents in the notebook**:  
In the notebook, use the file path of your document (e.g., `YTchatbot_report.pdf`). Once uploaded, the agent will confirm the file is loaded successfully. You can then ask questions about the data, such as "What is this PDF about?" or request visualizations. Use commands like `exit` to quit, `view_memory` to see your question history, or `clear_memory` to reset the session.

## Troubleshooting

- **Camera Issues:** Ensure webcam is connected. Adjust camera index in `main.py` if needed.
- **Email Issues:** Verify Gmail app password. "Less secure app access" is not required with app passwords.
- **Detection Issues:** Check terminal logs for similarity scores, deepfake, and liveliness results.

## Contributing

Fork the repository, make improvements, and submit a pull request!

## License

This project, **Vionna**.  
© 2025 Manshu Jaiswal. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files...
---
