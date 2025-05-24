import pyqtgraph as pg
import numpy as np

PEN_WIDTH = 2

class PhasePlotItem:
    def __init__(self, source_x, var_name_x, source_y, var_name_y, pen, name=None):
        self.source_x = source_x
        self.var_name_x = var_name_x
        self.source_y = source_y
        self.var_name_y = var_name_y
        self.pen = pen if pen is not None else pg.mkPen(color='w', width=PEN_WIDTH)
        self._name = name if name is not None else f"{var_name_x} vs {var_name_y}"

        # Assume source has model() and get_data_by_name()
        # and that get_data_by_name returns a numpy array
        self.data_x = self.source_x.model().get_data_by_name(self.var_name_x)
        self.data_y = self.source_y.model().get_data_by_name(self.var_name_y)

        if self.data_x is None:
            self.data_x = np.array([])
            print(f"Warning: Data for {self.var_name_x} not found.")
        if self.data_y is None:
            self.data_y = np.array([])
            print(f"Warning: Data for {self.var_name_y} not found.")

        self.plot_data_item = pg.PlotDataItem(self.data_x, self.data_y, pen=self.pen, name=self._name)

    def update_data(self, source_x, var_name_x, source_y, var_name_y):
        self.source_x = source_x
        self.var_name_x = var_name_x
        self.source_y = source_y
        self.var_name_y = var_name_y

        new_data_x = self.source_x.model().get_data_by_name(self.var_name_x)
        new_data_y = self.source_y.model().get_data_by_name(self.var_name_y)

        self.data_x = new_data_x if new_data_x is not None else np.array([])
        self.data_y = new_data_y if new_data_y is not None else np.array([])
        
        if new_data_x is None:
            print(f"Warning: Data for {self.var_name_x} not found during update.")
        if new_data_y is None:
            print(f"Warning: Data for {self.var_name_y} not found during update.")

        self.plot_data_item.setData(self.data_x, self.data_y)
        # Update name if it was default and var names changed
        if self._name == f"{self.var_name_x} vs {self.var_name_y}" or self._name == f"{var_name_x} vs {var_name_y}": # old default name
             self._name = f"{self.var_name_x} vs {self.var_name_y}"
             # self.plot_data_item.opts['name'] = self._name # Not directly settable, might need to recreate or manage legend separately

    def setPen(self, pen):
        self.pen = pen
        self.plot_data_item.setPen(self.pen)

    def name(self):
        return self._name

    def get_data_at_tick(self, tick_index):
        # Check if data_x and data_y are valid and have data
        if self.data_x is None or self.data_y is None:
            return None
        
        len_x = len(self.data_x)
        len_y = len(self.data_y)

        if tick_index < 0: # Allow negative indexing? For now, no.
            return None

        # Handle cases where one or both datasets might be too short or empty
        if tick_index >= len_x or tick_index >= len_y:
            # If one is long enough, should we return partial data or None?
            # For an X-Y plot, both are needed.
            return None
        
        # Handle empty arrays specifically, though len check above should cover it.
        if len_x == 0 or len_y == 0:
            return None

        return self.data_x[tick_index], self.data_y[tick_index]

    def get_plot_spec(self):
        # Assuming self.source_x and self.source_y are objects (e.g., DataFile instances)
        # that have a .filename attribute.
        source_x_filename = None
        if hasattr(self.source_x, 'filename'):
            source_x_filename = self.source_x.filename
        else:
            print(f"Warning: source_x for '{self.var_name_x}' does not have a 'filename' attribute. Plot spec may be incomplete.")

        source_y_filename = None
        if hasattr(self.source_y, 'filename'):
            source_y_filename = self.source_y.filename
        else:
            print(f"Warning: source_y for '{self.var_name_y}' does not have a 'filename' attribute. Plot spec may be incomplete.")

        return {
            'source_x_id': source_x_filename, # Changed from x_source_name
            'x_var': self.var_name_x,
            'source_y_id': source_y_filename, # Changed from y_source_name
            'y_var': self.var_name_y,
            'color': self.pen.color().name(),  # e.g., '#FF0000'
            'width': self.pen.width(),
            'name': self._name
        }

    # It might be useful to have a method to get the actual PlotDataItem
    # for adding to a plot widget.
    def get_qt_item(self):
        return self.plot_data_item
