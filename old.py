from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys

class Window(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)
        self.setWindowTitle("TOOD")

        self.rack_layout = QHBoxLayout()
        self.rack_layout.setAlignment(Qt.AlignLeft)
        rack_container = DragDropContainer(self.rack_layout, "rack")

        rack_scroll = QScrollArea()
        rack_scroll.setWidget(rack_container)
        rack_scroll.setWidgetResizable(True)

        new_column_button = QPushButton("+")
        new_column_button.setFixedSize(35,85)
        new_column_button.clicked.connect(self.create_new_column)

        main_layout = QHBoxLayout()
        main_layout.addWidget(new_column_button)
        main_layout.addWidget(rack_scroll)

        self.widget = QWidget()
        self.widget.setLayout(main_layout)
        self.setCentralWidget(self.widget)
        self.showMaximized()

    def create_new_column(self):
        column = Column("[    ]")
        column.dropid = "rack"
        self.rack_layout.addWidget(column)
        column.title.edit.setFocus()

class DragDropContainer(QWidget):
    def __init__(self, layout : QBoxLayout, dropid="", *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setLayout(layout)
        self.layout = layout
        self.dropid = dropid

    def dragEnterEvent(self, e):
        if e.source().dropid == self.dropid:
            e.accept()

    def dropEvent(self, e):
        pos = e.pos()
        widget = e.source()
        dir = self.layout.direction()
        added = False
        for n in range(self.layout.count()):
            w = self.layout.itemAt(n).widget()
            is_dest = False
            if dir == QBoxLayout.LeftToRight:
                is_dest = pos.x() < w.x() + w.size().width()
            elif dir == QBoxLayout.RightToLeft:
                is_dest = pos.x() > w.x()
            elif dir == QBoxLayout.TopToBottom:
                is_dest = pos.y() < w.y()  + w.size().height()
            elif dir == QBoxLayout.BottomToTop:
                is_dest = pos.y() > w.y()
            if is_dest:
                self.layout.insertWidget(n, widget)
                added = True
                break
        if not added:
            self.layout.addWidget(widget)
        e.accept()

class DragDropItem(QFrame):
    def __init__(self, *args, **kwargs):
        super(QFrame, self).__init__(*args, **kwargs)
        self.dropid = ""

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            drag.setMimeData(mime)
            #pixmap = QPixmap(self.size())
            #self.render(pixmap)
            #drag.setPixmap(pixmap)
            drag.exec_(Qt.MoveAction)

class Task(DragDropItem):

    def __init__(self, name, *args, **kwargs):
        super(DragDropItem, self).__init__(*args, **kwargs)

        self.title = EditableText(name, 30)
        done_button = QPushButton("DONE!!!")
        done_button.clicked.connect(self.complete_task)
        cancel_button = QPushButton("x")
        cancel_button.clicked.connect(self.cancel_task)
        cancel_button.setFixedWidth(25)

        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self.title)
        top_row_layout.addWidget(cancel_button)
        top_row_layout.addWidget(done_button)

        v_layout = QVBoxLayout()
        v_layout.addLayout(top_row_layout)
        self.setLayout(v_layout)

        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setLineWidth(2)
        self.setFixedHeight(100)

    def complete_task(self):
        self.setParent(None)

    def cancel_task(self):
        self.setParent(None)


class Column(DragDropItem):

    def __init__(self, name, *args, **kwargs):
        super(DragDropItem, self).__init__(*args, **kwargs)

        self.title = EditableText(name, 30)
        new_task_button = QPushButton("+")
        new_task_button.setFixedSize(85,35)
        new_task_button.clicked.connect(self.create_new_task)

        cancel_button = QPushButton("x")
        cancel_button.clicked.connect(self.delete_column)
        cancel_button.setFixedWidth(25)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.title)
        header_layout.addWidget(cancel_button)
        header_layout.addWidget(new_task_button)

        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)
        container = DragDropContainer(self.container_layout, "column")

        scroll = QScrollArea()
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)

        v_layout = QVBoxLayout()
        v_layout.addLayout(header_layout)
        v_layout.addWidget(scroll)
        self.setLayout(v_layout)

        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setLineWidth(2)
        self.setFixedWidth(300)

    def create_new_task(self):
        task = Task("[    ]")
        task.dropid = "column"
        self.container_layout.addWidget(task)
        task.title.edit.setFocus()

    def delete_column(self):
        self.setParent(None)

class EditableText(QStackedWidget):
    def __init__(self, text, height, *args, **kwargs):
        super(QStackedWidget, self).__init__(*args, **kwargs)

        self.label = QLabel(text)
        self.edit = self.DefocusLineEditFix(text)
        self.addWidget(self.label)
        self.addWidget(self.edit)
        self.edit.focus_lost.connect(lambda: self.setMode(False))
        self.edit.returnPressed.connect(lambda: self.setMode(False))
        self.setFixedHeight(height)
        self.setMode(True)

    class DefocusLineEditFix(QLineEdit):
        focus_lost = pyqtSignal()
        def focusOutEvent(self, event):
            self.focus_lost.emit()

    def mouseDoubleClickEvent(self, event):
        if self.currentWidget() == self.label:
            self.setMode(True)

    def setMode(self, toEdit):
        if toEdit:
            self.setCurrentWidget(self.edit)
            self.edit.selectAll()
            self.edit.setFocus()
        else:
            self.label.setText(self.edit.text())
            self.setCurrentWidget(self.label)



app = QApplication(sys.argv)
window = Window()
window.show()
app.exec_()
