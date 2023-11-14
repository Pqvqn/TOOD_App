from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QEvent, QDateTime, QDir, QSize, QTime
from PyQt5.QtGui import QDrag, QPixmap
from PyQt5.QtWidgets import QMainWindow, QPushButton, QScrollArea, QHBoxLayout, QWidget, QFrame, \
    QVBoxLayout, QStackedWidget, QLabel, QLineEdit, QCheckBox, QGroupBox, QGridLayout, QMessageBox, \
    QDoubleSpinBox, QDateTimeEdit, QFileDialog, QSizePolicy, QApplication, QComboBox


class View(QMainWindow):
    clicked_out_of_edit = pyqtSignal()

    def __init__(self, controller):
        super(QMainWindow, self).__init__()

        self.controller = controller

        # create UI
        self.setWindowTitle("TOOD")

        self.rack = Rack(self)

        new_shelf_button = QPushButton("+")
        new_shelf_button.setFixedSize(150, 100)

        debug_button = QPushButton("debug print")
        debug_button.setFixedSize(150, 75)

        load_tood_button = QPushButton("LOAD .TOOD")
        save_tood_button = QPushButton("SAVE .TOOD")
        options_grid = QGridLayout()
        options_grid.addWidget(load_tood_button, 1, 1)
        options_grid.addWidget(save_tood_button, 1, 2)

        self.stage = Stage(self)

        self.custom_fields = FieldControl(self)

        left_sidebar = QGroupBox()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(self.stage)
        sidebar_layout.addWidget(self.custom_fields)
        sidebar_layout.addWidget(new_shelf_button, alignment=Qt.AlignHCenter)
        sidebar_layout.addWidget(debug_button, alignment=Qt.AlignHCenter)
        sidebar_layout.addLayout(options_grid)
        left_sidebar.setLayout(sidebar_layout)
        left_sidebar.setFixedWidth(320)

        main_layout = QHBoxLayout()
        main_layout.addWidget(left_sidebar)
        main_layout.addWidget(self.rack)

        self.widget = QWidget()
        self.widget.setLayout(main_layout)
        self.setCentralWidget(self.widget)
        self.showMaximized()

        # event filtering for clicks
        debug_button.installEventFilter(self)
        new_shelf_button.installEventFilter(self)
        load_tood_button.installEventFilter(self)
        save_tood_button.installEventFilter(self)

        # connect inputs to controller
        debug_button.pressed.connect(self.controller.debug_print)
        new_shelf_button.pressed.connect(self.controller.new_shelf_in_rack)
        self.clicked_out_of_edit.connect(self.controller.widget_edit_ended)
        load_tood_button.pressed.connect(lambda: self.controller.load_tood(
            QFileDialog.getOpenFileName(self, "Open File", QDir.homePath(), "TOOD file (*.tood)")[0]))
        save_tood_button.pressed.connect(lambda: self.controller.save_tood(
            QFileDialog.getSaveFileName(self, "Save File", QDir.homePath(), "TOOD file (*.tood)")[0]))

    # methods to detect clicking out of selected widget
    def process_click_during_edit(self, pos):
        within_highlight = False
        # test if click was within the currently edited widget but not its children
        widg = self.controller.widget_being_edited
        if widg.underMouse() and not any(x.underMouse() for x in widg.get_children()):
            within_highlight = True
        else:
            # repeat check for other instances of the widget
            for wid in self.controller.edit_instances:
                if wid.underMouse() and not any(x.underMouse() for x in wid.get_children()):
                    within_highlight = True
                    break
        # if clicked out of a highlighted widget, emit signal to close edit mode
        if not within_highlight:
            self.clicked_out_of_edit.emit()

    def mousePressEvent(self, event):
        if self.controller.widget_being_edited is not None:
            self.process_click_during_edit(event.pos())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if self.controller.widget_being_edited is not None:
                self.process_click_during_edit(event.pos())

        return False

    # displays a custom warning box
    def show_warning(self, text):
        QMessageBox.warning(self, "Warning", text)


