import re
import fileinput

def replace_in_file(file_path: object, old_string: object, new_string: object) -> object:
    with fileinput.FileInput(file_path, inplace=True, backup='.bak') as file:
        for line in file:
            print(re.sub(old_string, new_string, line), end='')

replace_in_file("out_window.py", "on_clockButton_clicked", "on_clockInButton_clicked")
