# TOOD_App
To-do list application which uses shelves to organize tasks. Will include automatic sorting and filtering of tasks based on custom rules.

Uses MVC pattern with a PyQT5 GUI and task information stored in pandas dataframes that load and save to a .TOOD xml file.

Tasks can be created, edited, and marked complete/incomplete to keep track of and organize them.

TOOD uses shelves, which hold tasks and are placed on the main rack.
Subtask trees can be created by putting a shelf inside of a task, and then adding tasks to it.
Because tasks can be added to shelves and shelves can be added to tasks, complex nested organization patterns can be easily created with the drag-and-drop feature.

TOOD supports moving, linking, and duplicating both tasks and shelves, using left, right, and middle mouse buttons.
Linking a widget creates a new widget that references the same model data - meaning if one of the linked widgets is edited, they all update to reflect the change.
This is useful for complex organization of tasks.

Next Steps:
- Customizable data fields for tasks
- Custom Filtering and Sorting language that determine which widgets appear in a shelf and what order they appear in
- Better tools for keeping track of task progress
- Purging unneeded tasks from the .TOOD file
- Improved saving and loading of TOOD boards