class Task(QFrame):

    def __init__(self, view, owner, df_id, **info):
        super(QFrame, self).__init__()
        self.view = view
        self.owner = owner
        self.df_id = df_id
        self.setObjectName("Task" + str(self.df_id))

        # added padding when going from lower level up to this one
        self.nest_offset = 28

        # set as tuple when being dragged so action can be undone
        self.undo = None
        self.dragStartPosition = None

        # formatting for incomplete and complete button
        self.button_styles = ("border-radius : 10; border : 2px solid gray; background-color : white",
                              "border-radius : 10; background-color : green; color : white")

        # create UI
        self.title = EditableText("", 15)
        self.done_button = QPushButton()
        self.done_button.setFixedSize(20, 20)
        cancel_button = QPushButton("x")
        cancel_button.setFixedSize(15, 15)
        cancel_button.setFlat(True)
        self.due_label = QLabel("Due:")
        self.due_edit = EditableDate(None, 15)
        self.value_label = QLabel("Value:")
        self.value_edit = EditableSpin(0, 15)

        new_shelf_button = QPushButton("+")
        new_shelf_button.setFixedSize(40, 20)

        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container = QFrame()
        self.container.setLayout(self.container_layout)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)

        self.child_indicator = QFrame()
        self.child_indicator.setFrameShape(QFrame.NoFrame)
        self.child_indicator.setFixedHeight(8)

        self.collapse_tree = CollapseGrid(False)
        self.collapse_tree.add_child(new_shelf_button, (0, 4), None, align=Qt.AlignRight)
        self.collapse_tree.add_child(self.container, (1, 0, 1, 5), None)
        self.collapse_tree.add_child(self.child_indicator, None, (0, 1, 1, 3), align=Qt.AlignVCenter)

        id_label = QLabel(str(self.df_id))
        id_label.setStyleSheet("color: gray; font: italic")

        expanded = info["label"] == "///"
        collapse_grid = CollapseGrid(expanded)
        collapse_grid.add_child(self.title, (0, 1, 1, 4), (0, 1, 1, 2), align=Qt.AlignLeft)
        collapse_grid.add_child(self.done_button, (1, 4, 1, 2), (0, 3, 1, 2))
        collapse_grid.add_child(cancel_button, (0, 5, 1, 1), (0, 5, 1, 1))
        collapse_grid.add_child(self.due_label, (1, 1, 1, 1), None)
        collapse_grid.add_child(self.due_edit, (1, 2, 1, 2), None)
        collapse_grid.add_child(self.value_label, (2, 1, 1, 1), None)
        collapse_grid.add_child(self.value_edit, (2, 2, 1, 2), None)

        collapse_grid.add_child(self.collapse_tree, (3, 0, 2, 6), (1, 0, 1, 6))
        collapse_grid.add_child(id_label, (5, 0, 1, 3), None, align=Qt.AlignBottom)

        v_layout = QVBoxLayout()
        v_layout.addWidget(collapse_grid)
        self.setLayout(v_layout)

        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setLineWidth(2)
        self.set_edit_look(False)
        self.edit_fields(info)

        self.check_width()
        self.setAcceptDrops(True)

        # event filtering for clicks
        self.installEventFilter(self.view)
        self.done_button.installEventFilter(self.view)
        cancel_button.installEventFilter(self.view)
        new_shelf_button.installEventFilter(self.view)

        # update width when tree collapsed
        self.collapse_tree.collapse_toggled.connect(self.check_width)

        # connect inputs to controller
        new_shelf_button.pressed.connect(lambda: self.view.controller.new_shelf_in_task(self))
        cancel_button.pressed.connect(lambda: self.view.controller.task_removed(self))
        self.done_button.pressed.connect(
            lambda: self.view.controller.direct_field_change(self, ("completed", self.done_button.text() != "✔")))

        self.title.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "title"))
        self.due_edit.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "due_edit"))
        self.value_edit.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "value_edit"))
        self.title.edit_updated.connect(lambda x: self.view.controller.widget_field_changed(self, ("label", x)))
        self.due_edit.edit_updated.connect(lambda x: self.view.controller.widget_field_changed(self, ("due", x)))
        self.value_edit.edit_updated.connect(lambda x: self.view.controller.widget_field_changed(self, ("value", x)))

    # set width to accomodate children and update parent if width changes
    def check_width(self):
        max_wid = 0
        if not self.collapse_tree.state:
            # minimize width if tress is collapsed
            max_wid = 0
        else:
            # find minimum necessary width to contain children
            for i in range(self.container_layout.count()):
                wid = self.container_layout.itemAt(i).widget().size().width()
                if wid > max_wid:
                    max_wid = wid
        # if width changes, update parent widths
        if max_wid + self.nest_offset != self.size().width():
            self.setFixedWidth(max(max_wid + self.nest_offset, 222 + self.nest_offset))
            if isinstance(self.owner, Shelf):
                self.owner.check_width()

    # sets whether the task is highlighted for edit mode
    def set_edit_look(self, to_edit):
        if to_edit:
            self.setStyleSheet("""
                Task{
                    border: 2.5px solid blue;
                }
                """)
        else:
            self.setStyleSheet("""
                Task{
                    border: 1px solid black;
                }
                """)

    # update widget values to reflect change in model
    def edit_fields(self, edit_dict):
        if "label" in edit_dict:
            self.title.set_state(edit_dict["label"])
        if "completed" in edit_dict:
            self.done_button.setText("✔" if edit_dict["completed"] else "")
            self.done_button.setStyleSheet(self.button_styles[1 if edit_dict["completed"] else 0])
        if "due" in edit_dict:
            self.due_edit.set_state(None if edit_dict["due"] is None else str(edit_dict["due"]))
        if "value" in edit_dict:
            self.value_edit.set_state(edit_dict["value"], label=False)
            self.value_edit.set_state(str(edit_dict["value"]), edit=False)

        # update summary of data in this task for hover
        self.setToolTip(f"<p style='white-space:pre'><b>{self.title.label.text()}</b> {self.done_button.text()}\n"
                        f"Due at {self.due_edit.label.text()}</p>")

    # close all open edit widgets
    def close_fields(self):
        self.title.set_mode(False)
        self.due_edit.set_mode(False)
        self.value_edit.set_mode(False)

    def set_owner(self, o):
        self.owner = o

    def add_child(self, child):
        child.set_owner(self)
        self.container_layout.addWidget(child)
        if self.container_layout.count() == 1:
            self.child_indicator.setFrameShape(QFrame.Box)
        self.check_width()

    def insert_child(self, child, pos):
        child.set_owner(self)
        self.container_layout.insertWidget(pos, child)
        if self.container_layout.count() == 1:
            self.child_indicator.setFrameShape(QFrame.Box)
        self.check_width()

    def remove_child(self, child):
        child.set_owner(None)
        self.container_layout.removeWidget(child)
        child.setParent(None)
        if self.container_layout.count() == 0:
            self.child_indicator.setFrameShape(QFrame.NoFrame)
        self.check_width()

    def get_child(self, idx):
        return self.container_layout.itemAt(idx).widget()

    def get_children(self):
        return [self.container_layout.itemAt(i).widget() for i in range(self.container_layout.count())]

    def mousePressEvent(self, e):
        b = e.buttons()
        if b == Qt.LeftButton or b == Qt.RightButton or b == Qt.MiddleButton:
            # track beginning of mouse hold and only start drag when it goes far enough
            self.dragStartPosition = e.pos()

    def mouseReleaseEvent(self, e):
        # reset drag start once released
        self.dragStartPosition = None

    def mouseMoveEvent(self, e):
        b = e.buttons()

        # only process dragging while button held
        if not(b == Qt.LeftButton or b == Qt.RightButton or b == Qt.MiddleButton):
            return

        # dont do drag if start position not set
        if self.dragStartPosition is None:
            return

        # only process dragging once the mouse has moved far enough
        if (e.pos() - self.dragStartPosition).manhattanLength() < QApplication.startDragDistance() * 6:
            return

        # handle drag
        drag = QDrag(self)

        # have image of this task follow the cursor
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)

        # duplicate task into new task
        if b == Qt.MiddleButton:
            dupe = self.view.controller.duplicate_task_id(self.df_id)
            self.undo = (b, dupe)

            mime = QMimeData()
            mime.setText(dupe)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)
        # creates a new reference to this task
        elif b == Qt.RightButton:
            self.undo = (b,)

            mime = QMimeData()
            drag.setMimeData(mime)
            mime.setText(self.df_id)
            drag.exec_(Qt.LinkAction)
        # move the reference to this task
        elif b == Qt.LeftButton:
            self.undo = (b, self.owner,
                         self.owner.container_layout.indexOf(self)+1 if isinstance(self.owner, Shelf) else 0)
            self.view.controller.task_removed(self)

            mime = QMimeData()
            drag.setMimeData(mime)
            mime.setText(self.df_id)
            drag.exec_(Qt.MoveAction)

    # reverses changes made when initializing a drag in case drop fails
    def undo_drag(self):
        # if duplicated, delete the newly created task
        if self.undo[0] == Qt.MiddleButton:
            self.view.controller.erase_task_id(self.undo[1])
        # nothing needs to be done to undo reference copy
        elif self.undo[0] == Qt.RightButton:
            pass
        # if moved, place the task back in the original location
        elif self.undo[0] == Qt.LeftButton:
            if isinstance(self.undo[1], Shelf):
                self.view.controller.insert_task_id_in_shelf(self.df_id, self.undo[1], self.undo[2])
            elif isinstance(self.undo[1], Stage):
                self.view.controller.set_task_id_in_stage(self.df_id)
        self.undo = None

    # accept dragged shelves or shelf ids
    def dragEnterEvent(self, e):
        if e.mimeData().text()[0] == 's' or isinstance(e.source(), Shelf):
            e.accept()

    # handle placement of dropped shelves
    def dropEvent(self, e):
        pos = e.pos()
        widget = e.source()
        added = False
        shelf_id = e.mimeData().text()

        # undo drag and drop if shelf is already in this task
        if self.view.controller.is_shelf_id_in_task(shelf_id, self):
            if widget is not None:
                widget.undo_drag()
        # place the dropped shelf
        else:
            # check each subshelf position to find index
            for n in range(self.container_layout.count()):
                w = self.container_layout.itemAt(n).widget()
                if self.mapFromGlobal(pos).y() < w.y() + w.size().height():
                    # insert in place, shifting old widget down
                    self.view.controller.insert_shelf_id_in_task(shelf_id, self, n+1)
                    added = True
                    break
            # handle case where no location is found
            if not added:
                self.view.controller.insert_shelf_id_in_task(shelf_id, self, self.container_layout.count()+1)
            e.accept()


