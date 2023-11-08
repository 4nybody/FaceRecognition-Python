from PyQt5.QtGui import QImage, QPixmap
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSlot, QTimer, QDate
from PyQt5.QtWidgets import QDialog, QMessageBox
import cv2
import face_recognition
import numpy as np
import datetime
import os
import csv
import sqlite3

class Ui_OutputDialog(QDialog):
    def __init__(self):
        super(Ui_OutputDialog, self).__init__()
        loadUi("outputwindow.ui", self)

        now = QDate.currentDate()
        current_date = now.toString('ddd dd MMMM yyyy')
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        self.Date_Label.setText(current_date)
        self.Time_Label.setText(current_time)

        self.image = None
        self.conn = sqlite3.connect("attendance.db")
        self.create_tables()

        self.ClockInButton.clicked.connect(self.on_clockInButton_clicked)
        self.ClockOutButton.clicked.connect(self.on_clockOutButton_clicked)

        self.class_names = []
        self.TimeList1 = []  # Initialize TimeList1 and TimeList2
        self.TimeList2 = []

        self.clock_in_status = False  # To track if the user is currently clocked in
        self.user_name = ""  # To store the name of the user

    @pyqtSlot()
    def startVideo(self, camera_name):
        if len(camera_name) == 1:
            self.capture = cv2.VideoCapture(int(camera_name))
        else:
            self.capture = cv2.VideoCapture(camera_name)

        self.timer = QTimer(self)
        path = 'ImagesAttendance'
        if not os.path.exists(path):
            os.mkdir(path)

        images = []
        self.encode_list = []
        attendance_list = os.listdir(path)

        for cl in attendance_list:
            cur_img = cv2.imread(f'{path}/{cl}')
            images.append(cur_img)
            self.class_names.append(os.path.splitext(cl)[0])

        for img in images:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(img)
            encodes_cur_frame = face_recognition.face_encodings(img, boxes)[0]
            self.encode_list.append(encodes_cur_frame)

        self.timer.timeout.connect(self.update_frame)
        self.timer.start(10)

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                date_time DATETIME,
                action TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        self.conn.commit()

    def create_user(self, name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (?, ?)", (name, name))
        self.conn.commit()

    @pyqtSlot()
    @pyqtSlot()
    def on_clockInButton_clicked(self):
        # Handle Clock In button click
        if not self.clock_in_status:
            date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
            cursor = self.conn.cursor()
            if self.class_names:
                user_id = self.class_names[0]  # Assuming there is only one recognized user
                cursor.execute("INSERT INTO attendance (user_id, date_time, action) VALUES (?, ?, ?)",
                               (user_id, date_time_string, "Clock In"))
                self.conn.commit()
                with open('Attendance.csv', 'a') as f:
                    cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
                    user_name = cursor.fetchone()
                    if user_name:
                        user_name = user_name[0]
                    else:
                        user_name = 'Not in database'
                    buttonReply = QMessageBox.question(self, 'Welcome ' + user_name, 'Are you Clocking In?',
                                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if buttonReply == QMessageBox.Yes:
                        f.writelines(f'\n{user_id},{date_time_string},Clock In')
                        self.ClockInButton.setChecked(False)
                        self.NameLabel.setText(user_name)  # Set the user's name in the NameLabel
                        self.StatusLabel.setText('Clocked In')
                        self.HoursLabel.setText('Measuring')
                        self.MinLabel.setText('')
                        self.Time1 = datetime.datetime.now()
                        self.clock_in_status = True
                        self.user_name = user_name  # Store the user's name
                        self.ClockInButton.setEnabled(True)
                    else:
                        self.ClockInButton.setChecked(False)
                        self.ClockInButton.setEnabled(True)
            else:
                # User is not recognized
                user_name = 'Not in database'
                buttonReply = QMessageBox.question(self, 'Welcome ' + user_name, 'Are you Clocking In?',
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if buttonReply == QMessageBox.Yes:
                    self.ClockInButton.setChecked(False)
                    self.NameLabel.setText(user_name)  # Set the user's name in the NameLabel
                    self.StatusLabel.setText('Clocked In')
                    self.HoursLabel.setText('Measuring')
                    self.MinLabel.setText('')
                    self.Time1 = datetime.datetime.now()
                    self.clock_in_status = True
                    self.user_name = user_name  # Store the user's name
                    self.ClockInButton.setEnabled(True)
                else:
                    self.ClockInButton.setChecked(False)
                    self.ClockInButton.setEnabled(True)

    @pyqtSlot()
    def on_clockOutButton_clicked(self):
        # Handle Clock Out button click
        if self.clock_in_status:
            date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
            cursor = self.conn.cursor()
            user_name = self.user_name
            user_id = user_name
            cursor.execute("INSERT INTO attendance (user_id, date_time, action) VALUES (?, ?, ?)",
                           (user_id, date_time_string, "Clock Out"))
            self.conn.commit()
            with open('Attendance.csv', 'a') as f:
                buttonReply = QMessageBox.question(self, 'Cheers ' + user_name, 'Are you Clocking Out?',
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if buttonReply == QMessageBox.Yes:
                    date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
                    f.writelines(f'\n{user_name},{date_time_string},Clock Out')
                    self.ClockOutButton.setChecked(False)
                    self.NameLabel.setText(user_name)
                    self.StatusLabel.setText('Clocked Out')
                    self.Time2 = datetime.datetime.now()
                    self.elapse_list(user_name)
                    self.TimeList2.append(datetime.datetime.now())
                    check_in_time = self.TimeList1[-1]
                    check_out_time = self.TimeList2[-1]
                    elapse_hours = (check_out_time - check_in_time)
                    self.MinLabel.setText(
                        "{:.0f}".format(abs(elapse_hours.total_seconds() / 60) % 60) + 'm')
                    self.HoursLabel.setText(
                        "{:.0f}".format(abs(elapse_hours.total_seconds() / 3600)) + 'h')
                    self.clock_in_status = False
                    self.ClockOutButton.setEnabled(True)
        else:
            QMessageBox.warning(self, 'Not Clocked In', 'You are not clocked in.')

    def face_rec_(self, frame):
        faces_cur_frame = face_recognition.face_locations(frame)
        encodes_cur_frame = face_recognition.face_encodings(frame, faces_cur_frame)
        for encodeFace, faceLoc in zip(encodes_cur_frame, faces_cur_frame):
            match = face_recognition.compare_faces(self.encode_list, encodeFace, tolerance=0.50)
            face_dis = face_recognition.face_distance(self.encode_list, encodeFace)
            name = "unknown"
            best_match_index = np.argmin(face_dis)
            if match[best_match_index]:
                user_name = self.class_names[best_match_index].upper()
                y1, x2, y2, x1 = faceLoc
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(frame, (x1, y2 - 20), (x2, y2), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, user_name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
        return frame

    def elapse_list(self, user_name):
        try:
            with open('Attendance.csv', "r") as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                Time1 = None
                Time2 = None
                for row in csv_reader:
                    if row and len(row) >= 3:
                        name = row[0]
                        date_time = row[1]
                        action = row[2]
                        if name == user_name:
                            if action == 'Clock In':
                                Time1 = datetime.datetime.strptime(date_time, '%y/%m/%d %H:%M:%S')
                            elif action == 'Clock Out':
                                Time2 = datetime.datetime.strptime(date_time, '%y/%m/%d %H:%M:%S')

                if Time1 is not None and Time2 is not None:
                    self.TimeList1.append(Time1)
                    self.TimeList2.append(Time2)
        except Exception as e:
            print(f"Error in elapse_list: {e}")

    def update_frame(self):
        try:
            ret, self.image = self.capture.read()
            self.displayImage(self.image)
        except Exception as e:
            print(f"Error in update_frame: {e}")

    def displayImage(self, image, window=1):
        try:
            if image is not None:
                image = cv2.resize(image, (640, 480))
                image = self.face_rec_(image)
                qformat = QImage.Format_Indexed8
                if len(image.shape) == 3:
                    if image.shape[2] == 4:
                        qformat = QImage.Format_RGBA8888
                    else:
                        qformat = QImage.Format_RGB888
                outImage = QImage(image, image.shape[1], image.shape[0], image.strides[0], qformat)
                outImage = outImage.rgbSwapped()

                if window == 1:
                    self.imgLabel.setPixmap(QPixmap.fromImage(outImage))
                    self.imgLabel.setScaledContents(True)
        except Exception as e:
            print(f"Error in displayImage: {e}")

if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = Ui_OutputDialog()
    window.show()
    sys.exit(app.exec_())
