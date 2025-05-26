import pytest
from PyQt5.QtWidgets import QApplication, QWidget # QApplication is needed for qapp fixture if not already managed
from PyQt5.QtGui import QPalette
import sys
import os
import numpy as np
import pyqtgraph

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Attempt to import target classes
try:
    from sub_plot_widget import SubPlotWidget
    from custom_plot_item import CustomPlotItem
except ImportError as e:
    print(f"Failed to import SubPlotWidget or CustomPlotItem: {e}. Check sys.path and file locations.")
    SubPlotWidget = None
    CustomPlotItem = None

# Add a pytest mark to skip all tests in this module if SubPlotWidget is not available
if SubPlotWidget is None or CustomPlotItem is None:
    pytestmark = pytest.mark.skip(reason="SubPlotWidget or CustomPlotItem not importable, skipping all tests in this file.")

# --- Mock Classes (remain at module level) ---
class MockSignal:
    def connect(self, slot): pass
    def disconnect(self, slot): pass
    def emit(self, *args): pass

class MockRangeSlider(QWidget):
    def __init__(self):
        super().__init__()
        self.minValueChanged = MockSignal()
        self.maxValueChanged = MockSignal()
    def min(self): return 0.0
    def max(self): return 1.0
    def start(self): return 0.0
    def end(self): return 1.0

class MockTabs(QWidget):
    def __init__(self):
        super().__init__()
    def currentIndex(self): return 0

class MockPlotManager(QWidget):
    def __init__(self):
        super().__init__()
        self._time = 0.0
        self._tick = 0
        self.timeValueChanged = MockSignal()
        self.range_slider = MockRangeSlider()
        self._controller = None 
        self.tabs = MockTabs()

class MockPlotAreaWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._plot_manager_instance = MockPlotManager()
    def plot_manager(self): return self._plot_manager_instance
    def add_subplot_above(self, subplot): pass
    def add_subplot_below(self, subplot): pass
    def remove_subplot(self, subplot): pass
    def update_plot_xrange(self, val=None): pass

class MockDataSource:
    def __init__(self, time_data, y_data_dict):
        self.time = time_data
        self._y_data_dict = y_data_dict
        self.onClose = MockSignal()
        self.idx = None

    def model(self): 
        return self 
    
    def get_data_by_name(self, name):
        return self._y_data_dict.get(name)

# --- Pytest Fixture ---
@pytest.fixture
def subplot_widget_setup(qapp): # qapp is a standard fixture from pytest-qt
    # Create mock parent
    mock_parent_plot_area = MockPlotAreaWidget()
    
    widget = SubPlotWidget(parent=mock_parent_plot_area, object_name_override="test_subplot_pytest")
    
    yield widget # Provide the widget to the test
    
    # Teardown
    widget.deleteLater()
    mock_parent_plot_area.deleteLater()

# --- Test Functions ---
def test_instantiation(subplot_widget_setup):
    '''Test if a SubPlotWidget can be instantiated.'''
    subplot_widget = subplot_widget_setup
    assert subplot_widget is not None, "SubPlotWidget should be created."
    assert isinstance(subplot_widget, SubPlotWidget), "Widget should be an instance of SubPlotWidget."

