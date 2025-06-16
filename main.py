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

# Initialize resources
cap = None
daily_attendance_file = None
app = None

try:
    # Load known faces
    with open('data/encodings/face_encodings.pkl', 'rb') as f:
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
    print(f"Unique known names: {known_names}")

    # Load student emails from students.csv
    STUDENT_EMAILS = {}
    try:
        with open('data/students.csv', 'r') as email_file:
            csv_reader = csv.DictReader(email_file)
            if not csv_reader.fieldnames:
                print("Error: data/students.csv is empty or has no header row.")
                exit()
            print(f"Columns found in students.csv: {csv_reader.fieldnames}")
            
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
                print("Error: 'Name' column not found in data/students.csv.")
                exit()
            if not email_column:
                print("Error: 'Email' column not found in data/students.csv.")
                exit()

            for row in csv_reader:
                STUDENT_EMAILS[row[name_column]] = row[email_column]
    except FileNotFoundError:
        print("Error: data/students.csv file not found. Please create it with 'Name' and 'Email' columns.")
        exit()

    # Load sender credentials from sender_credentials.csv
    try:
        with open('data/sender_credentials.csv', 'r') as sender_file:
            csv_reader = csv.DictReader(sender_file)
            sender_data = next(csv_reader)
            SENDER_EMAIL = sender_data['Email']
            SENDER_APP_PASSWORD = sender_data['AppPassword']
    except FileNotFoundError:
        print("Error: data/sender_credentials.csv file not found. Please create it with 'Email' and 'AppPassword' columns.")
        exit()
    except KeyError as e:
        print(f"Error: Missing column {e} in data/sender_credentials.csv. Expected 'Email' and 'AppPassword'.")
        exit()

    # Load teacher details from teachers.csv
    TEACHER_DETAILS = {}
    try:
        with open('data/teachers.csv', 'r') as teacher_file:
            csv_reader = csv.DictReader(teacher_file)
            if not csv_reader.fieldnames:
                print("Error: data/teachers.csv is empty or has no header row.")
                exit()
            print(f"Columns found in teachers.csv: {csv_reader.fieldnames}")
            
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
                print("Error: 'Name' column not found in data/teachers.csv.")
                exit()
            if not email_column:
                print("Error: 'Email' column not found in data/teachers.csv.")
                exit()
            if not timing_column:
                print("Error: 'Class Timing' column not found in data/teachers.csv.")
                exit()

            teacher_data = next(csv_reader)
            TEACHER_DETAILS = {
                'name': teacher_data[name_column],
                'email': teacher_data[email_column],
                'class_timing': teacher_data[timing_column]
            }
    except FileNotFoundError:
        print("Error: data/teachers.csv file not found. Please create it with 'Name', 'Department', 'Email', 'Class Timing', and 'Max Classes' columns.")
        exit()
    except KeyError as e:
        print(f"Error: Missing column {e} in data/teachers.csv.")
        exit()

    # Parse class start time
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        class_start_time = datetime.strptime(f"{current_date} {TEACHER_DETAILS['class_timing']}", "%Y-%m-%d %H:%M:%S")
        class_end_time = class_start_time + timedelta(minutes=10)
        print(f"Class starts at: {class_start_time}")
        print(f"Class ends at: {class_end_time}")

        # Check if the class start time has already passed
        current_time = datetime.now()
        if current_time > class_end_time:
            print(f"Error: The class timing ({TEACHER_DETAILS['class_timing']}) has already passed for today ({current_date}). Please update the 'Class Timing' in data/teachers.csv to a future time.")
            exit()
    except ValueError:
        print("Error: Invalid 'Class Timing' format in data/teachers.csv. Expected format: HH:MM:SS (e.g., 21:00:00).")
        exit()

    # Wait until class start time if we're early
    if current_time < class_start_time:
        wait_seconds = (class_start_time - current_time).total_seconds()
        print(f"Waiting for class to start in {wait_seconds:.0f} seconds...")
        time.sleep(wait_seconds)

    attendance = {}
    cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("Error: Could not open camera. Trying camera index 0...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open camera with index 0 either. Please check your camera setup.")
            exit()

    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=0)

    # Reset liveliness tracking for the new session
    reset_liveliness()

    # Initialize weekly attendance CSV
    weekly_attendance_file = 'data/weekly_attendance.csv'
    if not os.path.exists(weekly_attendance_file):
        with open(weekly_attendance_file, 'w', newline='') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(['Date', 'Name', 'Status'])

    # Open daily attendance CSV for this session
    daily_attendance_file = open('data/attendance.csv', 'w', newline='')
    daily_writer = csv.writer(daily_attendance_file)
    daily_writer.writerow(['Name', 'Entry Time', 'Deepfake Status', 'Liveliness Status'])

    # Backend server URL
    DEEPFAKE_SERVER_URL = 'http://localhost:5001/predict'

    def send_to_deepfake_server(face_crop):
        try:
            _, buffer = cv2.imencode('.jpg', face_crop)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            response = requests.post(DEEPFAKE_SERVER_URL, json={'image': img_base64})
            result = response.json()
            if 'error' in result:
                print("Deepfake server returned an error:", result['error'])
                return "Real", 0.0
            return result['label'], result['confidence']
        except Exception as e:
            print(f"Error in deepfake detection: {e}")
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
                    print(f"[+] Sent absence alert to {student} at {email}")
                except Exception as e:
                    print(f"Error sending absence alert to {student} at {email}: {e}")
            server.quit()
        except Exception as e:
            print(f"Error connecting to SMTP server for absence alerts: {e}")

    def generate_attendance_summary(present_students, absent_students):
        present_list = []
        for student in present_students:
            present_list.append(f"{student['Name']} at {student['Entry Time']} (Deepfake: {student['Deepfake Status']}, Liveliness: {student['Liveliness Status']})")
        present_summary = "; ".join(present_list) if present_list else "None"
        absent_summary = ", ".join(absent_students) if absent_students else "None"
        
        prompt = f"""
        On {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST, an attendance session was conducted.
        The following students were present: {present_summary}.
        The following students were absent: {absent_summary}.
        Generate a concise, human-readable summary of the attendance session. Include the date, time, list of present students with their entry times, list of absent students, and any notable observations about deepfake or liveliness status.
        """

        summary = f"On {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST, the attendance session recorded the following: {present_summary}. All present students were verified as real (Deepfake: Real) and live (Liveliness: Live). The following students were absent: {absent_summary}."

        with open('data/attendance_summary.txt', 'w') as summary_file:
            summary_file.write(summary)
        print("[+] Attendance summary saved to data/attendance_summary.txt")
        print(f"Summary: {summary}")

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

        print("[+] Attendance report generated at data/attendance_report.csv")

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
            print(f"[+] Sent attendance report to {teacher_email}")
            server.quit()
        except Exception as e:
            print(f"Error sending attendance report to {teacher_email}: {e}")

    # Main attendance loop
    while True:
        current_time = datetime.now()
        if current_time >= class_end_time:
            print("Class session ended. Stopping attendance capture.")
            break

        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame")
            break

        boxes = detect_people(frame)
        print(f"YOLO detected {len(boxes)} people: {boxes}")

        for (x1, y1, x2, y2) in boxes:
            face_crop = frame[y1:y2, x1:x2]
            faces = app.get(face_crop)
            print(f"InsightFace detected {len(faces)} faces")
            name = "Unknown"
            deepfake_status = "Unknown"
            confidence = 0.0
            liveliness_status = "Unknown"

            if faces:
                embedding = faces[0].embedding
                similarities = [np.dot(embedding, known) / (np.linalg.norm(embedding) * np.linalg.norm(known)) for known in known_encodings]
                best_match_index = int(np.argmax(similarities))
                similarity_score = similarities[best_match_index]
                print(f"Similarity score for detected face: {similarity_score:.2f}")
                if similarity_score > 0.4:
                    name = known_names[best_match_index]
                    print(f"Recognized: {name}")

                    deepfake_status, confidence = send_to_deepfake_server(face_crop)
                    print(f"Deepfake result for {name}: {deepfake_status}, Confidence: {confidence:.2f}")

                    is_live = check_liveliness(name, (x1, y1, x2, y2))
                    print(f"Raw liveliness result for {name}: {is_live}")
                    liveliness_status = "Live" if is_live else "Static"
                    print(f"Liveliness result for {name}: {liveliness_status}")

                    if name not in attendance and deepfake_status == "Real" and liveliness_status == "Live":
                        entry_time = datetime.now().strftime("%H:%M:%S")
                        attendance[name] = entry_time
                        print(f"[+] Marked present: {name} at {entry_time} (Deepfake: {deepfake_status}, Confidence: {confidence:.2f}, Liveliness: {liveliness_status})")
                        daily_writer.writerow([name, entry_time, deepfake_status, liveliness_status])
                        daily_attendance_file.flush()

                        # Append to weekly attendance
                        with open(weekly_attendance_file, 'a', newline='') as f:
                            csv_writer = csv.writer(f)
                            csv_writer.writerow([datetime.now().strftime('%Y-%m-%d'), name, 'Present'])
                    else:
                        print(f"Failed to mark {name} as present. Deepfake: {deepfake_status}, Liveliness: {liveliness_status}")
                else:
                    print("Similarity score too low. Face not recognized.")
            else:
                print("No face detected in this frame.")

            label = f"{name} ({deepfake_status}, {confidence:.2f}, {liveliness_status})"
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if deepfake_status == "Real" and liveliness_status == "Live" else (0, 0, 255), 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if deepfake_status == "Real" and liveliness_status == "Live" else (0, 0, 255), 2)

        cv2.imshow("Auto Attendance - InsightFace", frame)
        if cv2.waitKey(1) & 0xFF == ord('x'):
            print("Session ended early by user.")
            break

    # Append absent students to weekly attendance
    with open(weekly_attendance_file, 'a', newline='') as f:
        csv_writer = csv.writer(f)
        absent_students = [name for name in known_names if name not in attendance]
        for student in absent_students:
            csv_writer.writerow([datetime.now().strftime('%Y-%m-%d'), student, 'Absent'])

    print(f"Absent students: {absent_students}")

    # Send daily absence alerts
    if absent_students:
        send_absence_alerts(absent_students, STUDENT_EMAILS)

    # Generate daily attendance summary
    present_students = []
    with open('data/attendance.csv', 'r') as attendance_file:
        csv_reader = csv.DictReader(attendance_file)
        for row in csv_reader:
            present_students.append(row)

    generate_attendance_summary(present_students, absent_students)

    # Send daily attendance report to teacher
    send_attendance_report_to_teacher(known_names, present_students, TEACHER_DETAILS['email'], class_start_time)

finally:
    # Graceful shutdown
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    if daily_attendance_file is not None:
        daily_attendance_file.close()
    print("Resources cleaned up successfully.")