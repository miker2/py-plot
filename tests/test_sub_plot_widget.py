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

# Qt imports for mock events and mime data
from PyQt5.QtCore import QMimeData, QByteArray, QPoint, Qt # QVariant removed as it seems unused
from PyQt5.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
import pickle # For pickling data for mime types

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
    def __init__(self, time_data, y_data_dict, var_name=None):
        self.time = time_data
        self._y_data_dict = y_data_dict
        self.var_name = var_name # Added var_name attribute
        self.onClose = MockSignal()
        self.idx = None

    def model(self):
        return self

    def get_data_by_name(self, name):
        return self._y_data_dict.get(name)

# --- Helper Functions for Test Setup and Assertions ---

def _add_traces_to_subplot(subplot_widget: SubPlotWidget, traces_config: dict,
                           common_time_data: np.ndarray = None) -> dict[str, CustomPlotItem]:
    """
    Adds multiple traces to a subplot based on a configuration dictionary.

    Args:
        subplot_widget: The SubPlotWidget instance to add traces to.
        traces_config: A dictionary where keys are trace names and values are
                       either numpy arrays (for y_data, assuming common_time_data is provided)
                       or tuples of (time_data, y_data).
        common_time_data: Optional common time data if not specified per trace in traces_config.

    Returns:
        A dictionary mapping trace names to the created CustomPlotItem instances.
    """
    added_custom_plot_items = {}
    for trace_name, data_info in traces_config.items():
        if isinstance(data_info, tuple) and len(data_info) == 2:
            time_data, y_data = data_info
        elif common_time_data is not None:
            time_data = common_time_data
            y_data = data_info
        else:
            raise ValueError(f"Missing time_data for trace '{trace_name}' and no common_time_data provided.")

        # Construct var_name for MockDataSource for completeness, though not strictly used by plot_data_from_source
        var_name_src = f"{trace_name}_src"
        mock_source = MockDataSource(time_data, {trace_name: y_data}, var_name=var_name_src)
        subplot_widget.plot_data_from_source(trace_name, mock_source)
        if subplot_widget._traces and subplot_widget._traces[-1].trace.name() == trace_name:
            added_custom_plot_items[trace_name] = subplot_widget._traces[-1]
        else:
            # This case should ideally not happen if plot_data_from_source works correctly
            raise RuntimeError(f"Failed to retrieve CustomPlotItem for trace '{trace_name}' after adding.")
    return added_custom_plot_items

def _assert_trace_order_and_colors(subplot_widget: SubPlotWidget, expected_trace_names: list[str]):
    """
    Asserts the order and colors of traces in a SubPlotWidget.

    Args:
        subplot_widget: The SubPlotWidget to check.
        expected_trace_names: A list of trace names in the expected order.
    """
    assert len(subplot_widget._traces) == len(expected_trace_names), \
        f"Expected {len(expected_trace_names)} traces, got {len(subplot_widget._traces)}"
    
    actual_trace_names = [t.trace.name() for t in subplot_widget._traces]
    assert actual_trace_names == expected_trace_names, \
        f"Trace name order mismatch. Expected {expected_trace_names}, got {actual_trace_names}"

    for i, trace_name in enumerate(expected_trace_names):
        custom_plot_item = subplot_widget._traces[i]
        expected_color_obj = pyqtgraph.mkColor(SubPlotWidget.COLORS[i % len(SubPlotWidget.COLORS)])
        expected_color_name = expected_color_obj.name()

        # Verify CustomPlotItem (label) properties
        assert custom_plot_item.trace.name() == trace_name, \
            f"Trace at index {i} expected name '{trace_name}', got '{custom_plot_item.trace.name()}'"
        assert custom_plot_item.palette().color(QPalette.WindowText).name() == expected_color_name, \
            f"Label color for trace '{trace_name}' (index {i}) incorrect. Expected {expected_color_name}, " \
            f"got {custom_plot_item.palette().color(QPalette.WindowText).name()}"

        # Verify pyqtgraph.PlotDataItem properties
        assert custom_plot_item.trace.opts['pen'].color().name() == expected_color_name, \
            f"PlotDataItem pen color for trace '{trace_name}' (index {i}) incorrect. Expected {expected_color_name}, " \
            f"got {custom_plot_item.trace.opts['pen'].color().name()}"
        
        # Verify label order in FlowLayout
        label_in_layout = subplot_widget._labels.itemAt(i).widget()
        assert isinstance(label_in_layout, CustomPlotItem)
        assert label_in_layout.trace.name() == trace_name, \
            f"Label in layout at index {i} expected name '{trace_name}', got '{label_in_layout.trace.name()}'"


