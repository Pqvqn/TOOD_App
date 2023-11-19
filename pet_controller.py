from PyQt5.QtCore import QObject, pyqtSlot, QProcess

class PetController(QObject):

    def __init__(self, model, shelf):
        super().__init__()

        self.model = model
        self.pet_view = None

        self.shelf = shelf

        self.p = None
        self.start()

        # connect model signals to view ui
        self.model.shelf_moved_in_task.connect(self.move_shelf_in_task)
        self.model.task_moved_in_shelf.connect(self.move_task_in_shelf)
        self.model.shelf_info_changed.connect(self.change_shelf_info)
        self.model.task_info_changed.connect(self.change_task_info)
        self.model.new_model_loaded.connect(self.load_new_model)

    # open the desktop pet
    def start(self):
        if self.p is None:
            self.p = QProcess()
            self.p.readyReadStandardOutput.connect(self.handle_stdout)
            self.p.readyReadStandardError.connect(self.handle_stderr)
            self.p.stateChanged.connect(self.handle_state)
            self.p.finished.connect(self.process_finished)
            self.p.start('dist/pet_test/pet_test.exe')

            # for i in range(5):
            #     to = input() + "\n"
            #     self.p.write(bytes(to, 'utf-8'))

    # close out the desktop pet
    def close(self):
        if self.p is not None:
            self.p.terminate()

    def handle_stderr(self):
        data = self.p.readAllStandardError()
        stderr = bytes(data).decode("utf8")
        print(stderr)

    def handle_stdout(self):
        data = self.p.readAllStandardOutput()
        stdout = bytes(data).decode("utf8")
        print(stdout)

    def handle_state(self, state):
        states = {
            QProcess.NotRunning: 'Not running',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }
        state_name = states[state]
        print(f"State changed: {state_name}")

    def process_finished(self):
        print("Process finished.")
        self.p = None

    @pyqtSlot(str, str, int, int)
    def move_shelf_in_task(self, shelf, task, start, end):
        # only operate if the moved shelf is inside this shelf
        if self.model.check_tree_for(self.shelf, False, shelf, False, False):
            pass

    @pyqtSlot(str, str, int, int)
    def move_task_in_shelf(self, task, shelf, start, end):
        # only operate if the moved task is inside this shelf
        if self.model.check_tree_for(self.shelf, False, task, True, False):
            pass

    @pyqtSlot(str, dict)
    def change_shelf_info(self, shelf, info):
        # only operate if the changed shelf is this one
        if self.shelf == shelf:
            pass

    @pyqtSlot(str, dict)
    def change_task_info(self, task, info):
        # only operate if the changed task is inside this shelf
        if self.model.check_tree_for(self.shelf, False, task, True, False):
            pass

    @pyqtSlot(str, list)
    def load_new_model(self, stage, rack):
        self.close()