class Shelf(QFrame):

    def __init__(self, view, owner, df_id, **info):
        super(QFrame, self).__init__()
        self.view = view
        self.owner = owner
        self.df_id = df_id
        self.setObjectName("Shelf" + str(self.df_id))

        # added padding when going from lower level up to this one
        self.nest_offset = 28

        # set as tuple when being dragged so action can be undone
        self.undo = None
        self.dragStartPosition = None

        # create UI
        self.title = EditableText("", 15)
        cancel_button = QPushButton("x")
        cancel_button.setFixedSize(15, 15)
        cancel_button.setFlat(True)
        self.filter_label = QLabel("Filter:")
        self.filter_check = EditableCheck(False, 15)
        self.filter_text = EditableText("", 15)
        self.sorter_label = QLabel("Sorter:")
        self.sorter_check = EditableCheck(False, 15)
        self.sorter_text = EditableText("", 15)

        new_task_button = QPushButton("+")
        new_task_button.setFixedSize(40, 20)

        self.container_layout = QVBoxLayout()
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container = QFrame()
        self.container.setLayout(self.container_layout)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)

        tree = self.container
        self.scroll = QScrollArea()
        if isinstance(owner, Rack):
            self.scroll.setWidget(self.container)
            tree = self.scroll
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setContentsMargins(0, 0, 0, 0)

        self.child_indicator = QFrame()
        self.child_indicator.setFrameShape(QFrame.NoFrame)
        self.child_indicator.setFixedHeight(8)

        self.collapse_tree = CollapseGrid(True)
        self.collapse_tree.add_child(new_task_button, (0, 4), None, align=Qt.AlignRight)
        self.collapse_tree.add_child(tree, (1, 0, 1, 5), None)
        self.collapse_tree.add_child(self.child_indicator, None, (0, 1, 1, 3), align=Qt.AlignVCenter)

        id_label = QLabel(str(self.df_id))
        id_label.setStyleSheet("color: gray; font: italic")

        expanded = info["title"] == "///"
        collapse_grid = CollapseGrid(expanded)
        collapse_grid.add_child(self.title, (0, 1, 1, 4), (0, 1, 1, 2), align=Qt.AlignLeft)
        collapse_grid.add_child(cancel_button, (0, 5, 1, 1), (0, 5, 1, 1))
        collapse_grid.add_child(self.filter_label, (1, 2, 1, 1), None)
        collapse_grid.add_child(self.filter_check, (1, 1, 1, 1), (0, 3, 1, 1))
        collapse_grid.add_child(self.filter_text, (1, 3, 1, 3), None)
        collapse_grid.add_child(self.sorter_label, (2, 2, 1, 1), None)
        collapse_grid.add_child(self.sorter_check, (2, 1, 1, 1), (0, 4, 1, 1))
        collapse_grid.add_child(self.sorter_text, (2, 3, 1, 3), None)

        collapse_grid.add_child(self.collapse_tree, (3, 0, 2, 6), (1, 0, 1, 6))
        collapse_grid.add_child(id_label, (5, 0, 1, 3), None, align=Qt.AlignBottom)

        v_layout = QVBoxLayout()
        v_layout.addWidget(collapse_grid)
        v_layout.addWidget(self.collapse_tree)
        v_layout.addWidget(id_label, alignment=Qt.AlignBottom)
        self.setLayout(v_layout)

        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.set_edit_look(False)
        self.setLineWidth(2)

        self.edit_fields(info)

        self.check_width()
        self.setAcceptDrops(True)

        # event filtering for clicks
        self.installEventFilter(self.view)
        new_task_button.installEventFilter(self.view)
        cancel_button.installEventFilter(self.view)

        # use collapse signal to set alignment; necessary for collapsing shelves in rack
        self.collapse_tree.collapse_toggled.connect(lambda opened: self.owner.container_layout.setAlignment(self,
                                                    Qt.Alignment() if opened else Qt.AlignTop))
        # update width when tree collapsed
        self.collapse_tree.collapse_toggled.connect(self.check_width)

        # connect inputs to controller
        new_task_button.pressed.connect(lambda: self.view.controller.new_task_in_shelf(self))
        cancel_button.pressed.connect(lambda: self.view.controller.shelf_removed(self))

        self.title.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "title"))
        self.filter_check.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "filter_check"))
        self.filter_text.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "filter_text"))
        self.sorter_check.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "sorter_check"))
        self.sorter_text.edit_began.connect(lambda: self.view.controller.widget_field_entered(self, "sorter_text"))
        self.title.edit_updated.connect(lambda x: self.view.controller.widget_field_changed(self, ("title", x)))
        self.filter_check.edit_updated.connect(
            lambda x: self.view.controller.widget_field_changed(self, ("is_filter", x)))
        self.filter_text.edit_updated.connect(
            lambda x: self.view.controller.widget_field_changed(self, ("filter_string", x)))
        self.sorter_check.edit_updated.connect(
            lambda x: self.view.controller.widget_field_changed(self, ("is_sorter", x)))
        self.sorter_text.edit_updated.connect(
            lambda x: self.view.controller.widget_field_changed(self, ("sorter_string", x)))

    # set whether subtasks are held in a scrollbar or a frame
    def switch_scroll(self, to_scroll):
        c_layout = self.collapse_tree
        if to_scroll and c_layout.contains_widget(self.container):
            c_layout.replace_widget(self.container, self.scroll)
            self.scroll.setWidget(self.container)
            self.nest_offset += self.scroll.verticalScrollBar().sizeHint().width()
            self.check_width()
        elif not to_scroll and c_layout.contains_widget(self.scroll):
            self.scroll.takeWidget()
            c_layout.replace_widget(self.scroll, self.container)
            self.nest_offset -= self.scroll.verticalScrollBar().sizeHint().width()
            self.check_width()

    # set width to accommodate children and update parent if width changes
    def check_width(self):
        max_wid = 0
        if not self.collapse_tree.state:
            # minimize width if tress is collapsed
            max_wid = 0
        else:
            # find minimum necessary width to contain children
            for i in range(self.container_layout.count()):
                wid = self.container_layout.itemAt(i).widget().size().width()
                if wid > max_wid:
                    max_wid = wid

        # if width changes, update parent widths
        if max_wid + self.nest_offset != self.size().width():
            self.setFixedWidth(max(max_wid + self.nest_offset, 222 + self.nest_offset))
            if isinstance(self.owner, Task):
                self.owner.check_width()

    # sets whether the shelf is highlighted for edit mode
    def set_edit_look(self, to_edit):
        if to_edit:
            self.setStyleSheet("""
            Shelf{
                border: 2.5px solid blue;
            }
            """)
        else:
            self.setStyleSheet("""
            Shelf{
                border: 1px solid gray;
            }
            """)

    # update widget values to reflect change in model
    def edit_fields(self, edit_dict):
        if "title" in edit_dict:
            self.title.set_state(edit_dict["title"])
        if "is_filter" in edit_dict:
            self.filter_check.set_state(edit_dict["is_filter"])
        if "filter_string" in edit_dict:
            self.filter_text.set_state(edit_dict["filter_string"])
        if "is_sorter" in edit_dict:
            self.sorter_check.set_state(edit_dict["is_sorter"])
        if "sorter_string" in edit_dict:
            self.sorter_text.set_state(edit_dict["sorter_string"])

    # close all open edit widgets
    def close_fields(self):
        self.title.set_mode(False)
        self.filter_check.set_mode(False)
        self.filter_text.set_mode(False)
        self.sorter_check.set_mode(False)
        self.sorter_text.set_mode(False)

    def set_owner(self, o):
        self.owner = o
        # show scroll only if this widget is in the rack
        self.switch_scroll(isinstance(o, Rack))

    def add_child(self, child):
        child.set_owner(self)
        self.container_layout.addWidget(child)
        if self.container_layout.count() == 1:
            self.child_indicator.setFrameShape(QFrame.Box)
        self.check_width()

    def insert_child(self, child, pos):
        child.set_owner(self)
        self.container_layout.insertWidget(pos, child)
        if self.container_layout.count() == 1:
            self.child_indicator.setFrameShape(QFrame.Box)
        self.check_width()

    def remove_child(self, child):
        child.set_owner(None)
        self.container_layout.removeWidget(child)
        child.setParent(None)
        if self.container_layout.count() == 0:
            self.child_indicator.setFrameShape(QFrame.NoFrame)
        self.check_width()

    def get_child(self, idx):
        return self.container_layout.itemAt(idx).widget()

    def get_children(self):
        return [self.container_layout.itemAt(i).widget() for i in range(self.container_layout.count())]

    def mousePressEvent(self, e):
        b = e.buttons()
        if b == Qt.LeftButton or b == Qt.RightButton or b == Qt.MiddleButton:
            # track beginning of mouse hold and only start drag when it goes far enough
            self.dragStartPosition = e.pos()

    def mouseReleaseEvent(self, e):
        # reset drag start once released
        self.dragStartPosition = None

    def mouseMoveEvent(self, e):
        b = e.buttons()

        # only process dragging while button held
        if not(b == Qt.LeftButton or b == Qt.RightButton or b == Qt.MiddleButton):
            return

        # dont do drag if start position not set
        if self.dragStartPosition is None:
            return

        # only process dragging once the mouse has moved far enough
        if (e.pos() - self.dragStartPosition).manhattanLength() < QApplication.startDragDistance() * 6:
            return

        # handle drag
        drag = QDrag(self)

        # have image of this task follow the cursor
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)

        # duplicate shelf into new shelf
        if b == Qt.MiddleButton:
            dupe = self.view.controller.duplicate_shelf_id(self.df_id)
            self.undo = (b, dupe)

            mime = QMimeData()
            mime.setText(dupe)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)
        # creates a new reference to this shelf
        elif b == Qt.RightButton:
            self.undo = (b,)

            mime = QMimeData()
            drag.setMimeData(mime)
            mime.setText(self.df_id)
            drag.exec_(Qt.LinkAction)
        # move the reference to this shelf
        elif b == Qt.LeftButton:
            self.undo = (b, self.owner, self.owner.container_layout.indexOf(self) + 1)
            self.view.controller.shelf_removed(self)

            mime = QMimeData()
            drag.setMimeData(mime)
            mime.setText(self.df_id)
            drag.exec_(Qt.MoveAction)

    # reverses changes made when initializing a drag in case drop fails
    def undo_drag(self):
        # if duplicated, delete the newly created shelf
        if self.undo[0] == Qt.MiddleButton:
            self.view.controller.erase_shelf_id(self.undo[1])
        # nothing needs to be done to undo reference copy
        elif self.undo[0] == Qt.RightButton:
            pass
        # if moved, place the shelf back in the original location
        elif self.undo[0] == Qt.LeftButton:
            self.view.controller.insert_shelf_id_in_task(self.df_id, self.undo[1], self.undo[2])
        self.undo = None

    # accept dragged tasks or task ids
    def dragEnterEvent(self, e):
        if e.mimeData().text()[0] == 't' or isinstance(e.source(), Task):
            e.accept()

    # handle placement of dropped tasks
    def dropEvent(self, e):
        pos = e.pos()
        widget = e.source()
        added = False
        task_id = e.mimeData().text()

        # undo drag and drop if task is already in this shelf
        if self.view.controller.is_task_id_in_shelf(task_id, self):
            if widget is not None:
                widget.undo_drag()
        # place the dropped task
        else:
            # check each subtask position to find index
            for n in range(self.container_layout.count()):
                w = self.container_layout.itemAt(n).widget()
                # take scroll affecting position into account if scroll is visible
                y = w.parent().mapToParent(w.pos()).y() if self.layout().indexOf(self.scroll) > 0 else w.y()
                if self.mapFromGlobal(pos).y() < y + w.size().height():
                    # insert in place, shifting old widget down
                    self.view.controller.insert_task_id_in_shelf(task_id, self, n+1)
                    added = True
                    break
            # handle case where no location is found
            if not added:
                self.view.controller.insert_task_id_in_shelf(task_id, self, self.container_layout.count()+1)
            e.accept()