def test_add_trace_programmatic(subplot_widget_setup):
    '''Test programmatically adding a trace to SubPlotWidget.'''
    subplot_widget = subplot_widget_setup
    
    # Prepare mock data
    time_data = np.array([0.0, 0.1, 0.2, 0.3])
    y_data = np.array([1.0, 1.5, 1.3, 1.8])
    trace_name = "test_signal_1"
    
    mock_source = MockDataSource(time_data, {trace_name: y_data})

    # Call plot_data_from_source
    subplot_widget.plot_data_from_source(trace_name, mock_source)

    # Verifications
    assert len(subplot_widget._traces) == 1, "One trace should be in _traces list."
    assert isinstance(subplot_widget._traces[0], CustomPlotItem), "_traces item should be a CustomPlotItem."
    
    assert subplot_widget._traces[0].text().startswith(trace_name), \
                    f"Label text should start with trace name. Got: '{subplot_widget._traces[0].text()}'"
    
    assert subplot_widget._labels.count() == 1, "One label widget should be in FlowLayout."
    label_widget_in_layout = subplot_widget._labels.itemAt(0).widget()
    assert isinstance(label_widget_in_layout, CustomPlotItem), "Widget in layout should be CustomPlotItem."
    assert label_widget_in_layout == subplot_widget._traces[0], "Label in layout should be same instance as in _traces."

    expected_color_str = SubPlotWidget.COLORS[0]
    plot_data_item_pen = subplot_widget._traces[0].trace.opts['pen']
    assert plot_data_item_pen.color().name() == expected_color_str, "PlotDataItem pen color incorrect."
    
    label_palette_color = label_widget_in_layout.palette().color(QPalette.WindowText)
    assert label_palette_color.name() == expected_color_str, "Label text color incorrect."
    
    num_plot_items = 0
    for item in subplot_widget.pw.getPlotItem().items:
        if isinstance(item, pyqtgraph.PlotDataItem):
            num_plot_items +=1
    assert num_plot_items == 1, "PlotWidget should have 1 PlotDataItem."
    
    found_plot_data_item = False
    for item in subplot_widget.pw.getPlotItem().items:
        if isinstance(item, pyqtgraph.PlotDataItem) and item.name() == trace_name:
            found_plot_data_item = True
            break
    assert found_plot_data_item, "PlotDataItem with correct name was not added to pyqtgraph PlotItem."

def test_remove_trace_programmatic(subplot_widget_setup):
    '''Test programmatically removing a trace from SubPlotWidget.'''
    subplot_widget = subplot_widget_setup

    # 1. Add a trace first
    time_data = np.array([0.0, 0.1, 0.2, 0.3])
    y_data1 = np.array([1.0, 1.5, 1.3, 1.8])
    trace_name1 = "test_signal_to_remove"
    
    mock_source1 = MockDataSource(time_data, {trace_name1: y_data1})
    subplot_widget.plot_data_from_source(trace_name1, mock_source1)

    assert len(subplot_widget._traces) == 1, "Trace should be added before removal."
    added_label_item = subplot_widget._traces[0]
    added_pg_trace_item = added_label_item.trace

    # 2. Add a second trace
    y_data2 = np.array([2.0, 2.5, 2.3, 2.8])
    trace_name2 = "test_signal_remaining"
    mock_source2 = MockDataSource(time_data, {trace_name2: y_data2})
    subplot_widget.plot_data_from_source(trace_name2, mock_source2)

    assert len(subplot_widget._traces) == 2, "Two traces should be present before removal."

    # 3. Call remove_item for the first trace
    print(f"DEBUG_TEST: Attempting to remove trace '{trace_name1}'")
    subplot_widget.remove_item(added_pg_trace_item, added_label_item, is_move_operation=False)
    print(f"DEBUG_TEST: Called remove_item for '{trace_name1}'")

    # 4. Verifications after removal
    assert len(subplot_widget._traces) == 1, "One trace should remain in _traces list."
    assert added_label_item not in subplot_widget._traces, "Removed label should not be in _traces."
    
    assert subplot_widget._labels.count() == 1, "One label widget should remain in FlowLayout."
    remaining_label_in_layout = subplot_widget._labels.itemAt(0).widget()
    assert remaining_label_in_layout.text().startswith(trace_name2), \
                    f"Remaining label text incorrect. Expected to start with '{trace_name2}', got '{remaining_label_in_layout.text()}'"
    assert remaining_label_in_layout == subplot_widget._traces[0], "Remaining label in layout should match _traces."

    expected_color_str = SubPlotWidget.COLORS[0] # Color should reset to the first color for the remaining trace
    remaining_pg_item_pen = subplot_widget._traces[0].trace.opts['pen']
    assert remaining_pg_item_pen.color().name() == expected_color_str, "Remaining PlotDataItem pen color incorrect after removal."
    remaining_label_palette_color = remaining_label_in_layout.palette().color(QPalette.WindowText)
    assert remaining_label_palette_color.name() == expected_color_str, "Remaining label text color incorrect after removal."
    
    plot_data_item_count = 0
    for item in subplot_widget.pw.getPlotItem().items:
        if isinstance(item, pyqtgraph.PlotDataItem):
            plot_data_item_count += 1
    assert plot_data_item_count == 1, "PlotWidget should have 1 PlotDataItem remaining."
    
    found_removed_pg_item = False
    for item in subplot_widget.pw.getPlotItem().items:
        if item == added_pg_trace_item:
            found_removed_pg_item = True
            break
    assert not found_removed_pg_item, "Removed pyqtgraph PlotDataItem instance should not be in PlotItem's items."

