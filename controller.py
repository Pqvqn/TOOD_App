from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import QWidget
from view import Task, Shelf, Rack, Stage


class Controller(QObject):

    def __init__(self, model):
        super().__init__()

        self.model = model
        self.view = None

        # the current task or shelf that has controller is tracking edits for
        self.widget_being_edited = None
        self.edit_dict = {}
        self.edit_instances = []

        # connect model signals to view ui
        self.model.task_in_stage_changed.connect(self.change_task_in_stage)
        self.model.shelf_moved_in_task.connect(self.move_shelf_in_task)
        self.model.task_moved_in_shelf.connect(self.move_task_in_shelf)
        self.model.shelf_added_to_rack.connect(self.add_shelf_to_rack)
        self.model.shelf_removed_from_rack.connect(self.remove_shelf_from_rack)
        self.model.shelf_moved_in_rack.connect(self.move_shelf_in_rack)
        self.model.shelf_info_changed.connect(self.change_shelf_info)
        self.model.task_info_changed.connect(self.change_task_info)
        self.model.new_model_loaded.connect(self.load_new_model)

    def register_view(self, view):
        self.view = view

    # creates and returns widget with accompanying nested widgets already assembled into place
    def assemble_tree(self, df_id, is_id_task):
        # get children of this node from model
        if is_id_task:
            root = Task(self.view, None, df_id, **self.model.get_task_info([df_id])[df_id])
            children = self.model.get_subshelves(df_id)
        else:
            root = Shelf(self.view, None, df_id, **self.model.get_shelf_info([df_id])[df_id])
            children = self.model.get_subtasks(df_id)

        # create the tree widgets from bottom to top
        for c_id in children:
            child = self.assemble_tree(c_id, not is_id_task)
            root.add_child(child)

        return root

    # returns all widget instances in the nesting tree of the given shelf or task
    def find_instances(self, df_id, is_id_task):
        instances = []
        if is_id_task:
            # add stage appearance as an instance
            if df_id == self.model.stage:
                instances.append(self.view.stage.task)
            # search up the tree and back down for instances of the parent
            parents = self.model.get_supershelves(df_id, include_index=True)
        else:
            # add rack appearances as instances
            if df_id in self.model.rack:
                indices = [i for i, x in enumerate(self.model.rack) if x == df_id]
                instances.extend([self.view.rack.get_child(i) for i in indices])
            # search up the tree and back down for instances of the parent
            parents = self.model.get_supertasks(df_id, include_index=True)

        # get instances from view and return
        for p in parents:
            p_instances = self.find_instances(p[0], not is_id_task)
            for p_i in p_instances:
                instances.append(p_i.get_child(p[1]-1))
        return instances

    # slots from view triggers
    @pyqtSlot()
    def debug_print(self):
        print("_____TASKS_____")
        print(self.model.taskdf)
        print("_____SHELVES_____")
        print(self.model.shelfdf)
        print("_____MATRIX_____")
        print(self.model.nestmat)
        print("_____RACK_____")
        print(self.model.rack)
        print("_____STAGE_____")
        print(self.model.stage)

    @pyqtSlot()
    def new_shelf_in_rack(self):
        df_id = self.model.create_empty_shelf()
        self.model.add_shelf_to_rack(df_id)

    @pyqtSlot()
    def new_task_in_stage(self):
        df_id = self.model.create_empty_task()
        self.model.replace_task_in_stage(df_id)

    @pyqtSlot(QWidget)
    def new_shelf_in_task(self, task):
        shelf = self.model.create_empty_shelf()
        success = self.model.position_shelf_in_task(shelf, task.df_id)
        if not success[0]:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget)
    def new_task_in_shelf(self, shelf):
        task = self.model.create_empty_task()
        success = self.model.position_task_in_shelf(task, shelf.df_id)
        if not success[0]:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget)
    def shelf_removed(self, shelf):
        parent = shelf.owner
        success = (False,)
        if isinstance(parent, Task):
            success = self.model.position_shelf_in_task(shelf.df_id, parent.df_id, idx=0)
        elif isinstance(parent, Rack):
            self.model.remove_shelf_from_rack(self.view.rack.get_index(shelf))
        if len(success) > 1 and not success[0]:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget)
    def task_removed(self, task):
        parent = task.owner
        success = (False,)
        if isinstance(parent, Shelf):
            success = self.model.position_task_in_shelf(task.df_id, parent.df_id, idx=0)
        elif isinstance(parent, Stage):
            self.model.replace_task_in_stage(None)
        if len(success) > 1 and not success[0]:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget, str)
    def widget_field_entered(self, widget, field_name):
        if self.widget_being_edited is None:
            # set up variables for edit
            self.widget_being_edited = widget
            self.edit_dict = {}
            self.edit_instances = self.find_instances(widget.df_id, isinstance(widget, Task))
            self.edit_instances.remove(widget)

            # put widgets in edit mode
            widget.set_edit_look(True)
            for inst in self.edit_instances:
                inst.set_edit_look(True)
                getattr(inst, field_name).set_mode(True)

        elif self.widget_being_edited == widget:
            for inst in self.edit_instances:
                getattr(inst, field_name).set_mode(True)

    @pyqtSlot(QWidget, tuple)
    def widget_field_changed(self, widget, change):
        # if another instance is being edited, switch main edit widget to the new one
        if self.widget_being_edited != widget and widget in self.edit_instances:
            self.edit_instances.append(self.widget_being_edited)
            self.edit_instances.remove(widget)
            self.widget_being_edited = widget

        if self.widget_being_edited == widget:
            # add change to dict
            self.edit_dict[change[0]] = change[1]
            # mirror change onto other widgets
            for inst in self.edit_instances:
                inst.edit_fields({change[0]: change[1]})

    @pyqtSlot()
    def widget_edit_ended(self):
        # remove the edit highlight from widgets and close all open edit fields
        self.widget_being_edited.set_edit_look(False)
        self.widget_being_edited.close_fields()
        for inst in self.edit_instances:
            inst.set_edit_look(False)
            inst.close_fields()
        # update model
        success = (False,)
        df_id = self.widget_being_edited.df_id
        if isinstance(self.widget_being_edited, Shelf):
            success = self.model.edit_shelf(df_id, **self.edit_dict)
        elif isinstance(self.widget_being_edited, Task):
            success = self.model.edit_task(df_id, **self.edit_dict)

        if len(success) > 1 and success[0]:
            # clear edit variables
            self.widget_being_edited = None
            self.edit_dict = {}
            self.edit_instances = []

        elif len(success) > 1:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget, tuple)
    def direct_field_change(self, widget, change):
        if isinstance(widget, Task):
            success = self.model.edit_task(widget.df_id, **{change[0]: change[1]})
        else:
            success = self.model.edit_shelf(widget.df_id, **{change[0]: change[1]})
        if not success[0]:
            self.view.show_warning(success[1])

    @pyqtSlot(QWidget)
    def copy_shelf(self, line_edit):
        if not line_edit.text() in self.model.shelfdf.index:
            self.view.show_warning("Index not a valid shelf")
        else:
            self.model.add_shelf_to_rack(line_edit.text())

    @pyqtSlot(QWidget)
    def copy_task(self, line_edit):
        if not line_edit.text() in self.model.taskdf.index:
            self.view.show_warning("Index not a valid task")
        else:
            self.model.replace_task_in_stage(line_edit.text())

    @pyqtSlot(str)
    def load_tood(self, path):
        if path != "":
            with open(path, "r") as tood_file:
                self.model.read_from_file(tood_file)

    @pyqtSlot(str)
    def save_tood(self, path):
        if path != "":
            with open(path, "ab") as tood_file:
                tood_file.seek(0)
                tood_file.truncate()
                self.model.write_to_file(tood_file)

    def duplicate_task_id(self, og_id):
        if og_id not in self.model.taskdf.index:
            self.view.show_warning(og_id+" is an invalid task ID")
            return

        index = self.model.create_empty_task()
        info_dict = self.model.get_task_info([og_id])[og_id]
        info_dict.pop("seen")
        success = self.model.edit_task(index, **info_dict)
        if not success[0]:
            self.view.show_warning(success[1])
        return index

    def erase_task_id(self, df_id):
        if df_id not in self.model.taskdf.index:
            self.view.show_warning(df_id+" is an invalid task ID")
            return

        self.model.erase_task(df_id)

    def insert_task_id_in_shelf(self, task_id, shelf, idx):
        if task_id not in self.model.taskdf.index:
            self.view.show_warning(task_id+" is an invalid task ID")
            return

        success = self.model.position_task_in_shelf(task_id, shelf.df_id, idx=idx)
        if not success[0]:
            self.view.show_warning(success[1])

    def is_task_id_in_shelf(self, task_id, shelf):
        if task_id not in self.model.taskdf.index:
            self.view.show_warning(task_id+" is an invalid task ID")
            return

        return task_id in self.model.get_subtasks(shelf.df_id)

    def set_task_id_in_stage(self, task_id):
        if task_id not in self.model.taskdf.index:
            self.view.show_warning(task_id+" is an invalid task ID")

        self.model.replace_task_in_stage(task_id)

    def duplicate_shelf_id(self, og_id):
        if og_id not in self.model.shelfdf.index:
            self.view.show_warning(og_id+" is an invalid shelf ID")
            return

        index = self.model.create_empty_shelf()
        info_dict = self.model.get_shelf_info([og_id])[og_id]
        info_dict.pop("seen")
        success = self.model.edit_shelf(index, **info_dict)
        if not success[0]:
            self.view.show_warning(success[1])
        return index

    def erase_shelf_id(self, df_id):
        if df_id not in self.model.shelfdf.index:
            self.view.show_warning(df_id+" is an invalid shelf ID")
            return

        self.model.erase_shelf(df_id)

    def insert_shelf_id_in_task(self, shelf_id, task, idx):
        if shelf_id not in self.model.shelfdf.index:
            self.view.show_warning(shelf_id+" is an invalid shelf ID")
            return

        success = self.model.position_shelf_in_task(shelf_id, task.df_id, idx=idx)
        if not success[0]:
            self.view.show_warning(success[1])

    def is_shelf_id_in_task(self, shelf_id, task):
        if shelf_id not in self.model.shelfdf.index:
            self.view.show_warning(shelf_id+" is an invalid shelf ID")
            return

        return shelf_id in self.model.get_subshelves(task.df_id)

    def insert_shelf_id_in_rack(self, shelf_id, idx):
        if shelf_id not in self.model.shelfdf.index:
            self.view.show_warning(shelf_id+" is an invalid shelf ID")
            return

        self.model.add_shelf_to_rack(shelf_id, insert_at=idx)

    # slots from model triggers
    @pyqtSlot(str, str)
    def change_task_in_stage(self, prev_task, new_task):
        if prev_task != "":
            self.view.stage.clear()
        if new_task != "":
            self.view.stage.add_child(self.assemble_tree(new_task, True))

    @pyqtSlot(str, str, int, int)
    def move_shelf_in_task(self, shelf, task, start, end):
        task_instances = self.find_instances(task, True)
        # remove
        if start != 0:
            for t_i in task_instances:
                t_i.remove_child(t_i.get_child(start-1))
        # add
        if end != 0:
            for t_i in task_instances:
                s_i = self.assemble_tree(shelf, False)
                t_i.insert_child(s_i, end-1)

    @pyqtSlot(str, str, int, int)
    def move_task_in_shelf(self, task, shelf, start, end):
        shelf_instances = self.find_instances(shelf, False)
        # remove
        if start != 0:
            for s_i in shelf_instances:
                s_i.remove_child(s_i.get_child(start-1))
        # add
        if end != 0:
            for s_i in shelf_instances:
                t_i = self.assemble_tree(task, True)
                s_i.insert_child(t_i, end-1)

    @pyqtSlot(str, int)
    def add_shelf_to_rack(self, shelf, index):
        self.view.rack.insert_child(self.assemble_tree(shelf, False), index)

    @pyqtSlot(str, int)
    def remove_shelf_from_rack(self, shelf, index):
        self.view.rack.remove_child(self.view.rack.get_child(index))

    @pyqtSlot(str, int)
    def move_shelf_in_rack(self, shelf, index):
        self.view.rack.remove_child(self.view.rack.get_child(index))
        self.view.rack.insert_child(self.assemble_tree(shelf, False), index)

    @pyqtSlot(str, dict)
    def change_shelf_info(self, shelf, info):
        instances = self.find_instances(shelf, False)
        for inst in instances:
            inst.edit_fields(info)

    @pyqtSlot(str, dict)
    def change_task_info(self, task, info):
        instances = self.find_instances(task, True)
        for inst in instances:
            inst.edit_fields(info)

    @pyqtSlot(str, list)
    def load_new_model(self, stage, rack):
        self.view.stage.clear()
        self.change_task_in_stage("", stage)
        self.view.rack.clear()
        for r in reversed(rack):
            self.add_shelf_to_rack(r, 0)