class Rack(QScrollArea):

    def __init__(self, view):
        super(QScrollArea, self).__init__()
        self.view = view

        self.container_layout = QHBoxLayout()
        self.container_layout.setAlignment(Qt.AlignLeft)
        rack_container = QWidget()
        rack_container.setLayout(self.container_layout)

        self.setAcceptDrops(True)

        self.setWidget(rack_container)
        self.setWidgetResizable(True)

    def add_child(self, child):
        child.set_owner(self)
        self.container_layout.addWidget(child)

    def insert_child(self, child, pos):
        child.set_owner(self)
        self.container_layout.insertWidget(pos, child)

    def remove_child(self, child):
        child.set_owner(None)
        self.container_layout.removeWidget(child)
        child.setParent(None)

    def clear(self):
        for i in reversed(range(self.container_layout.count())):
            self.remove_child(self.container_layout.itemAt(i).widget())

    def get_child(self, idx):
        return self.container_layout.itemAt(idx).widget()

    def get_index(self, child):
        return self.container_layout.indexOf(child)

    # accept dragged shelves or shelf ids
    def dragEnterEvent(self, e):
        if e.mimeData().text()[0] == 's' or isinstance(e.source(), Shelf):
            e.accept()

    # handle placement of dropped shelves
    def dropEvent(self, e):
        pos = e.pos()
        added = False
        shelf_id = e.mimeData().text()

        # check each subshelf position to find index
        for n in range(self.container_layout.count()):
            w = self.container_layout.itemAt(n).widget()
            if self.mapFromGlobal(pos).x() < w.parent().mapToParent(w.pos()).x() + w.size().width():
                # insert in place, shifting old widget down
                self.view.controller.insert_shelf_id_in_rack(shelf_id, n+1)
                added = True
                break
        # handle case where no location is found
        if not added:
            self.view.controller.insert_shelf_id_in_rack(shelf_id, self.container_layout.count()+1)
        e.accept()