def test_add_and_remove_multiple_traces(subplot_widget_setup):
    '''Tests adding multiple traces, removing one from the middle, and verifying state.'''
    subplot_widget = subplot_widget_setup # Get the widget from the fixture

    # Mock data
    time_data = np.array([0.0, 0.1, 0.2, 0.3])
    trace_data = {
        "S1": np.array([1.0, 1.1, 1.2, 1.3]),
        "S2": np.array([2.0, 2.1, 2.2, 2.3]),
        "S3": np.array([3.0, 3.1, 3.2, 3.3])
    }
    
    source_s1 = MockDataSource(time_data, {"S1": trace_data["S1"]})
    source_s2 = MockDataSource(time_data, {"S2": trace_data["S2"]})
    source_s3 = MockDataSource(time_data, {"S3": trace_data["S3"]})

    # 1. Add three traces
    subplot_widget.plot_data_from_source("S1", source_s1)
    subplot_widget.plot_data_from_source("S2", source_s2)
    subplot_widget.plot_data_from_source("S3", source_s3)

    # Verify initial state
    assert len(subplot_widget._traces) == 3
    assert subplot_widget._traces[0].trace.name() == "S1"
    assert subplot_widget._traces[1].trace.name() == "S2"
    assert subplot_widget._traces[2].trace.name() == "S3"
    
    # Check initial colors (optional, but good for consistency)
    assert subplot_widget._traces[0].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[0]
    assert subplot_widget._traces[1].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[1]
    assert subplot_widget._traces[2].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[2]

    # Store references to items for removal
    label_s1 = subplot_widget._traces[0]
    trace_s1_pg = label_s1.trace # pyqtgraph item
    label_s2 = subplot_widget._traces[1]
    trace_s2_pg = label_s2.trace
    # label_s3 = subplot_widget._traces[2] # Not needed if removing S2

    # 2. Remove the middle trace (S2)
    print("DEBUG_TEST: Removing middle trace 'S2'")
    subplot_widget.remove_item(trace_s2_pg, label_s2, is_move_operation=False)

    # Verify state after removing S2
    assert len(subplot_widget._traces) == 2
    assert subplot_widget._traces[0].trace.name() == "S1"
    assert subplot_widget._traces[1].trace.name() == "S3"
    
    # Verify colors of remaining traces (S1 should be COLORS[0], S3 should be COLORS[1])
    assert subplot_widget._traces[0].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[0], "S1 color wrong after S2 removal"
    assert subplot_widget._traces[1].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[1], "S3 color wrong after S2 removal"
    
    # Verify labels in FlowLayout
    assert subplot_widget._labels.count() == 2
    assert subplot_widget._labels.itemAt(0).widget().trace.name() == "S1"
    assert subplot_widget._labels.itemAt(1).widget().trace.name() == "S3"

    # Verify pyqtgraph PlotDataItems
    pg_item_names = [item.name() for item in subplot_widget.pw.getPlotItem().items if isinstance(item, pyqtgraph.PlotDataItem)]
    assert sorted(pg_item_names) == sorted(["S1", "S3"]), "Incorrect PlotDataItems in pyqtgraph plot after S2 removal"

    # 3. (Optional) Remove another trace (e.g., S1 - the first one)
    print("DEBUG_TEST: Removing first trace 'S1'")
    subplot_widget.remove_item(trace_s1_pg, label_s1, is_move_operation=False)
    
    # Verify state after removing S1
    assert len(subplot_widget._traces) == 1
    assert subplot_widget._traces[0].trace.name() == "S3"
    assert subplot_widget._traces[0].trace.opts['pen'].color().name() == SubPlotWidget.COLORS[0], "S3 color wrong after S1 removal"
    
    assert subplot_widget._labels.count() == 1
    assert subplot_widget._labels.itemAt(0).widget().trace.name() == "S3"

    pg_item_names_final = [item.name() for item in subplot_widget.pw.getPlotItem().items if isinstance(item, pyqtgraph.PlotDataItem)]
    assert pg_item_names_final == ["S3"], "Incorrect PlotDataItems in pyqtgraph plot after S1 removal"

# Note: Removed 'if __name__ == "__main__": unittest.main()' as pytest handles test discovery and execution.
