from random import randint
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal
import re
import mmap

pd.options.mode.chained_assignment = None


# creates a new label index that doesn't overlap with any existing labels
def generate_next_label(column_list, prefix=""):
    if len(column_list) == 0:
        # create first index of table
        return prefix + str(randint(1, 25))
    else:
        # remove prefix and convert list of strings to ints
        fixed_list = [int(x[len(prefix):]) for x in column_list]
        return prefix + str(max(fixed_list) + randint(1, 25))


class Model(QObject):

    # signals
    task_moved_in_shelf = pyqtSignal(str, str, int, int)  # task id, shelf id, start idx, end idx
    shelf_moved_in_task = pyqtSignal(str, str, int, int)  # shelf id, task id, start idx, end idx
    shelf_moved_in_rack = pyqtSignal(str, int)  # shelf id, end idx
    shelf_added_to_rack = pyqtSignal(str, int)  # shelf id, end idx
    shelf_removed_from_rack = pyqtSignal(str, int)  # shelf id, prev idx
    task_in_stage_changed = pyqtSignal(str, str)  # prev id, new id
    task_info_changed = pyqtSignal(str, dict)  # task id, all task values to be updated
    shelf_info_changed = pyqtSignal(str, dict)  # shelf id, all shelf values to be updated
    new_model_loaded = pyqtSignal(str, list)  # stage, rack
    field_added = pyqtSignal(str, type)  # label, field type
    field_deleted = pyqtSignal(str)  # label
    field_data_copied = pyqtSignal(str, str)  # original label, copy label
    field_renamed = pyqtSignal(str, str)  # old label, new label

    def __init__(self):
        super(QObject, self).__init__()

        # column labels and required types for task dataframe
        self.taskattributes = {"label": str,
                            "seen": int,
                            "completed": bool,
                            "remind": pd.Timestamp}
        # column labels for custom task fields in task dataframe
        self.taskfields = {}
        # shelf labels and required types for task dataframe
        self.shelfattributes = {"title": str,
                             "seen": int,
                             "is_filter": bool,
                             "filter_string": str,
                             "is_sorter": bool,
                             "sorter_string": str}

        # dataframe of task data by task index
        self.taskdf = pd.DataFrame(columns=list(self.taskattributes) + list(self.taskfields))
        # dataframe of shelf data by shelf index
        self.shelfdf = pd.DataFrame(columns=list(self.shelfattributes.keys()))
        # nesting matrix of ordering of tasks within shelves and vice-versa; tasks are columns, shelves are rows
        # positive integers are for task ordering in shelf, negative integers are for shelf ordering in task, 0 is none
        # no recursive loop is allowed to exist
        self.nestmat = pd.DataFrame()
        # the shelves displayed horizontally in the app
        self.rack = []
        #  spot for single task outside of shelves
        self.stage = None

    # returns true if the target shelf or task is found the current shelf or task in the nesting tree
    def check_tree_for(self, current, is_current_task, target, is_target_task, is_searching_up):
        # found target
        if is_current_task == is_target_task and current == target:
            return True

        # find next tasks or shelves to check
        if is_current_task:
            strip = self.nestmat[current]
            next_layer = strip.index[strip.values > 0 if is_searching_up else strip.values < 0]
        else:
            strip = self.nestmat.loc[current]
            next_layer = strip.index[strip.values < 0 if is_searching_up else strip.values > 0]

        # recursively check all children or parents
        for x in next_layer:
            if self.check_tree_for(x, not is_current_task, target, is_target_task, is_searching_up):
                return True
        return False

    def run_on_tree(self, current, is_current_task, is_searching_up, function):
        # run lambda expression
        function(current=current, is_current_task=is_current_task)

        # find next tasks or shelves to run on
        if is_current_task:
            strip = self.nestmat[current]
            next_layer = strip.index[strip.values > 0 if is_searching_up else strip.values < 0]
        else:
            strip = self.nestmat.loc[current]
            next_layer = strip.index[strip.values < 0 if is_searching_up else strip.values > 0]

        # recursively run on all children or parents
        for x in next_layer:
            self.run_on_tree(x, not is_current_task, is_searching_up, function)

    def increment_seen(self, current, is_current_task, amount):
        if is_current_task:
            self.taskdf.at[current, "seen"] += amount
        else:
            self.shelfdf.at[current, "seen"] += amount

    # creates a new task index
    # return label of new task
    def create_empty_task(self):
        label_idx = generate_next_label(list(self.taskdf.index.values), prefix="t")
        self.taskdf.loc[label_idx] = {"label": "///",
                                      "seen": 0,
                                      "due": None,
                                      "completed": False}
        # add task to nesting matrix
        self.nestmat[label_idx] = 0
        return label_idx

    # creates a new shelf index
    # return label of new shelf
    def create_empty_shelf(self):
        label_idx = generate_next_label(list(self.shelfdf.index.values), prefix="s")
        self.shelfdf.loc[label_idx] = {"title": "///",
                                       "seen": 0,
                                       "is_filter": False,
                                       "filter_string": "",
                                       "is_sorter": False,
                                       "sorter_string": ""}
        # add shelf to nesting matrix
        if len(self.nestmat.columns) > 0:
            self.nestmat.loc[label_idx] = 0
        else:
            self.nestmat = pd.concat([self.nestmat, pd.DataFrame(index=[label_idx])])
        return label_idx

    # change the position index of a task inside a shelf (positive ints in nest matrix)
    # adds task if index was previously zero and removes if index is now zero
    # return tuple: (success of program, termination message)
    def position_task_in_shelf(self, task, shelf, idx=None, filter_override=False, sorter_override=False):
        prev_idx = self.nestmat.at[shelf, task]
        tail_idx = max(self.nestmat.loc[shelf].max(), 0)

        # tasks can't be inserted at a specific position for a sorter, so idx must be None or 0 (for removal)
        if self.shelfdf.at[shelf, "is_sorter"] and not sorter_override:
            if idx is None:
                index = self.sort_task_into_shelf(task, shelf)
            elif idx == 0:
                index = idx
            else:
                return False, "Can't insert tasks into specific position in sorters"
        else:
            # by default, append to end
            index = tail_idx + 1 if idx is None else idx

        # reject invalid indices
        if index < 0 or index > tail_idx + 1:
            return False, "Invalid index given for insertion"

        # don't overwrite an opposite nest
        if prev_idx < 0:
            return False, "Shelf is within task"

        # if removing task, shift rightwards indices to the left
        if prev_idx != 0 and index == 0:
            # tasks cannot be removed from filters
            if self.shelfdf.at[shelf, "is_filter"] and not filter_override:
                return False, "Can't remove task from filter shelf"
            self.nestmat.loc[shelf, self.nestmat.loc[shelf] >= prev_idx] -= 1
            self.run_on_tree(task, True, False, lambda **c:
                             self.increment_seen(**c, amount=-self.shelfdf.at[shelf, "seen"]))
        # if moving this task to the right, shift indices between the positions to the left
        elif 0 < prev_idx < index:
            self.nestmat.loc[shelf, (self.nestmat.loc[shelf] >= prev_idx) & (self.nestmat.loc[shelf] <= index)] -= 1
        # if moving this task to the left, shift indices between the positions to the right
        elif prev_idx > index:
            self.nestmat.loc[shelf, (self.nestmat.loc[shelf] <= prev_idx) & (self.nestmat.loc[shelf] >= index)] += 1
        # if adding new task, shift rightwards indices to the right
        elif prev_idx == 0 and index != 0:
            # tasks cannot be added to filters
            if self.shelfdf.at[shelf, "is_filter"] and not filter_override:
                return False, "Can't add task to filter shelf"
            # verify that shelf isn't below task and task isn't above shelf in nesting
            if self.check_tree_for(task, True, shelf, False, False) or \
                    self.check_tree_for(shelf, False, task, True, True):
                return False, "Addition would create circular nesting"
            self.nestmat.loc[shelf, self.nestmat.loc[shelf] >= index] += 1
            self.run_on_tree(task, True, False, lambda **c:
                             self.increment_seen(**c, amount=self.shelfdf.at[shelf, "seen"]))

        self.nestmat.at[shelf, task] = index
        self.task_moved_in_shelf.emit(task, shelf, prev_idx, index)
        return True, ""

    # change the position index of a shelf inside a task (negative ints in nest matrix)
    # adds shelf if index was previously zero and removes if index is now zero
    # return tuple: (success of program, termination message)
    def position_shelf_in_task(self, shelf, task, idx=None):
        tail_idx = max(-self.nestmat[task].min(), 0)
        prev_idx = -self.nestmat.at[shelf, task]
        # by default, append to end
        index = tail_idx + 1 if idx is None else idx

        # reject invalid indices
        if index < 0 or index > tail_idx + 1:
            return False, "Invalid index given for insertion"

        # don't overwrite an opposite nest
        if prev_idx < 0:
            return False, "Task is within shelf"

        # if removing shelf, shift rightwards indices to the left
        if prev_idx != 0 and index == 0:
            self.nestmat[task][-self.nestmat[task] >= prev_idx] += 1
            self.run_on_tree(shelf, False, False, lambda **c:
                             self.increment_seen(**c, amount=-self.taskdf.at[task, "seen"]))
        # if moving this shelf to the right, shift indices between the positions to the left
        elif 0 < prev_idx < index:
            self.nestmat[task][(-self.nestmat[task] >= prev_idx) & (-self.nestmat[task] <= index)] += 1
        # if moving this shelf to the left, shift indices between the positions to the right
        elif prev_idx > index:
            self.nestmat[task][(-self.nestmat[task] <= prev_idx) & (-self.nestmat[task] >= index)] -= 1
        # if adding new shelf, shift rightwards indices to the right
        elif prev_idx == 0 and index != 0:
            # filters cannot be involved in nesting
            # if self.shelfdf.at[shelf, "is_filter"]:
            #     return False, "Can't add filter shelf to task"
            # verify that task isn't below shelf and shelf isn't above task in nesting
            if self.check_tree_for(shelf, False, task, True, False) or \
                    self.check_tree_for(task, True, shelf, False, True):
                return False, "Addition would create circular nesting"
            self.nestmat[task][-self.nestmat[task] >= index] -= 1
            self.run_on_tree(shelf, False, False, lambda **c:
                             self.increment_seen(**c, amount=self.taskdf.at[task, "seen"]))

        self.nestmat.at[shelf, task] = -index
        self.shelf_moved_in_task.emit(shelf, task, prev_idx, index)
        return True, ""

    # add a shelf to the rack
    def add_shelf_to_rack(self, shelf, insert_at=None):
        # add to end by default
        if insert_at is None:
            self.rack.append(shelf)
            self.run_on_tree(shelf, False, False, lambda **c: self.increment_seen(**c, amount=1))
            self.shelf_added_to_rack.emit(shelf, len(self.rack)-1)
        else:
            self.rack.insert(insert_at, shelf)
            self.run_on_tree(shelf, False, False, lambda **c: self.increment_seen(**c, amount=1))
            self.shelf_added_to_rack.emit(shelf, insert_at)

    # move shelf to different position in rack
    def move_shelf_in_rack(self, shelf, index):
        self.rack.remove(shelf)
        self.rack.insert(index, shelf)
        self.shelf_moved_in_rack.emit(shelf, index)

    # remove a shelf from the rack
    def remove_shelf_from_rack(self, index):
        shelf = self.rack.pop(index)
        self.run_on_tree(shelf, False, False, lambda **c: self.increment_seen(**c, amount=-1))
        self.shelf_removed_from_rack.emit(shelf, index)

    # change which task is in the stage
    def replace_task_in_stage(self, new_task):
        prev_task = self.stage
        self.stage = new_task
        if prev_task is not None:
            self.run_on_tree(prev_task, True, False, lambda **c: self.increment_seen(**c, amount=-1))
        if new_task is not None:
            self.run_on_tree(new_task, True, False, lambda **c: self.increment_seen(**c, amount=1))
        self.task_in_stage_changed.emit(prev_task if prev_task is not None else None,
                                        new_task if new_task is not None else None)

    # edit task data via dict and check against relevant columns
    # return tuple: (success of program, termination message)
    def edit_task(self, task, **kwargs):

        # make sure all values are of the correct type
        for key in kwargs:
            if key not in self.taskattributes and key not in self.taskfields:
                return False, key + " is not a task parameter"
            if kwargs[key] is not None and key in self.taskattributes and not isinstance(kwargs[key],
                                                                                         self.taskattributes.get(key)):
                # convert types that need conversion
                if self.taskattributes.get(key) == pd.Timestamp:
                    kwargs[key] = pd.Timestamp(kwargs[key])
                else:
                    return False, key + " must have type " + self.taskattributes[key].__name__
            if kwargs[key] is not None and key in self.taskfields and not isinstance(kwargs[key],
                                                                                     self.taskfields.get(key)):
                # convert types that need conversion
                if self.taskfields.get(key) == pd.Timestamp:
                    kwargs[key] = pd.Timestamp(kwargs[key])
                else:
                    return False, key + " must have type " + self.taskfields[key].__name__

        # don't allow internal parameters to be modified
        if "seen" in kwargs:
            return False, "seen is an internal parameter"

        # update values
        self.taskdf.loc[task, kwargs.keys()] = kwargs.values()
        self.task_info_changed.emit(task, kwargs)

        # check if task needs to be added/removed from filters
        self.check_against_filters(task)
        # check if task needs to be resorted in any sorters it is in
        self.check_parent_sorters(task)

        return True, ""

    # edit shelf data via dict and verify tasks if necessary
    # return tuple: (success of program, termination message)
    def edit_shelf(self, shelf, **kwargs):
        # make sure all values are of the correct type
        for key in kwargs:
            if key not in self.shelfattributes:
                return False, key + " is not a shelf parameter"
            if kwargs[key] is not None and not isinstance(kwargs[key], self.shelfattributes.get(key)):
                # convert types that need conversion
                if self.shelfattributes.get(key) == pd.Timestamp:
                    kwargs[key] = pd.Timestamp(kwargs[key])
                else:
                    return False, key + " must have type " + self.shelfattributes[key].__name__

        # don't create filters that are subshelves of any task
        # if "is_filter" in kwargs and kwargs["is_filter"]:
        #     strip = self.nestmat.loc[shelf]
        #     next_layer = strip.index[strip.values < 0]
        #     if len(next_layer) != 0:
        #         return False, "Subshelves can't become filters"

        # don't allow internal parameters to be modified
        if "seen" in kwargs:
            return False, "seen is an internal parameter"

        # update values
        self.shelfdf.loc[shelf, kwargs.keys()] = kwargs.values()
        self.shelf_info_changed.emit(shelf, kwargs)

        # redo filtering
        if self.shelfdf.at[shelf, "is_filter"]:
            self.refilter_shelf(shelf)
        # redo sorting
        if self.shelfdf.at[shelf, "is_sorter"]:
            self.resort_shelf(shelf)

        return True, ""

    # delete all data associated with task
    def erase_task(self, task):
        # remove from task listing
        self.taskdf.drop(index=task, inplace=True)

        # remove from all supershelves
        strip = self.nestmat[task]
        for shelf in strip.index[strip.values > 0]:
            self.position_task_in_shelf(task, shelf, idx=0, filter_override=True, sorter_override=True)

        # remove from stage
        if task == self.stage:
            self.replace_task_in_stage(None)

        # delete from nesting list
        self.nestmat.drop(columns=task, inplace=True)

    # delete all data associated with shelf
    def erase_shelf(self, shelf):
        # remove from shelf listing
        self.shelfdf.drop(index=shelf, inplace=True)

        # remove from rack
        if shelf in self.rack:
            self.rack.remove(shelf)

        # remove from all supertasks
        strip = self.nestmat.loc[shelf]
        for task in strip.index[strip.values < 0]:
            self.position_shelf_in_task(shelf, task, idx=0)

        # delete from nesting list
        self.nestmat.drop(index=shelf, inplace=True)

    # add a new field for tasks
    def add_custom_field(self, label, f_type):
        if label in self.taskfields.keys():
            return False, label + " is already a field"
        if label in self.taskattributes.keys():
            return False, label + " is an internal task attribute"

        self.taskfields[label] = f_type
        self.taskdf[label] = None

        self.field_added.emit(label, f_type)
        return True, ""

    # delete a field from tasks
    def delete_custom_field(self, label):
        if label not in self.taskfields.keys():
            return False, label + " isn't an existing field"

        self.taskfields.pop(label)
        self.taskdf.drop(columns=label, inplace=True)

        self.field_deleted.emit(label)
        return True, ""

    # copy current task data for a field to another field
    def copy_field_data(self, from_l, to_l):
        if from_l not in self.taskfields.keys():
            return False, from_l + " isn't an existing field"
        if to_l not in self.taskfields.keys():
            return False, to_l + " isn't an existing field"

        self.taskdf[to_l] = self.taskdf[from_l]

        self.field_data_copied.emit(from_l, to_l)
        return True, ""

    # change the label for a field
    def rename_field(self, old_l, new_l):
        if new_l == old_l:
            return True, "no change made"
        if new_l in self.taskfields.keys():
            return False, new_l + " is already a field"
        if new_l in self.taskattributes.keys():
            return False, new_l + " is an internal task attribute"
        if old_l not in self.taskfields.keys():
            return False, old_l + " isn't an existing field"

        self.taskfields[new_l] = self.taskfields.pop(old_l)
        self.taskdf.rename(columns={old_l: new_l}, inplace=True)

        self.field_renamed.emit(old_l, new_l)
        return True, ""

    # sorter and filter methods should be rewritten to use pandas functionality

    # apply filter to task, return boolean for if the task passes
    def run_filter_on(self, task, filter_string):
        return not self.taskdf.loc[task].completed

    # add task to any filters in which it should belong and remove from any it shouldn't
    def check_against_filters(self, task):
        filters = self.shelfdf.loc[self.shelfdf["is_filter"]]
        filter_strings = filters["filter_string"]
        filter_ids = filters.index
        for string, dfid in zip(filter_strings, filter_ids):
            if self.run_filter_on(task, string):
                if self.nestmat.at[id, task] == 0:
                    self.position_task_in_shelf(task, dfid, filter_override=True)
            else:
                if self.nestmat.at[id, task] != 0:
                    self.position_task_in_shelf(task, dfid, idx=0, filter_override=True)

    # check all tasks against this filter and add or remove ones when necessary
    def refilter_shelf(self, shelf):
        f_string = self.shelfdf.at[shelf, "filter_string"]
        for task in self.taskdf.index:
            if self.run_filter_on(task, f_string):
                if self.nestmat.at[shelf, task] == 0:
                    self.position_task_in_shelf(task, shelf, filter_override=True)
            else:
                if self.nestmat.at[shelf, task] != 0:
                    self.position_task_in_shelf(task, shelf, idx=0, filter_override=True)

    # apply sorter to task, return its resulting integer weight
    def run_sorter_on(self, task, sorter_string):
        return self.taskdf.at[task, "value"]

    # check that the task is in the correct position in all of its sorters, and fix the position if it isn't
    def check_parent_sorters(self, task):
        strip = self.nestmat[task]
        shelves = strip.index[strip.values > 0]
        sorters = self.shelfdf.loc[shelves].loc[self.shelfdf["is_sorter"]]
        sorter_ids = sorters.index
        for dfid in sorter_ids:
            index = self.sort_task_into_shelf(task, dfid)
            if index != self.nestmat.at[dfid, task]:
                self.position_task_in_shelf(task, dfid, idx=index, sorter_override=True)

    # fix positions of tasks in shelf to match  the
    def resort_shelf(self, shelf):
        s_string = self.shelfdf.at[shelf, "sorter_string"]
        strip = self.nestmat.loc[shelf]
        curr_order = strip[strip.values > 0]
        new_order = pd.Series([self.run_sorter_on(x, s_string) for x in curr_order.keys()], curr_order.keys())
        new_order = new_order.sort_values(ascending=False)
        for i, task in enumerate(reversed(new_order.keys())):
            self.position_task_in_shelf(task, shelf, idx=len(new_order)-i, sorter_override=True)

    # given that a shelf is sorted, find the index that the task should be inserted to preserve decreasing order
    def sort_task_into_shelf(self, task, shelf):
        s_string = self.shelfdf.at[shelf, "sorter_string"]
        strip = self.nestmat.loc[shelf]
        curr_order = strip[strip.values > 0]
        new_order = pd.Series([self.run_sorter_on(x, s_string) for x in curr_order.keys()], curr_order.keys())
        new_order = new_order.sort_values(ascending=True)
        return len(new_order)-new_order.searchsorted(self.run_sorter_on(task, s_string), side="right")+1

    # return dict form of tasks
    def get_task_info(self, task_list):
        return self.taskdf.loc[task_list].to_dict("index")

    # return dict form of shelves
    def get_shelf_info(self, shelf_list):
        return self.shelfdf.loc[shelf_list].to_dict("index")

    # return ordered list of shelves in task
    def get_subshelves(self, task):
        strip = self.nestmat[task]
        series = strip[strip.values < 0]
        sorted_list = sorted(series.keys(), key=series.get)
        sorted_list.reverse()
        return sorted_list

    # return ordered list of shelves that own this task
    def get_supershelves(self, task, include_index=False):
        strip = self.nestmat[task]
        series = strip[strip.values > 0]
        if include_index:
            plain_list = list(series.items())
        else:
            plain_list = series.keys()
        return plain_list

    # return ordered list of tasks in shelf
    def get_subtasks(self, shelf):
        strip = self.nestmat.loc[shelf]
        series = strip[strip.values > 0]
        sorted_list = sorted(series.keys(), key=series.get)
        return sorted_list

    # return ordered list of tasks that own this shelf
    def get_supertasks(self, shelf, include_index=False):
        strip = self.nestmat.loc[shelf]
        series = strip[strip.values < 0]
        if include_index:
            plain_list = [(k, -v) for (k, v) in series.items()]
        else:
            plain_list = series.keys()
        return plain_list

    def write_to_file(self, file):
        # write header
        file.write(bytes("<?xml version='1.0' encoding='utf-8'?>\n", 'utf-8'))
        file.write(bytes("<data>\n", 'utf-8'))
        # write shelfdf
        if len(self.shelfdf.index) > 0:
            self.shelfdf.to_xml(file, attr_cols=self.shelfdf.columns.tolist(), root_name="shelves", row_name="shelf",
                                xml_declaration=False)
        else:
            file.write(bytes("<shelves/>\n", 'utf-8'))
        # write taskfields
        if len(self.taskfields) > 0:
            file.write(bytes("<fields>\n", 'utf-8'))
            for (k, v) in self.taskfields:
                file.write(bytes("  <field>" + k + "=" + v + "</field>\n", 'utf-8'))
            file.write(bytes("</fields>\n", 'utf-8'))
        else:
            file.write(bytes("<fields/>\n", 'utf-8'))
        # write taskdf
        if len(self.taskdf.index) > 0:
            self.taskdf.to_xml(file, attr_cols=self.taskdf.columns.tolist(), root_name="tasks", row_name="task",
                               xml_declaration=False)
        else:
            file.write(bytes("<tasks/>\n", 'utf-8'))
        # write nestmat
        if len(self.nestmat.index) > 0:
            self.nestmat.replace(0, None).to_xml(file, attr_cols=self.nestmat.columns.tolist(), root_name="nesting",
                                                 row_name="shelf", xml_declaration=False)
        else:
            file.write(bytes("<nesting/>\n", 'utf-8'))
        # write rack
        if len(self.rack) > 0:
            file.write(bytes("<rack>\n", 'utf-8'))
            for x in self.rack:
                file.write(bytes("  <shelf>"+x+"</shelf>\n", 'utf-8'))
            file.write(bytes("</rack>\n", 'utf-8'))
        else:
            file.write(bytes("<rack/>\n", 'utf-8'))
        # write stage
        if self.stage is not None:
            file.write(bytes("<stage>\n", 'utf-8'))
            file.write(bytes("  <task>"+self.stage+"</task>\n", 'utf-8'))
            file.write(bytes("</stage>\n", 'utf-8'))
        else:
            file.write(bytes("<stage/>\n", 'utf-8'))
        file.write(bytes("</data>\n", 'utf-8'))

    def read_from_file(self, file):
        # only read from structures that exist
        has_data = {}
        # find rack and stage values
        with open(file.name, "r+") as file:
            data = bytes(mmap.mmap(file.fileno(), 0))
            data_sects = ["shelves", "fields", "tasks", "nesting", "rack", "stage"]
            for d_s in data_sects:
                has_data[d_s] = re.search(bytes("<"+d_s+">", 'utf-8'), data) is not None and \
                                re.search(bytes("</"+d_s+">", 'utf-8'), data) is not None

            if has_data["rack"]:
                rack_loc = re.search(re.compile(b"(?<=<rack>).*(?=</rack>)", flags=re.DOTALL), data).span()
                shelf_racks = re.findall(re.compile(b"(?<=<shelf>)\n?.*\n?(?=</shelf>)"), data[rack_loc[0]:rack_loc[1]])
                self.rack = [str(x, 'UTF-8') for x in shelf_racks]
            else:
                self.rack = []

            if has_data["stage"]:
                stage_loc = re.search(re.compile(b"(?<=<stage>).*(?=</stage>)", flags=re.DOTALL), data).span()
                task_stage = re.findall(re.compile(b"(?<=<task>)\n?.*\n?(?=</task>)"), data[stage_loc[0]:stage_loc[1]])
                self.stage = str(task_stage[0], 'UTF-8')
            else:
                self.stage = None

        # open shelf dataframe
        if has_data["shelves"]:
            with open(file.name, "r") as file:
                self.shelfdf = pd.read_xml(file, xpath="/data/shelves/shelf").set_index("index")
                # fix NA data types
                self.shelfdf["filter_string"] = self.shelfdf["filter_string"].fillna("")
                self.shelfdf["sorter_string"] = self.shelfdf["sorter_string"].fillna("")
        else:
            self.shelfdf = pd.DataFrame(columns=list(self.shelfattributes.keys()))

        # read in custom task fields
        if has_data["fields"]:
            fields_loc = re.search(re.compile(b"(?<=<fields>).*(?=</fields>)", flags=re.DOTALL), data).span()
            field_list = re.findall(re.compile(b"(?<=<field>)\n?.*\n?(?=</field>)"), data[fields_loc[0]:fields_loc[1]])
            self.taskfields = {str(x, 'UTF-8').split("=")[0]:str(x, 'UTF-8').split("=")[1] for x in field_list}

        # open task dataframe
        if has_data["tasks"]:
            with open(file.name, "r") as file:
                self.taskdf = pd.read_xml(file, xpath="/data/tasks/task").set_index("index")

            # add fields missing from task df
            missing_col = pd.Series([fi for fi in self.taskfields.keys() if fi not in self.taskdf.columns])
            mis_c_df = pd.DataFrame(columns=missing_col)
            self.taskdf = pd.concat([self.taskdf, mis_c_df], axis=1)
        else:
            self.taskdf = pd.DataFrame(columns=list(self.taskattributes)+list(self.taskfields))

        # open nesting matrix
        if has_data["nesting"]:
            with open(file.name, "r") as file:
                self.nestmat = (pd.read_xml(file, xpath="/data/nesting/shelf")  # read entries
                                  .set_index("index")  # set dataframe index to index column
                                  .fillna(0)  # replace missing values with 0 (for no nesting)
                                  .astype(int))  # convert floats to integers

                # add shelves missing from matrix
                missing_row = pd.Series([si for si in self.shelfdf.index if si not in self.nestmat.index])
                mis_r_df = pd.DataFrame(index=missing_row)
                self.nestmat = pd.concat([self.nestmat, mis_r_df])

                # add tasks missing from matrix
                missing_col = pd.Series([ti for ti in self.taskdf.index if ti not in self.nestmat.columns])
                mis_c_df = pd.DataFrame(columns=missing_col)
                self.nestmat = pd.concat([self.nestmat, mis_c_df], axis=1)

                self.nestmat = self.nestmat.fillna(0.0)
        else:
            self.nestmat = pd.DataFrame()

        self.new_model_loaded.emit(self.stage if self.stage is not None else "", self.rack)
