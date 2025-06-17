import csv
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load student emails from students.csv
STUDENT_EMAILS = {}
try:
    with open('data/students.csv', 'r') as email_file:
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
except FileNotFoundError:
    logger.error("data/students.csv file not found")
    exit(1)

# Load sender credentials from sender_credentials.csv
try:
    with open('data/sender_credentials.csv', 'r') as sender_file:
        csv_reader = csv.DictReader(sender_file)
        sender_data = next(csv_reader)
        SENDER_EMAIL = sender_data['Email']
        SENDER_APP_PASSWORD = sender_data['AppPassword']
except FileNotFoundError:
    logger.error("data/sender_credentials.csv file not found")
    exit(1)
except KeyError as e:
    logger.error(f"Missing column {e} in data/sender_credentials.csv")
    exit(1)

# Load teacher details from teachers.csv to get max_classes
TEACHER_DETAILS = {}
try:
    with open('data/teachers.csv', 'r') as teacher_file:
        csv_reader = csv.DictReader(teacher_file)
        if not csv_reader.fieldnames:
            logger.error("data/teachers.csv is empty or has no header row")
            exit(1)
        logger.info(f"Columns found in teachers.csv: {csv_reader.fieldnames}")
        
        max_classes_column = None
        for field in csv_reader.fieldnames:
            if field.lower() == 'max classes':
                max_classes_column = field
                break

        if not max_classes_column:
            logger.error("'Max Classes' column not found in data/teachers.csv")
            exit(1)

        teacher_data = next(csv_reader)
        TEACHER_DETAILS = {
            'max_classes': int(teacher_data[max_classes_column])
        }
except FileNotFoundError:
    logger.error("data/teachers.csv file not found")
    exit(1)
except KeyError as e:
    logger.error(f"Missing column {e} in data/teachers.csv")
    exit(1)

weekly_attendance_file = 'data/weekly_attendance.csv'

def send_weekly_attendance_report(students_emails, max_classes):
    known_names = set()
    try:
        with open(weekly_attendance_file, 'r') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                known_names.add(row['Name'])
    except FileNotFoundError:
        logger.error("weekly_attendance.csv not found. No weekly report generated")
        return

    attendance_records = {}
    for student in known_names:
        attendance_records[student] = {'present': 0, 'total_sessions': 0}

    try:
        with open(weekly_attendance_file, 'r') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                name = row['Name']
                status = row['Status']
                if name in attendance_records:
                    attendance_records[name]['total_sessions'] += 1
                    if status == 'Present':
                        attendance_records[name]['present'] += 1
    except FileNotFoundError:
        logger.error("weekly_attendance.csv not found. No weekly report generated")
        return

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)

        for student, email in students_emails.items():
            if student not in attendance_records:
                continue
            present_count = attendance_records[student]['present']
            total_sessions = max_classes
            attendance_percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0

            if attendance_percentage < 50:
                message = "Your attendance is quite low. Please try to attend more classes to improve your participation."
            elif attendance_percentage < 80:
                message = "You're attending some classes, but there's room for improvement. Aim to attend more sessions."
            else:
                message = "Great job! You're attending most classes. Keep up the good work!"

            subject = "Weekly Attendance Report - AutoAttendanceYOLO"
            body = f"""
            Dear {student},

            Here is your weekly attendance report as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST:

            - Classes Attended: {present_count} out of {total_sessions}
            - Attendance Percentage: {attendance_percentage:.2f}%

            {message}

            Regards,
            AutoAttendance System
            """

            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            logger.info(f"Sent weekly attendance report to {student} at {email}")

        server.quit()
    except Exception as e:
        logger.error(f"Error sending weekly attendance reports: {e}")
        return

    with open(weekly_attendance_file, 'w', newline='') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['Date', 'Name', 'Status'])
    logger.info("Reset weekly_attendance.csv for the next week")

# Main loop with improved timing logic
last_report_time = None
while True:
    current_time = datetime.now()
    current_day = current_time.strftime('%A')
    current_hour = current_time.hour
    current_minute = current_time.minute

    # Check if it's Sunday between 22:40 and 22:41
    if (current_day == 'Sunday' and current_hour == 22 and 40 <= current_minute <= 41):
        # Ensure the report is sent only once per week
        if last_report_time is None or (current_time - last_report_time).days >= 7:
            logger.info(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Sending weekly attendance report")
            send_weekly_attendance_report(STUDENT_EMAILS, TEACHER_DETAILS['max_classes'])
            last_report_time = current_time
    else:
        logger.debug(f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Waiting for Sunday 10:40 PM to send weekly report")

    time.sleep(30)  # Check every 30 seconds