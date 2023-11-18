from PyQt5.QtCore import QObject, pyqtSlot

class PetController(QObject):

    def __init__(self, model, shelf):
        super().__init__()

        self.model = model
        self.pet_view = None

        self.shelf = shelf

        # connect model signals to view ui
        self.model.shelf_moved_in_task.connect(self.move_shelf_in_task)
        self.model.task_moved_in_shelf.connect(self.move_task_in_shelf)
        self.model.shelf_info_changed.connect(self.change_shelf_info)
        self.model.task_info_changed.connect(self.change_task_info)
        self.model.new_model_loaded.connect(self.load_new_model)

    # close out the desktop pet
    def close(self):
        pass

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