# --- Helper Functions for MimeData and Events ---
def create_data_item_mime_data(data_source_name: str) -> QMimeData:
    """
    Creates QMimeData for dragging a new data source (e.g., from VarListWidget).
    MIME type: "application/x-DataItem"
    """
    mime_data = QMimeData()
    # Create a simple object that mimics the expected DataItem structure
    # The important part for the dropEvent in SubPlotWidget is `selected.var_name`
    mock_data_item = type('MockDataItem', (object,), {'var_name': data_source_name})()
    pickled_data = pickle.dumps(mock_data_item)
    mime_data.setData("application/x-DataItem", QByteArray(pickled_data))
    return mime_data

def create_custom_plot_item_mime_data(plot_name: str) -> QMimeData:
    """
    Creates QMimeData for dragging an existing CustomPlotItem (trace label).
    MIME type: "application/x-customplotitem"
    """
    mime_data = QMimeData()
    mime_data.setText(plot_name) # Set plot_name as text
    # The actual format string used in setFormat might differ,
    # but setText is a common way if it's just string data.
    # If a specific format string is critical, adjust accordingly.
    # For now, let's assume setText is sufficient or we adjust if tests fail.
    # Based on sub_plot_widget.py, it expects text data for this type.
    mime_data.setData("application/x-customplotitem", QByteArray(plot_name.encode()))
    return mime_data

def create_unrecognized_mime_data() -> QMimeData:
    """
    Creates QMimeData with an unrecognized format for testing ignore behavior.
    MIME type: "application/x-unknown"
    """
    mime_data = QMimeData()
    mime_data.setData("application/x-unknown", QByteArray(b"unknown_data"))
    return mime_data

def create_mock_drag_enter_event(mime_data: QMimeData, pos: QPoint,
                                 possible_actions=Qt.MoveAction) -> QDragEnterEvent:
    """
    Creates a mock QDragEnterEvent.
    The event is initialized as not accepted; the widget handler should call acceptProposedAction().
    """
    # Constructor: QDragEnterEvent(pos, possibleActions, mimeData, buttons, modifiers)
    event = QDragEnterEvent(pos, possible_actions, mime_data, Qt.NoButton, Qt.NoModifier)
    event.setAccepted(False) 
    return event

def create_mock_drag_move_event(mime_data: QMimeData, pos: QPoint,
                                possible_actions=Qt.MoveAction) -> QDragMoveEvent:
    """
    Creates a mock QDragMoveEvent.
    The widget handler should call accept() or ignore().
    """
    # Constructor: QDragMoveEvent(pos, possibleActions, mimeData, buttons, modifiers)
    event = QDragMoveEvent(pos, possible_actions, mime_data, Qt.NoButton, Qt.NoModifier)
    # event.setAccepted(False) # QDragMoveEvent doesn't have setAccepted directly like QDragEnterEvent
    return event

def create_mock_drop_event(mime_data: QMimeData, pos: QPoint, 
                           source_widget: QWidget = None, # Though not directly settable on event via constructor
                           possible_actions=Qt.MoveAction,
                           proposed_action=Qt.MoveAction) -> QDropEvent:
    """
    Creates a mock QDropEvent.
    The `proposed_action` is set on the event. The widget handler should call acceptProposedAction().
    The `source_widget` parameter is conceptual for clarity; actual event.source() often needs patching.
    """
    # Constructor: QDropEvent(pos, possibleActions, mimeData, buttons, modifiers)
    event = QDropEvent(pos, possible_actions, mime_data, Qt.NoButton, Qt.NoModifier)
    event.setDropAction(proposed_action)
    # event.setAccepted(False) # Default for QDropEvent is not accepted until explicitly accepted.
    # Note: source_widget is not directly used to set event.source() here due to Qt limitations.
    # It's typically mocked on the event instance using mocker.patch.object(event, 'source', ...).
    return event

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