class Stage(QGroupBox):

    def __init__(self, view):
        super(QGroupBox, self).__init__()
        self.view = view

        # create UI
        self.setTitle("Staging")
        create_task = QPushButton("+")

        space = QFrame()
        space.setFrameStyle(QFrame.Panel | QFrame.Plain)
        space.setLineWidth(1)
        space.setFixedHeight(180)

        self.task = None
        self.setAcceptDrops(True)

        self.container_layout = QVBoxLayout()
        space.setLayout(self.container_layout)
        self.container_layout.setContentsMargins(5, 5, 5, 5)

        header = QHBoxLayout()
        header.addStretch()
        header.addWidget(create_task)
        v_layout = QVBoxLayout()
        v_layout.addLayout(header)
        v_layout.addWidget(space)
        self.setLayout(v_layout)

        self.setFixedHeight(240)
        self.setFixedWidth(300)

        # event filtering for clicks
        create_task.installEventFilter(self.view)

        # connect inputs to controller
        create_task.pressed.connect(self.view.controller.new_task_in_stage)

    def add_child(self, child):
        child.set_owner(self)
        self.container_layout.addWidget(child)
        self.task = child

    def clear(self):
        if self.task is not None:
            self.task.set_owner(None)
            self.task.setParent(None)

    # accept dragged tasks or task ids
    def dragEnterEvent(self, e):
        if e.mimeData().text()[0] == 't' or isinstance(e.source(), Task):
            e.accept()

    # replace task with dropped task
    def dropEvent(self, e):
        task_id = e.mimeData().text()
        self.view.controller.set_task_id_in_stage(task_id)
        e.accept()


