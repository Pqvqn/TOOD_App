
# for i in range(5):
#     bit = input()
#     print("received", i, ":", bit, "!")
# input()
import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton, QHBoxLayout, QWidget


class PetView(QMainWindow):

    def __init__(self):
        super(QMainWindow, self).__init__()

        text_input = QLineEdit()
        submit_button = QPushButton("GO")
        submit_button.clicked.connect(lambda: print(text_input.text(), flush=True))

        h_layout = QHBoxLayout()
        h_layout.addWidget(text_input)
        h_layout.addWidget(submit_button)

        self.widget = QWidget()
        self.widget.setLayout(h_layout)
        self.setCentralWidget(self.widget)

class App(QApplication):

    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)

        self.view = PetView()
        self.view.show()

if __name__ == '__main__':
    app = App(sys.argv)
    sys.exit(app.exec())