def test_drag_data_item_to_subplot(subplot_widget_setup, mocker):
    '''Test dragging a DataItem (from VarListWidget) onto SubPlotWidget.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup
    trace_name = "temperature_sensor"
    time_data = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    y_data = np.array([20.0, 20.5, 21.0, 20.8, 21.2])

    # Mock the source widget (VarListWidget) and its model (DataSource)
    # The dropEvent in SubPlotWidget expects event.source() to be the VarListWidget,
    # and event.source().model() to be the DataSource.
    mock_var_list_widget = QWidget() # Mock of VarListWidget
    mock_data_source = MockDataSource(time_data, {trace_name: y_data}, var_name=trace_name)
    # Use mocker to make mock_var_list_widget.model() return our mock_data_source
    mocker.patch.object(mock_var_list_widget, 'model', return_value=mock_data_source)


    mime_data = create_data_item_mime_data(data_source_name=trace_name)
    drop_pos = QPoint(10, 10)

    # 2. Simulate Drag and Drop
    # Drag Enter Event
    drag_enter_event = create_mock_drag_enter_event(mime_data, drop_pos)
    subplot_widget.dragEnterEvent(drag_enter_event)
    assert drag_enter_event.isAccepted(), "dragEnterEvent should be accepted for DataItem"

    # Drag Move Event
    drag_move_event = create_mock_drag_move_event(mime_data, drop_pos)
    subplot_widget.dragMoveEvent(drag_move_event)
    assert drag_move_event.isAccepted(), "dragMoveEvent should be accepted for DataItem"

    # Drop Event
    # The QDropEvent's source() method is important here.
    # We need to ensure that event.source() returns an object that has a model() method,
    # which in turn returns our mock_data_source.
    # The create_mock_drop_event doesn't directly set event.source() in a way
    # that the C++ Qt internals would for a real drag.
    # We will mock the SubPlotWidget's plot_data_from_source method to verify it's called,
    # or rely on the side effects (trace added).
    # For a more direct test of source(), we might need to patch QDropEvent.source().
    # However, SubPlotWidget.dropEvent directly calls self.plot_data_from_source
    # with data_name and data_source (which is event.source().model()).
    # So, if plot_data_from_source works as expected, this implies the interaction was correct.

    # To make event.source() work as expected by subplot_widget.dropEvent:
    # event.source() should return an object (the VarListWidget mock)
    # that has a .model() method returning the DataSource.
    # The QDropEvent constructor doesn't allow setting source directly in PyQt.
    # We'll pass our mock_var_list_widget to create_mock_drop_event,
    # but it's for conceptual clarity as the helper doesn't use it to set event.source().
    # Instead, we will rely on the fact that SubPlotWidget will call plot_data_from_source,
    # and we've set up mock_data_source correctly.
    # The critical part is that plot_data_from_source gets the correct data_name and data_source.
    # The data_name comes from the mimeData. The data_source comes from event.source().model().

    # To properly simulate the event.source().model() call within dropEvent,
    # we need to ensure that when the dropEvent occurs, the event object's source()
    # method can be called and it returns our mock_var_list_widget.
    # This is tricky because QDropEvent.source() is a C++ method.
    # A practical way is to use mocker.patch.object on the event instance if possible,
    # or ensure the calling context provides the source.
    # The SubPlotWidget's dropEvent implementation is:
    #   source_widget = event.source()
    #   data_source = source_widget.model()
    #   self.plot_data_from_source(data_name, data_source)
    # We need event.source() to return mock_var_list_widget.

    drop_event = create_mock_drop_event(mime_data, drop_pos, source_widget=mock_var_list_widget) # Pass mock_var_list_widget
    
    # Mock the event.source() call specifically for this event instance
    # This is a bit of a workaround because QDropEvent is a C++ wrapped object.
    # A cleaner way might involve a more complex setup or patching where source() is called.
    # For now, let's assume the call to plot_data_from_source is the main integration point.
    # We will patch `event.source` if `create_mock_drop_event` cannot set it up.
    # The `create_mock_drop_event` currently doesn't set `source()` to be retrievable.
    # We will directly patch the `source` method of the created `drop_event` object.
    mocker.patch.object(drop_event, 'source', return_value=mock_var_list_widget)

    subplot_widget.dropEvent(drop_event)
    assert drop_event.isAccepted(), "dropEvent should be accepted for DataItem"

    # 3. Verification
    assert len(subplot_widget._traces) == 1, "One trace should be added to _traces list."
    custom_plot_item = subplot_widget._traces[0]
    assert isinstance(custom_plot_item, CustomPlotItem), "_traces item should be a CustomPlotItem."

    assert custom_plot_item.text().startswith(trace_name), \
        f"Label text should start with trace name. Got: '{custom_plot_item.text()}'"

    assert subplot_widget._labels.count() == 1, "One label widget should be in FlowLayout."
    label_widget_in_layout = subplot_widget._labels.itemAt(0).widget()
    assert label_widget_in_layout == custom_plot_item, "Label in layout should be the same instance."

    # Check pyqtgraph.PlotDataItem
    pg_plot_item = None
    for item in subplot_widget.pw.getPlotItem().items:
        if isinstance(item, pyqtgraph.PlotDataItem) and item.name() == trace_name:
            pg_plot_item = item
            break
    assert pg_plot_item is not None, f"PlotDataItem with name '{trace_name}' not found in pyqtgraph PlotItem."

    # Verify data in PlotDataItem
    # pg_plot_item.yData might not be exactly the same object due to pyqtgraph processing,
    # but the values should match.
    assert np.array_equal(pg_plot_item.yData, y_data), "Y-data in PlotDataItem does not match source."
    # Time data (xData) is also set by plot_data_from_source using data_source.time
    assert np.array_equal(pg_plot_item.xData, time_data), "X-data in PlotDataItem does not match source."


    # Verify color
    expected_color_str = SubPlotWidget.COLORS[0]
    assert pg_plot_item.opts['pen'].color().name() == expected_color_str, "PlotDataItem pen color incorrect."
    label_palette_color = custom_plot_item.palette().color(QPalette.WindowText)
    assert label_palette_color.name() == expected_color_str, "Label text color incorrect."

def test_reorder_custom_plot_item_same_subplot(subplot_widget_setup, mocker):
    '''Test reordering a CustomPlotItem (trace) within the same SubPlotWidget.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup: Add three traces
    common_time_data = np.array([0.0, 0.1, 0.2])
    traces_to_add = {
        "TraceA": np.array([1,2,3]),
        "TraceB": np.array([4,5,6]),
        "TraceC": np.array([7,8,9])
    }
    added_items = _add_traces_to_subplot(subplot_widget, traces_to_add, common_time_data)
    _assert_trace_order_and_colors(subplot_widget, ["TraceA", "TraceB", "TraceC"])
    
    dragged_label = added_items["TraceA"] # This is "TraceA" CustomPlotItem
    assert dragged_label._subplot_widget == subplot_widget # Ensure it's correctly parented

    # 2. Simulate Drag and Drop for Reordering "TraceA" to the end
    mime_data = create_custom_plot_item_mime_data(dragged_label.trace.name())
    # Drop position within the label area (FlowLayout). The exact point is less critical
    # here as _get_drop_index is mocked to control insertion point.
    drop_pos = QPoint(10, subplot_widget.flow_layout_widget.height() // 2 if subplot_widget.flow_layout_widget.height() > 0 else 10)

    # Mock _get_drop_index to simulate dropping "TraceA" to become the last item.
    # If "TraceA" (index 0) is dragged, and we want it at the end of [A, B, C] (effectively index 2),
    # _get_drop_index should return 2.
    mocker.patch.object(subplot_widget, '_get_drop_index', return_value=2)

    # Drag Enter
    drag_enter_event = create_mock_drag_enter_event(mime_data, drop_pos)
    subplot_widget.dragEnterEvent(drag_enter_event)
    assert drag_enter_event.isAccepted(), "dragEnterEvent should be accepted for CustomPlotItem reorder"

    # Drag Move
    drag_move_event = create_mock_drag_move_event(mime_data, drop_pos)
    subplot_widget.dragMoveEvent(drag_move_event)
    assert drag_move_event.isAccepted(), "dragMoveEvent should be accepted for CustomPlotItem reorder"

    # Drop Event
    # The source of the event must be the dragged_label (CustomPlotItem) itself.
    drop_event = create_mock_drop_event(mime_data, drop_pos, source_widget=dragged_label, proposed_action=Qt.MoveAction)
    mocker.patch.object(drop_event, 'source', return_value=dragged_label) # Critical mock for event.source()
    
    subplot_widget.dropEvent(drop_event)
    assert drop_event.isAccepted(), "dropEvent should be accepted for CustomPlotItem reorder"

    # 3. Verification
    _assert_trace_order_and_colors(subplot_widget, ["TraceB", "TraceC", "TraceA"])

def test_move_custom_plot_item_between_subplots(qapp, mocker): # qapp for event loop
    '''Test moving a CustomPlotItem from one SubPlotWidget to another.'''
    mock_parent_source = MockPlotAreaWidget()
    source_subplot = SubPlotWidget(parent=mock_parent_source, object_name_override="subplot_source")
    mock_parent_target = MockPlotAreaWidget()
    target_subplot = SubPlotWidget(parent=mock_parent_target, object_name_override="subplot_target")

    try:
        # 1. Setup
        trace_name = "MovableTrace"
        time_data = np.array([0.0, 0.1, 0.2])
        y_data = np.array([10, 20, 30])
        mock_data_source = MockDataSource(time_data, {trace_name: y_data}, var_name="MovableTrace_src")

        source_subplot.plot_data_from_source(trace_name, mock_data_source)

        # Initial verification
        assert len(source_subplot._traces) == 1
        assert source_subplot._traces[0].trace.name() == trace_name
        assert len(target_subplot._traces) == 0
        dragged_label = source_subplot._traces[0] # This is the CustomPlotItem
        assert dragged_label._subplot_widget == source_subplot
        
        # Spy on signal connections
        # CustomPlotItem.on_time_changed is the slot connected to PlotManager.timeValueChanged
        # We need to spy on the connect/disconnect methods of the MockSignal instances
        source_plot_manager_time_signal = source_subplot.parent().plot_manager().timeValueChanged
        target_plot_manager_time_signal = target_subplot.parent().plot_manager().timeValueChanged

        spy_source_disconnect = mocker.spy(source_plot_manager_time_signal, 'disconnect')
        spy_target_connect = mocker.spy(target_plot_manager_time_signal, 'connect')


        # 2. Simulate Drag and Drop to Target Subplot
        mime_data = create_custom_plot_item_mime_data(dragged_label.trace.name())
        drop_pos_target = QPoint(10, 10) # Position within target_subplot

        mocker.patch.object(target_subplot, '_get_drop_index', return_value=0) # Insert at the beginning

        # Drag Enter on Target
        drag_enter_event_target = create_mock_drag_enter_event(mime_data, drop_pos_target)
        target_subplot.dragEnterEvent(drag_enter_event_target)
        assert drag_enter_event_target.isAccepted(), "dragEnterEvent on target should be accepted"

        # Drag Move on Target
        drag_move_event_target = create_mock_drag_move_event(mime_data, drop_pos_target)
        target_subplot.dragMoveEvent(drag_move_event_target)
        assert drag_move_event_target.isAccepted(), "dragMoveEvent on target should be accepted"

        # Drop on Target
        drop_event_target = create_mock_drop_event(mime_data, drop_pos_target, source_widget=dragged_label, proposed_action=Qt.MoveAction)
        mocker.patch.object(drop_event_target, 'source', return_value=dragged_label)
        
        target_subplot.dropEvent(drop_event_target)
        assert drop_event_target.isAccepted(), "dropEvent on target should be accepted"

        # 3. Verification
        # Source Subplot
        assert len(source_subplot._traces) == 0, "Source subplot should have no traces"
        assert source_subplot._labels.count() == 0, "Source subplot should have no labels in layout"
        source_pg_items = [item for item in source_subplot.pw.getPlotItem().items if isinstance(item, pyqtgraph.PlotDataItem)]
        assert len(source_pg_items) == 0, "Source subplot PlotWidget should have no PlotDataItems"

        # Target Subplot
        assert len(target_subplot._traces) == 1, "Target subplot should have one trace"
        assert target_subplot._traces[0] == dragged_label, "Moved trace instance should be in target subplot's _traces"
        assert dragged_label._subplot_widget == target_subplot, "Moved trace's _subplot_widget should point to target"
        
        assert target_subplot._labels.count() == 1, "Target subplot should have one label in layout"
        assert target_subplot._labels.itemAt(0).widget() == dragged_label, "Moved label should be in target's layout"

        target_pg_items = [item for item in target_subplot.pw.getPlotItem().items if isinstance(item, pyqtgraph.PlotDataItem)]
        assert len(target_pg_items) == 1, "Target subplot PlotWidget should have one PlotDataItem"
        assert target_pg_items[0].name() == trace_name, "PlotDataItem in target should have correct name"
        assert target_pg_items[0] == dragged_label.trace, "PlotDataItem in target should be the one from the moved label"

        # Color verification (should be updated to first color in new subplot)
        expected_color_str = SubPlotWidget.COLORS[0]
        assert dragged_label.trace.opts['pen'].color().name() == expected_color_str, "Moved trace pen color incorrect in target"
        assert dragged_label.palette().color(QPalette.WindowText).name() == expected_color_str, "Moved trace label color incorrect in target"

        # Signal Connection Verification
        # Check that disconnect was called on the source's PlotManager.timeValueChanged signal
        # with the on_time_changed method of the dragged_label (CustomPlotItem).
        spy_source_disconnect.assert_called_once_with(dragged_label.on_time_changed)
        
        # Check that connect was called on the target's PlotManager.timeValueChanged signal
        # with the on_time_changed method of the dragged_label.
        spy_target_connect.assert_called_once_with(dragged_label.on_time_changed)

    finally:
        # Cleanup
        source_subplot.deleteLater()
        target_subplot.deleteLater()
        mock_parent_source.deleteLater()
        mock_parent_target.deleteLater()

def test_drag_custom_plot_item_to_plot_area_appends(subplot_widget_setup, mocker):
    '''Test dragging a CustomPlotItem to the plot graph area appends it to the end.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup: Add three traces
    common_time_data = np.array([0.0, 0.1, 0.2])
    traces_to_add = {
        "TraceX": np.array([1,2,3]),
        "TraceY": np.array([4,5,6]),
        "TraceZ": np.array([7,8,9])
    }
    added_items = _add_traces_to_subplot(subplot_widget, traces_to_add, common_time_data)
    _assert_trace_order_and_colors(subplot_widget, ["TraceX", "TraceY", "TraceZ"])

    dragged_label = added_items["TraceX"] # This is "TraceX" CustomPlotItem
    assert dragged_label._subplot_widget == subplot_widget

    # 2. Simulate Drag and Drop to Plot Area
    mime_data = create_custom_plot_item_mime_data(dragged_label.trace.name())
    
    # Ensure widget has processed initial layout to get valid geometries for pw and flow_layout_widget
    # This is important for the e.pos().y() >= self.flow_layout_widget.geometry().bottom() check in dropEvent.
    if subplot_widget.parentWidget():
        subplot_widget.parentWidget().resize(600, 400) # Give parent area some size
    subplot_widget.resize(600,300) # Give subplot some size so children get geometry
    QApplication.processEvents() # Allow Qt to process layout changes
        
    # Define drop position within the plot widget (pw) area.
    # This position must be below the flow_layout_widget to trigger append logic.
    # Using the center of the plot widget (pw) should generally satisfy this.
    drop_pos_plot_area = QPoint(subplot_widget.pw.width() // 2, 
                                subplot_widget.pw.geometry().top() + subplot_widget.pw.height() // 2)
    
    # Verification that the chosen drop point is indeed in the "plot area"
    # (i.e., below the label area / flow_layout_widget)
    if subplot_widget.flow_layout_widget.geometry().bottom() > drop_pos_plot_area.y():
        # This can happen if pw itself is very small or above flow_layout_widget due to unexpected layout in test.
        # Adjust drop_pos_plot_area to be definitively below.
        # This situation indicates a potential issue in how geometry is perceived in the test vs. real use.
        # For the test to proceed, force a y-coordinate that is certainly "in the plot area".
        print(f"Warning: Calculated drop_pos_y {drop_pos_plot_area.y()} was not below flow_layout_widget bottom "
              f"{subplot_widget.flow_layout_widget.geometry().bottom()}. Adjusting for test.")
        drop_pos_plot_area.setY(subplot_widget.flow_layout_widget.geometry().bottom() + 10)

    assert drop_pos_plot_area.y() >= subplot_widget.flow_layout_widget.geometry().bottom(), \
        f"Drop Y {drop_pos_plot_area.y()} must be >= flow_layout bottom {subplot_widget.flow_layout_widget.geometry().bottom()} for append logic."

    # Drag Enter
    drag_enter_event = create_mock_drag_enter_event(mime_data, drop_pos_plot_area)
    subplot_widget.dragEnterEvent(drag_enter_event)
    assert drag_enter_event.isAccepted(), "dragEnterEvent should be accepted when dragging over plot area"

    # Drag Move
    spy_hide_indicator = mocker.spy(subplot_widget, '_hide_drop_indicator')
    drag_move_event = create_mock_drag_move_event(mime_data, drop_pos_plot_area)
    subplot_widget.dragMoveEvent(drag_move_event)
    assert drag_move_event.isAccepted(), "dragMoveEvent should be accepted"
    spy_hide_indicator.assert_called_once() # Drop indicator should hide when over plot area

    # Drop Event
    drop_event = create_mock_drop_event(mime_data, drop_pos_plot_area, source_widget=dragged_label, proposed_action=Qt.MoveAction)
    mocker.patch.object(drop_event, 'source', return_value=dragged_label) # Critical mock
    
    subplot_widget.dropEvent(drop_event)
    assert drop_event.isAccepted(), "dropEvent should be accepted for append logic"

    # 3. Verification
    # Expected order: TraceX (dragged from index 0) should now be at the end.
    _assert_trace_order_and_colors(subplot_widget, ["TraceY", "TraceZ", "TraceX"])

def test_drag_unrecognized_mime_type_is_ignored(subplot_widget_setup, mocker):
    '''Test that SubPlotWidget ignores drag/drop with unrecognized mime types.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup: Add an initial trace
    initial_trace_name = "InitialTrace"
    time_data = np.array([0.0, 0.1])
    y_data = np.array([1, 2])
    mock_source = MockDataSource(time_data, {initial_trace_name: y_data}, var_name="InitialTrace_src")
    subplot_widget.plot_data_from_source(initial_trace_name, mock_source)

    assert len(subplot_widget._traces) == 1
    assert subplot_widget._traces[0].trace.name() == initial_trace_name

    # 2. Simulate Drag and Drop with Unrecognized Mime Type
    unrecognized_mime_data = create_unrecognized_mime_data()
    drop_pos = QPoint(10, 10)

    # Drag Enter Event
    drag_enter_event = create_mock_drag_enter_event(unrecognized_mime_data, drop_pos)
    subplot_widget.dragEnterEvent(drag_enter_event)
    assert not drag_enter_event.isAccepted(), "dragEnterEvent should not be accepted for unrecognized mime type"

    # Drop Event
    # For dropEvent, it might not call event.setAccepted(False) if it just ignores.
    # The key is that the state of the widget doesn't change.
    # However, good practice for a widget is to explicitly ignore an event it doesn't handle.
    # SubPlotWidget's dropEvent calls event.ignore() if mime type is not recognized.
    # QDropEvent.isAccepted() is true if accept() or acceptProposedAction() was called.
    # If ignore() is called, isAccepted() remains false (its default state).
    drop_event = create_mock_drop_event(unrecognized_mime_data, drop_pos)
    # We don't need to mock event.source() here as the mime type check happens first.
    subplot_widget.dropEvent(drop_event)
    assert not drop_event.isAccepted(), "dropEvent should not be accepted for unrecognized mime type"


    # 3. Verification: Ensure no changes to the subplot
    assert len(subplot_widget._traces) == 1, "Number of traces should remain 1."
    assert subplot_widget._labels.count() == 1, "Number of labels should remain 1."
    assert subplot_widget._traces[0].trace.name() == initial_trace_name, "The initial trace should still be present."

    # Check that no new pyqtgraph items were added
    pg_item_count = 0
    for item in subplot_widget.pw.getPlotItem().items:
        if isinstance(item, pyqtgraph.PlotDataItem):
            pg_item_count +=1
    assert pg_item_count == 1, "PlotWidget should still have only 1 PlotDataItem."

# Note: Removed 'if __name__ == "__main__": unittest.main()' as pytest handles test discovery and execution.