class FieldControl(QGroupBox):

    def __init__(self, view):
        super(QGroupBox, self).__init__()
        self.view = view

        new_field_name = QLineEdit()
        new_field_type = QComboBox()
        new_field_type.addItem("spin")
        new_field_type.addItem("text")
        new_field_type.addItem("check")
        new_field_type.addItem("date")
        new_field_button = QPushButton("+")
        new_field_button.setFixedSize(45, 24)

        create_row = QHBoxLayout()
        create_row.addWidget(new_field_name)
        create_row.addWidget(new_field_type)
        create_row.addWidget(new_field_button)

        self.field_container = QVBoxLayout()
        self.field_container.setAlignment(Qt.AlignTop)

        v_layout = QVBoxLayout()
        v_layout.setAlignment(Qt.AlignTop)
        v_layout.addLayout(create_row)
        v_layout.addLayout(self.field_container)

        self.setLayout(v_layout)

        new_field_name.installEventFilter(self.view)
        new_field_type.installEventFilter(self.view)
        new_field_button.installEventFilter(self.view)
        self.installEventFilter(self.view)

        new_field_button.clicked.connect(lambda: self.field_container.addWidget(
            FieldControl.FieldDeclaration(view, new_field_name.text(), new_field_type.currentText())))

    class FieldDeclaration(QWidget):

        def __init__(self, view, label_text, edit_type):
            super(QWidget, self).__init__()
            self.view = view

            label = EditableText(label_text, 30, autoescape=True)
            type_text = QLabel(edit_type)
            cancel_button = QPushButton("x")
            cancel_button.setFixedSize(15, 15)
            cancel_button.setFlat(True)

            h_layout = QHBoxLayout()
            h_layout.addWidget(label)
            h_layout.addWidget(type_text)
            h_layout.addWidget(cancel_button)
            self.setLayout(h_layout)

            label.installEventFilter(self.view)
            type_text.installEventFilter(self.view)
            cancel_button.installEventFilter(self.view)
            self.installEventFilter(self.view)
            cancel_button.clicked.connect(lambda: self.setParent(None))


