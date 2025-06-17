from insightface.app import FaceAnalysis
import numpy as np
import pickle
import cv2
import csv
from datetime import datetime, timedelta
import requests
import base64
from utils.yolo_utils import detect_people
from utils.liveliness import check_liveliness, reset_liveliness
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import time
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize resources
cap = None
daily_attendance_file = None
app = None

try:
    # Load known faces
    encodings_path = 'data/encodings/face_encodings.pkl'
    if not os.path.exists(encodings_path):
        logger.error(f"Face encodings file not found at {encodings_path}")
        exit(1)
    with open(encodings_path, 'rb') as f:
        known_encodings, known_names = pickle.load(f)

    # Remove duplicates from known_names while preserving corresponding encodings
    unique_names = []
    unique_encodings = []
    seen_names = set()
    for name, encoding in zip(known_names, known_encodings):
        if name not in seen_names:
            unique_names.append(name)
            unique_encodings.append(encoding)
            seen_names.add(name)

    known_names = unique_names
    known_encodings = unique_encodings
    logger.info(f"Unique known names: {known_names}")

    # Load student emails from students.csv
    STUDENT_EMAILS = {}
    students_file = 'data/students.csv'
    if not os.path.exists(students_file):
        logger.error(f"Students file not found at {students_file}")
        exit(1)
    try:
        with open(students_file, 'r') as email_file:
            csv_reader = csv.DictReader(email_file)
            if not csv_reader.fieldnames:
                logger.error("data/students.csv is empty or has no header row")
                exit(1)
            logger.info(f"Columns found in students.csv: {csv_reader.fieldnames}")
            
            email_column = None
            for field in csv_reader.fieldnames:
                if field.lower() == 'email':
                    email_column = field
                    break
            name_column = None
            for field in csv_reader.fieldnames:
                if field.lower() == 'name':
                    name_column = field
                    break

            if not name_column:
                logger.error("'Name' column not found in data/students.csv")
                exit(1)
            if not email_column:
                logger.error("'Email' column not found in data/students.csv")
                exit(1)

            for row in csv_reader:
                STUDENT_EMAILS[row[name_column]] = row[email_column]
    except Exception as e:
        logger.error(f"Error reading students.csv: {e}")
        exit(1)

    # Load sender credentials from sender_credentials.csv
    sender_file = 'data/sender_credentials.csv'
    if not os.path.exists(sender_file):
        logger.error(f"Sender credentials file not found at {sender_file}")
        exit(1)
    try:
        with open(sender_file, 'r') as sender_file:
            csv_reader = csv.DictReader(sender_file)
            sender_data = next(csv_reader)
            SENDER_EMAIL = sender_data['Email']
            SENDER_APP_PASSWORD = sender_data['AppPassword']
    except Exception as e:
        logger.error(f"Error reading sender_credentials.csv: {e}")
        exit(1)

    # Load teacher details from teachers.csv
    TEACHER_DETAILS = {}
    teachers_file = 'data/teachers.csv'
    if not os.path.exists(teachers_file):
        logger.error(f"Teachers file not found at {teachers_file}")
        exit(1)
    try:
        with open(teachers_file, 'r') as teacher_file:
            csv_reader = csv.DictReader(teacher_file)
            if not csv_reader.fieldnames:
                logger.error("data/teachers.csv is empty or has no header row")
                exit(1)
            logger.info(f"Columns found in teachers.csv: {csv_reader.fieldnames}")
            
            email_column = None
            for field in csv_reader.fieldnames:
                if field.lower() == 'email':
                    email_column = field
                    break
            name_column = None
            for field in csv_reader.fieldnames:
                if field.lower() == 'name':
                    name_column = field
                    break
            timing_column = None
            for field in csv_reader.fieldnames:
                if field.lower() == 'class timing':
                    timing_column = field
                    break

            if not name_column:
                logger.error("'Name' column not found in data/teachers.csv")
                exit(1)
            if not email_column:
                logger.error("'Email' column not found in data/teachers.csv")
                exit(1)
            if not timing_column:
                logger.error("'Class Timing' column not found in data/teachers.csv")
                exit(1)

            teacher_data = next(csv_reader)
            TEACHER_DETAILS = {
                'name': teacher_data[name_column],
                'email': teacher_data[email_column],
                'class_timing': teacher_data[timing_column]
            }
    except Exception as e:
        logger.error(f"Error reading teachers.csv: {e}")
        exit(1)

    # Parse class start time
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        class_start_time = datetime.strptime(f"{current_date} {TEACHER_DETAILS['class_timing']}", "%Y-%m-%d %H:%M:%S")
        class_end_time = class_start_time + timedelta(minutes=10)
        logger.info(f"Class starts at: {class_start_time}")
        logger.info(f"Class ends at: {class_end_time}")

        current_time = datetime.now()
        if current_time > class_end_time:
            logger.error(f"The class timing ({TEACHER_DETAILS['class_timing']}) has already passed for today ({current_date})")
            exit(1)
    except ValueError as e:
        logger.error(f"Invalid 'Class Timing' format in data/teachers.csv. Expected format: HH:MM:SS (e.g., 21:00:00). Error: {e}")
        exit(1)

    # Wait until class start time if we're early
    if current_time < class_start_time:
        wait_seconds = (class_start_time - current_time).total_seconds()
        logger.info(f"Waiting for class to start in {wait_seconds:.0f} seconds...")
        time.sleep(wait_seconds)

    attendance = {}
    # Try multiple camera indices
    # for index in range(3):  # Try indices 0, 1, 2
    cap = cv2.VideoCapture(1)
        # if cap.isOpened():
        #     logger.info(f"Camera opened successfully with index {index}")
        #     break
    
    if not cap.isOpened():
        logger.error("Could not open camera with indices 0, 1, or 2. Please check your camera setup")
        exit(1)

    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=0)

    reset_liveliness()

    # Initialize weekly attendance CSV
    weekly_attendance_file = 'data/weekly_attendance.csv'
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(weekly_attendance_file):
        with open(weekly_attendance_file, 'w', newline='') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(['Date', 'Name', 'Status'])

    # Open daily attendance CSV
    daily_attendance_file = open('data/attendance.csv', 'w', newline='')
    daily_writer = csv.writer(daily_attendance_file)
    daily_writer.writerow(['Name', 'Entry Time', 'Deepfake Status', 'Liveliness Status'])

    # Corrected deepfake server URL (LOCAL)
    # DEEPFAKE_SERVER_URL = 'http://localhost:5001/detect_deepfake'
    # Update the URL to use the Docker service name
    DEEPFAKE_SERVER_URL = 'http://deepfake-server:5001/detect_deepfake'
    def send_to_deepfake_server(face_crop):
        try:
            _, buffer = cv2.imencode('.jpg', face_crop)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            response = requests.post(DEEPFAKE_SERVER_URL, json={'image': img_base64})
            response.raise_for_status()
            result = response.json()
            if 'error' in result:
                logger.warning(f"Deepfake server error: {result['error']}")
                return "Real", 0.0
            return result['label'], result['confidence']
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in deepfake detection: {e}")
            return "Real", 0.0

    def send_absence_alerts(absent_students, all_students_emails):
        subject = "Absence Alert - Verify Absent Students"
        absent_list = ", ".join(absent_students) if absent_students else "None"
        body = f"""
        Dear Students,

        The following students were absent from today's session on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:
        {absent_list}

        Please verify if this is correct by replying to this email or via SMS.
        If you believe this is an error, let us know.

        Regards,
        AutoAttendance System
        """

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            for student, email in all_students_emails.items():
                try:
                    msg = MIMEMultipart()
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = email
                    msg['Subject'] = subject
                    msg.attach(MIMEText(body, 'plain'))
                    server.sendmail(SENDER_EMAIL, email, msg.as_string())
                    logger.info(f"Sent absence alert to {student} at {email}")
                except Exception as e:
                    logger.error(f"Error sending absence alert to {student} at {email}: {e}")
            server.quit()
        except Exception as e:
            logger.error(f"Error connecting to SMTP server for absence alerts: {e}")

    def generate_attendance_summary(present_students, absent_students):
        present_list = []
        for student in present_students:
            present_list.append(f"{student['Name']} at {student['Entry Time']} (Deepfake: {student['Deepfake Status']}, Liveliness: {student['Liveliness Status']})")
        present_summary = "; ".join(present_list) if present_list else "None"
        absent_summary = ", ".join(absent_students) if absent_students else "None"
        
        summary = f"On {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST, the attendance session recorded the following: {present_summary}. All present students were verified as real (Deepfake: Real) and live (Liveliness: Live). The following students were absent: {absent_summary}."

        with open('data/attendance_summary.txt', 'w') as summary_file:
            summary_file.write(summary)
        logger.info("Attendance summary saved to data/attendance_summary.txt")
        logger.info(f"Summary: {summary}")

    def send_attendance_report_to_teacher(known_names, present_students, teacher_email, session_start_time):
        report_file_path = 'data/attendance_report.csv'
        with open(report_file_path, 'w', newline='') as report_file:
            csv_writer = csv.writer(report_file)
            csv_writer.writerow(['Student Name', 'Status', 'Lateness (Minutes)'])

            present_dict = {student['Name']: student['Entry Time'] for student in present_students}
            for student in known_names:
                if student in present_dict:
                    status = "Present"
                    entry_time_str = present_dict[student]
                    entry_time = datetime.strptime(f"{current_date} {entry_time_str}", "%Y-%m-%d %H:%M:%S")
                    lateness = (entry_time - session_start_time).total_seconds() / 60.0
                    lateness_str = f"{lateness:.2f}" if lateness > 0 else "0.00"
                else:
                    status = "Absent"
                    lateness_str = "N/A"
                csv_writer.writerow([student, status, lateness_str])

        logger.info("Attendance report generated at data/attendance_report.csv")

        subject = "Attendance Report - AutoAttendanceYOLO"
        body = f"""
        Dear Teacher,

        Please find attached the attendance report for the session on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST.
        The session started at {session_start_time.strftime('%Y-%m-%d %H:%M:%S')} IST.

        Regards,
        AutoAttendance System
        """

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = teacher_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            with open(report_file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename=attendance_report.csv')
            msg.attach(part)
            server.sendmail(SENDER_EMAIL, teacher_email, msg.as_string())
            logger.info(f"Sent attendance report to {teacher_email}")
            server.quit()
        except Exception as e:
            logger.error(f"Error sending attendance report to {teacher_email}: {e}")

    # Main attendance loop
    while True:
        current_time = datetime.now()
        if current_time >= class_end_time:
            logger.info("Class session ended. Stopping attendance capture")
            break

        ret, frame = cap.read()
        if not ret:
            logger.warning("Failed to capture frame")
            continue

        boxes = detect_people(frame)
        logger.info(f"YOLO detected {len(boxes)} people: {boxes}")

        for (x1, y1, x2, y2) in boxes:
            face_crop = frame[y1:y2, x1:x2]
            faces = app.get(face_crop)
            logger.info(f"InsightFace detected {len(faces)} faces")
            name = "Unknown"
            deepfake_status = "Unknown"
            confidence = 0.0
            liveliness_status = "Unknown"

            if faces:
                embedding = faces[0].embedding
                similarities = [np.dot(embedding, known) / (np.linalg.norm(embedding) * np.linalg.norm(known)) for known in known_encodings]
                best_match_index = int(np.argmax(similarities))
                similarity_score = similarities[best_match_index]
                logger.info(f"Similarity score for detected face: {similarity_score:.2f}")
                if similarity_score > 0.4:
                    name = known_names[best_match_index]
                    logger.info(f"Recognized: {name}")

                    deepfake_status, confidence = send_to_deepfake_server(face_crop)
                    logger.info(f"Deepfake result for {name}: {deepfake_status}, Confidence: {confidence:.2f}")

                    is_live = check_liveliness(name, (x1, y1, x2, y2))
                    logger.info(f"Raw liveliness result for {name}: {is_live}")
                    liveliness_status = "Live" if is_live else "Static"
                    logger.info(f"Liveliness result for {name}: {liveliness_status}")

                    if name not in attendance and deepfake_status == "Real" and liveliness_status == "Live":
                        entry_time = datetime.now().strftime("%H:%M:%S")
                        attendance[name] = entry_time
                        logger.info(f"Marked present: {name} at {entry_time} (Deepfake: {deepfake_status}, Confidence: {confidence:.2f}, Liveliness: {liveliness_status})")
                        daily_writer.writerow([name, entry_time, deepfake_status, liveliness_status])
                        daily_attendance_file.flush()

                        with open(weekly_attendance_file, 'a', newline='') as f:
                            csv_writer = csv.writer(f)
                            csv_writer.writerow([datetime.now().strftime('%Y-%m-%d'), name, 'Present'])
                    else:
                        logger.warning(f"Failed to mark {name} as present. Deepfake: {deepfake_status}, Liveliness: {liveliness_status}")
                else:
                    logger.info("Similarity score too low. Face not recognized")
            else:
                logger.info("No face detected in this frame")

            label = f"{name} ({deepfake_status}, {confidence:.2f}, {liveliness_status})"
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if deepfake_status == "Real" and liveliness_status == "Live" else (0, 0, 255), 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if deepfake_status == "Real" and liveliness_status == "Live" else (0, 0, 255), 2)

        cv2.imshow("Auto Attendance - InsightFace", frame)
        if cv2.waitKey(1) & 0xFF == ord('x'):
            logger.info("Session ended early by user")
            break

    # Append absent students to weekly attendance
    with open(weekly_attendance_file, 'a', newline='') as f:
        csv_writer = csv.writer(f)
        absent_students = [name for name in known_names if name not in attendance]
        for student in absent_students:
            csv_writer.writerow([datetime.now().strftime('%Y-%m-%d'), student, 'Absent'])

    logger.info(f"Absent students: {absent_students}")

    if absent_students:
        send_absence_alerts(absent_students, STUDENT_EMAILS)

    present_students = []
    with open('data/attendance.csv', 'r') as attendance_file:
        csv_reader = csv.DictReader(attendance_file)
        for row in csv_reader:
            present_students.append(row)

    generate_attendance_summary(present_students, absent_students)
    send_attendance_report_to_teacher(known_names, present_students, TEACHER_DETAILS['email'], class_start_time)

finally:
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    if daily_attendance_file is not None:
        daily_attendance_file.close()
    logger.info("Resources cleaned up successfully")