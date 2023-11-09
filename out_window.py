from PyQt5.QtGui import QImage, QPixmap
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSlot, QTimer, QDate
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5 import QtWidgets  # Add this line
import cv2
import face_recognition
import numpy as np
import datetime
import os
import csv
import sqlite3


class Ui_OutputDialog(QDialog):
    recognized_user_id = None

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

        self.user_clock_in_status_dict = {}
        self.TimeList1 = {}  # Initialize TimeList1 as an empty dictionary
        self.TimeList2 = {}

        self.ClockInButton.clicked.connect(self.on_clockInButton_clicked)
        self.ClockOutButton.clicked.connect(self.on_clockOutButton_clicked)

        self.class_names = []
        self.clock_in_status = False
        self.user_name = ""
        self.clock_in_pending = False

        self.startVideo("your_camera_name")

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

        self.class_names = []

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM users")
        user_ids = cursor.fetchall()
        self.class_names = [str(user_id[0]) for user_id in user_ids]

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
    def on_clockInButton_clicked(self):
        if not self.clock_in_status:
            recognized_user_name = self.get_user_name_by_id(self.recognized_user_id)

            if recognized_user_name:
                if self.user_clock_in_status_dict.get(recognized_user_name, False):
                    QMessageBox.warning(self, 'Clock In Error', f'{recognized_user_name} has already clocked in.')
                    return

                date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO attendance (user_id, date_time, action) VALUES (?, ?, ?)",
                               (recognized_user_name, date_time_string, "Clock In"))
                self.conn.commit()

                with open('Attendance.csv', 'a') as f:
                    buttonReply = QMessageBox.question(self, 'Welcome ' + recognized_user_name, 'Are you Clocking In?',
                                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if buttonReply == QMessageBox.Yes:
                        f.writelines(f'\n{recognized_user_name},{date_time_string},Clock In')
                        self.ClockInButton.setChecked(False)
                        self.StatusLabel.setText('Clocked In')
                        self.HoursLabel.setText('Measuring')
                        self.MinLabel.setText('')

                        # Record the current time when the user clocks in again
                        self.Time1 = datetime.datetime.now()

                        self.user_name = recognized_user_name
                        self.user_clock_in_status_dict[recognized_user_name] = True
                        self.clock_in_status = True  # Set the overall clock-in status to True
                        self.ClockInButton.setEnabled(True)
                    else:
                        self.ClockInButton.setChecked(False)
                        self.ClockInButton.setEnabled(True)
            else:
                QMessageBox.warning(self, 'Recognition Error', 'Unable to recognize the user for Clock In.')
                self.ClockInButton.setChecked(False)
                self.ClockInButton.setEnabled(True)
        else:
            self.clock_in_status = False

    @pyqtSlot()
    def on_clockOutButton_clicked(self):
        recognized_user_name = self.get_user_name_by_id(self.recognized_user_id)

        if recognized_user_name:
            if self.user_clock_in_status_dict.get(recognized_user_name, False):
                date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO attendance (user_id, date_time, action) VALUES (?, ?, ?)",
                               (recognized_user_name, date_time_string, "Clock Out"))
                self.conn.commit()

                with open('Attendance.csv', 'a') as f:
                    buttonReply = QMessageBox.question(self, 'Cheers ' + recognized_user_name, 'Are you Clocking Out?',
                                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if buttonReply == QMessageBox.Yes:
                        date_time_string = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
                        f.writelines(f'\n{recognized_user_name},{date_time_string},Clock Out')
                        self.ClockOutButton.setChecked(False)
                        self.StatusLabel.setText('Clocked Out')
                        self.Time2 = datetime.datetime.now()
                        self.elapse_list(recognized_user_name)

                        if recognized_user_name in self.TimeList1:
                            check_in_time = self.TimeList1[recognized_user_name]
                            check_out_time = self.Time2  # Use the current time for check-out

                            print(
                                f'Clocked out: {recognized_user_name}, Time1: {check_in_time}, Time2: {check_out_time}')

                            elapse_hours, minutes = divmod((check_out_time - check_in_time).total_seconds(), 3600)
                            minutes //= 60
                            print(f'Clocked in: {recognized_user_name}, Time1: {self.TimeList1[recognized_user_name]}')

                            self.MinLabel.setText("{:.0f}".format(minutes) + 'm')
                            self.HoursLabel.setText("{:.0f}".format(elapse_hours) + 'h')
                            print(f'Set labels: Minutes: {minutes}, Hours: {elapse_hours}')

                            # Reset the dictionary when the user clocks out
                            self.user_clock_in_status_dict.pop(recognized_user_name, None)
                            self.TimeList1.pop(recognized_user_name, None)

                            # Force GUI update
                            QtWidgets.QApplication.processEvents()

                        else:
                            print(f'Clocked out: {recognized_user_name}, Time1 not found.')
                            self.MinLabel.setText('')
                            self.HoursLabel.setText('')
                        self.user_clock_in_status_dict.pop(recognized_user_name, None)
                        self.clock_in_status = False  # Reset the overall clock-in status
                        self.ClockOutButton.setEnabled(True)
                    else:
                        self.ClockOutButton.setChecked(False)
                        self.ClockOutButton.setEnabled(True)
            else:
                QMessageBox.warning(self, 'Clock Out Error', f'{recognized_user_name} has not clocked in.')
        else:
            QMessageBox.warning(self, 'Recognition Error', 'Unable to recognize the user for Clock Out.')
            self.ClockOutButton.setChecked(False)
            self.ClockOutButton.setEnabled(True)

    def face_rec_(self, frame):
        faces_cur_frame = face_recognition.face_locations(frame)
        encodes_cur_frame = face_recognition.face_encodings(frame, faces_cur_frame)

        recognized_user_id = None

        for encodeFace, faceLoc in zip(encodes_cur_frame, faces_cur_frame):
            match = face_recognition.compare_faces(self.encode_list, encodeFace, tolerance=0.50)
            face_dis = face_recognition.face_distance(self.encode_list, encodeFace)
            name = "unknown"
            best_match_index = np.argmin(face_dis)

            if match[best_match_index]:
                recognized_user_id = self.class_names[best_match_index]
                self.recognized_user_id = recognized_user_id

                recognized_user_name = self.get_user_name_by_id(recognized_user_id)

                (top, right, bottom, left) = faceLoc
                if recognized_user_name:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.rectangle(frame, (left, bottom - 20), (right, bottom), (0, 255, 0), cv2.FILLED)
                    cv2.putText(frame, recognized_user_name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_COMPLEX, 0.5,
                                (255, 255, 255), 1)

                    self.user_name = recognized_user_name
                    self.NameLabel.setText(recognized_user_name)

                    if self.clock_in_status and self.user_name == recognized_user_name:
                        self.StatusLabel.setText('Clocked In')
                        self.HoursLabel.setText('Measuring')
                        self.MinLabel.setText('')
                        self.Time1 = datetime.datetime.now()
                    elif self.user_clock_in_status_dict.get(recognized_user_name, False):
                        self.StatusLabel.setText('Clocked In')
                        self.HoursLabel.setText('Measuring')
                        self.MinLabel.setText('')
                    else:
                        self.StatusLabel.setText('Not Clocked In')
                        self.HoursLabel.setText('')
                        self.MinLabel.setText('')
                        self.Time1 = None

                break

        return frame

    def get_user_name_by_id(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()

        if user_data:
            return user_data[0]
        else:
            return 'Unknown'

    def elapse_list(self, user_name):
        try:
            with open('Attendance.csv', "r") as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                Time1 = None
                Time2 = None
                for row in csv_reader:
                    print(row)  # Add this line to see the content of each row
                    if row and len(row) >= 3:
                        name = row[0]
                        date_time = row[1]
                        action = row[2]
                        if name == user_name:
                            if action == 'Clock In':
                                Time1 = datetime.datetime.strptime(date_time, '%y/%m/%d %H:%M:%S')
                                self.TimeList1[user_name] = Time1  # Update TimeList1 when the user clocks in
                            elif action == 'Clock Out':
                                Time2 = datetime.datetime.strptime(date_time, '%y/%m/%d %H:%M:%S')

                if Time1 is None and Time2 is not None:
                    Time1 = datetime.datetime.now()
                if Time1 is not None and Time2 is not None:
                    self.TimeList1[user_name] = Time1
                    self.TimeList2[user_name] = Time2
        except Exception as e:
            print(f"Error in elapse_list: {e}")

    def update_frame(self):
        try:
            ret, self.image = self.capture.read()

            if ret:
                self.image = self.face_rec_(self.image)
                self.displayImage(self.image)
        except Exception as e:
            print(f"Error in update_frame: {e}")

    def displayImage(self, image, window=1):
        try:
            if image is not None:
                image = cv2.resize(image, (640, 480))
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