class Editable(QStackedWidget):
    # class for editable widgets that switch between editable input mode and locked in display mode

    edit_began = pyqtSignal()
    edit_updated = pyqtSignal()

    def __init__(self, data, height, autoescape=False, autoset=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.autoescape = autoescape
        self.autoset = autoset
        self.fixed_height = height
        self.label = QLabel("")
        self.edit = self.make_edit()
        self.set_state(data)
        self.addWidget(self.label)
        self.addWidget(self.edit)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        if autoescape:
            self.edit.focus_lost.connect(lambda: self.set_mode(False))

    def sizeHint(self):
        return QSize(300, 15)

    # returns widget used for edit mode; changes per subclass
    def make_edit(self):
        return QWidget()

    # switch to edit mode when double clicked into
    def mouseDoubleClickEvent(self, event):
        if self.currentWidget() == self.label:
            self.set_mode(True)
            self.edit_began.emit()

    def focus(self):
        self.edit.setFocus()

    # set state of label and edit widgets
    def set_state(self, state, edit=True, label=True):
        if edit:
            self.edit.setText(state)
        if label:
            self.label.setText(state)

    # switch in or out of edit mode
    def set_mode(self, toEdit):
        if toEdit:
            self.setCurrentWidget(self.edit)
            if self.autoset:
                self.set_state(self.label.text(), label=False)
        else:
            self.setCurrentWidget(self.label)
            if self.autoset:
                self.set_state(self.edit.text(), edit=False)


class EditableText(Editable):
    edit_updated = pyqtSignal(str)

    def __init__(self, text, height, *args, **kwargs):
        super().__init__(text, height, *args, **kwargs)

        self.edit.textEdited.connect(lambda x: self.edit_updated.emit(x))
        if self.autoescape:
            self.edit.returnPressed.connect(lambda: self.set_mode(False))

    def make_edit(self):
        return self.DefocusLineEditFix()

    class DefocusLineEditFix(QLineEdit):
        focus_lost = pyqtSignal()

        def focusOutEvent(self, event):
            self.focus_lost.emit()

    def set_state(self, state, edit=True, label=True):
        if edit:
            self.edit.setText(state)
            if self.autoescape:
                self.edit.selectAll()
                self.edit.setFocus()
        if label:
            self.label.setText(state)


class EditableCheck(Editable):
    edit_updated = pyqtSignal(bool)

    def __init__(self, checked, height, *args, **kwargs):
        super().__init__(checked, height, *args, **kwargs)

        self.setFixedWidth(height)
        self.edit.clicked.connect(lambda x: self.edit_updated.emit(x))

    def make_edit(self):
        return self.DefocusCheckFix()

    class DefocusCheckFix(QCheckBox):
        focus_lost = pyqtSignal()

        def focusOutEvent(self, event):
            self.focus_lost.emit()

    def set_state(self, state, edit=True, label=True):
        if edit:
            self.edit.setChecked(state)
        if label:
            self.label.setText("☑" if state else "☐")


class EditableSpin(Editable):
    edit_updated = pyqtSignal(float)

    def __init__(self, number, height, *args, **kwargs):
        super().__init__(number, height, *args, **kwargs)

        self.edit.valueChanged.connect(lambda x: self.edit_updated.emit(float(x)))

    def make_edit(self):
        return self.DefocusDoubleSpinBoxFix()

    class DefocusDoubleSpinBoxFix(QDoubleSpinBox):
        focus_lost = pyqtSignal()

        def focusOutEvent(self, event):
            self.focus_lost.emit()

    def set_state(self, state, edit=True, label=True):
        if edit:
            self.edit.setValue(state)
        if label:
            self.label.setText(str(state))


class EditableDate(Editable):
    edit_updated = pyqtSignal(str)
    display_format = "M/d/yyyy h:mm AP"
    model_format = "yyyy-MM-dd hh:mm:ss"

    def __init__(self, number, height, *args, **kwargs):
        super().__init__(number, height, *args, **kwargs)

        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat(EditableDate.display_format)
        self.edit.dateTimeChanged.connect(lambda x: self.edit_updated.emit(x.toString(EditableDate.model_format)))

    def make_edit(self):
        return self.DefocusDateTimeEditFix()

    class DefocusDateTimeEditFix(QDateTimeEdit):
        focus_lost = pyqtSignal()

        def focusOutEvent(self, event):
            self.focus_lost.emit()

    # by default, dates are assumed to be the upcoming midnight
    def default_time(self):
        dt = QDateTime.currentDateTime().addDays(1)
        dt.setTime(QTime())
        return dt

    def set_state(self, state, edit=True, label=True):
        if edit:
            self.edit.setDateTime(self.default_time() if state is None else
                                  QDateTime.fromString(state, EditableDate.model_format))
        if label:
            self.label.setText("--/--/-- --:--" if state is None else
                    QDateTime.fromString(state, EditableDate.model_format).toString(EditableDate.display_format))


class CollapseGrid(QWidget):
    # class that can toggle between two widget layouts when an open/close button is clicked

    collapse_toggled = pyqtSignal(bool)

    def __init__(self, init_state, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.grid = QGridLayout()
        self.setLayout(self.grid)

        self.component_widgets = []
        self.toggle_arrow = QPushButton()
        self.toggle_arrow.clicked.connect(lambda x: self.set_state(not self.state))
        self.toggle_arrow.setFixedSize(15, 15)
        self.toggle_arrow.setFlat(True)
        self.grid.addWidget(self.toggle_arrow, 0, 0)

        self.grid.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)

        self.state = False
        self.set_state(init_state)

    # open or close the layout
    def set_state(self, is_open):
        self.state = is_open
        # process each widget
        for w in self.component_widgets:
            # if opened, and appears in opened layout, move to open position
            if self.state and w[1] is not None:
                self.grid.removeWidget(w[0])
                self.grid.addWidget(w[0], *w[1], alignment=w[3])
                w[0].show()
            # if closed, and appears in closed layout, move to closed position
            elif not self.state and w[2] is not None:
                self.grid.removeWidget(w[0])
                self.grid.addWidget(w[0], *w[2], alignment=w[3])
                w[0].show()
            # if hidden in current state, hide
            else:
                w[0].hide()
        self.toggle_arrow.setText("v" if self.state else ">")
        self.collapse_toggled.emit(self.state)

    # add a child widget and set its open and closed positions
    def add_child(self, widget, open_pos, close_pos, align=Qt.Alignment()):
        # invalid, never appears
        if open_pos is None and close_pos is None:
            return
        # add to open position
        elif self.state and open_pos is not None:
            self.grid.addWidget(widget, *open_pos, alignment=align)
        # add to close position
        elif not self.state and close_pos is not None:
            self.grid.addWidget(widget, *close_pos, alignment=align)
        # add to close pos and hide
        elif self.state and open_pos is None:
            self.grid.addWidget(widget, *close_pos, alignment=align)
            widget.hide()
        # add to open pos hide
        elif not self.state and close_pos is None:
            self.grid.addWidget(widget, *open_pos, alignment=align)
            widget.hide()
        # append widget to list of all widgets
        self.component_widgets.append((widget, open_pos, close_pos, align))

    # returns true if widget is in this grid
    def contains_widget(self, widget):
        for component in self.component_widgets:
            if component[0] == widget:
                return True
        return False

    # replaces a widget with a new one that follows the same collapse rule
    def replace_widget(self, original_w, new_w):
        for component in self.component_widgets:
            if component[0] == original_w:
                self.component_widgets.remove(component)
                self.grid.removeWidget(original_w)
                self.add_child(new_w, component[1], component[2], component[3])
                return
