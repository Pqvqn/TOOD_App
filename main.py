import sys

from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget

from model import Model
from controller import Controller
from view import View

class App(QApplication):
    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)

        #opener = QWidget()
        #get_file = QFileDialog.getOpenFileName(opener, "Open File", QDir.homePath(), "TOOD file (*.tood)")

        self.model = Model() # get_file)
        self.controller = Controller(self.model)
        self.view = View(self.controller)
        self.controller.register_view(self.view)

        self.view.show()

if __name__ == '__main__':
    app = App(sys.argv)
    sys.exit(app.exec_())
