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
from PyQt5.QtCore import QMimeData, QByteArray, QPoint, Qt, QEvent # Added QEvent
from PyQt5.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QDrag, QMouseEvent # QDrag, QMouseEvent already here
from PyQt5.QtWidgets import QApplication, QWidget # QApplication is needed for QDrag.startDragDistance
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

class MockDraggableVarItem(QWidget):
    """
    A mock QWidget that simulates a draggable item from a variable list.
    It initiates a QDrag operation on mouse move.
    """
    def __init__(self, data_source_name: str, mock_data_model: MockDataSource, parent: QWidget = None):
        super().__init__(parent)
        self.data_source_name = data_source_name
        self._mock_data_model = mock_data_model
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = create_data_item_mime_data(self.data_source_name)
        drag.setMimeData(mime_data)

        # The exec_() call will block until the drag is completed.
        # For testing with qtbot, this is generally fine as qtbot manages the event loop.
        drag.exec_(Qt.MoveAction)
        event.accept()

    def model(self) -> MockDataSource:
        """Mimics the model() method of a VarListWidget item, returning the data source."""
        return self._mock_data_model

class MockDraggableUnrecognizedItem(QWidget):
    """
    A mock QWidget that simulates a draggable item with unrecognized mime data.
    """
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.drag_start_position = QPoint()
        self.setFixedSize(50, 30) # Give it a size for event handling

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        # event.accept() # Let event propagate

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = create_unrecognized_mime_data() # Use helper for unrecognized data
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction) # Actual action result doesn't matter much for this test
        # event.accept()

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
def create_unrecognized_mime_data() -> QMimeData:
    """
    Creates QMimeData with an unrecognized format for testing ignore behavior.
    MIME type: "application/x-unknown"
    """
    mime_data = QMimeData()
    mime_data.setData("application/x-unknown", QByteArray(b"unknown_data"))
    return mime_data

# Obsolete event creation helpers are removed as their functionality is now
# integrated into the mock_drag_exec_... side effect functions within each test.
# - create_mock_drag_enter_event
# - create_mock_drag_move_event
# - create_mock_drop_event
# The create_custom_plot_item_mime_data is also removed as CustomPlotItem
# now creates its own QMimeData internally.

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
def test_drag_data_item_to_subplot(subplot_widget_setup, qtbot, mocker): # Added qtbot
    '''Test dragging a DataItem (from a VarListWidget-like source) onto SubPlotWidget using qtbot.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup
    trace_name = "temperature_sensor"
    time_data = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    y_data = np.array([20.0, 20.5, 21.0, 20.8, 21.2])

    source_model = MockDataSource(time_data, {trace_name: y_data}, var_name=trace_name)
    draggable_item = MockDraggableVarItem(data_source_name=trace_name, mock_data_model=source_model)

    qtbot.addWidget(subplot_widget)
    qtbot.addWidget(draggable_item)

    # Ensure widgets are visible and have a size for event processing
    subplot_widget.show()
    subplot_widget.resize(300, 200)
    qtbot.waitExposed(subplot_widget)

    draggable_item.show()
    draggable_item.resize(50, 30)
    qtbot.waitExposed(draggable_item)

    # 2. Simulate Drag and Drop with qtbot
    # Start drag from the draggable_item
    qtbot.mousePress(draggable_item, Qt.LeftButton, pos=QPoint(5, 5))
    # Move mouse enough to trigger QDrag initiation in draggable_item.mouseMoveEvent
    # The actual QDrag.exec_() will be called here.
    # mouseMove on draggable_item is needed to start the drag.
    # The subsequent mouseMove to subplot_widget and mouseRelease on subplot_widget
    # will be processed by the Qt event loop during drag.exec_().

    # The QDrag object is created in draggable_item.mouseMoveEvent.
    # qtbot.mouseMove alone won't complete the drag if QDrag.exec_ is blocking.
    # However, pytest-qt's event loop processing should handle this.
    # The key is that QDrag.exec_ starts its own event loop.
    # We need to ensure that the drag object correctly delivers events to the target.

    # Point for drag initiation on draggable_item
    drag_start_point_local = QPoint(draggable_item.width()//2, draggable_item.height()//2)

    # Point for drop on subplot_widget (local coordinates)
    drop_point_on_subplot_local = QPoint(subplot_widget.width()//2, subplot_widget.height()//2)

    # Simulate the drag operation
    # mousePress on the source widget (draggable_item)
    qtbot.mousePress(draggable_item, Qt.LeftButton, pos=drag_start_point_local)

    # mouseMove on the source widget to initiate the QDrag
    # This move must be sufficient to exceed QApplication.startDragDistance()
    # The actual QDrag object is created and exec_() is called within draggable_item.mouseMoveEvent
    # QDrag.exec_() will take over the event loop.
    # We don't need to call qtbot.mouseMove to the target then qtbot.mouseRelease.
    # The drag.exec_() handles the interaction. We just need to ensure it's triggered.
    # For testing, the target of the drop is implicitly handled by Qt's DND system
    # once drag.exec_() starts. We need to ensure our subplot_widget is a valid drop target.

    # To ensure the drag is initiated and processed, we can use qtbot.dnd.
    # However, the subtask asks to use mousePress/Move/Release.
    # The tricky part is that drag.exec_() is blocking.
    # pytest-qt normally handles this by processing events.

    # Let's try a direct simulation sequence:
    # 1. Press on draggable_item
    # 2. Move on draggable_item (to start QDrag.exec_())
    # The QDrag.exec_() then takes over. Events during this loop are handled by Qt.
    # The dragEnter, dragMove, dropEvent on the SubPlotWidget should be triggered
    # by Qt's internal drag and drop handling if SubPlotWidget is a valid drop target
    # and accepts the proposed action.

    # The `QDrag.exec_()` will start a new event loop.
    # Events on `subplot_widget` will be processed by this loop.
    # We don't explicitly call `qtbot.mouseMove(subplot_widget, ...)` or
    # `qtbot.mouseRelease(subplot_widget, ...)` because these would occur *after*
    # `exec_()` returns, but the drop happens *during* `exec_()`.

    # We need to ensure that the drag operation (started by mouseMove on draggable_item)
    # actually targets the subplot_widget. This usually happens because the mouse cursor
    # physically moves over the subplot_widget during the drag.
    # In a test, this is tricky. `QDrag.exec_()` might not "see" the subplot_widget
    # correctly without actual mouse cursor movement or a way to direct the drag.

    # A common way to test QDrag is to mock `QDrag.exec_` or parts of it,
    # or use `qtbot.dnd` if available and suitable.
    # Given the constraint of using mousePress/Move/Release, we rely on the fact
    # that `draggable_item.mouseMoveEvent` calls `drag.exec_()`.
    # The `SubPlotWidget` should then receive the drop if its `dragEnterEvent` accepts.

    # We will mock QDrag.exec_ to simulate the drop on the target widget.
    # This is because qtbot.mouseMove/Release after initiating QDrag won't work as expected
    # due to QDrag.exec_()'s blocking nature and its own event loop.

    def mock_drag_exec(drag_instance, action): # drag_instance is the QDrag object
        # Simulate that the drag moved over subplot_widget and was dropped
        # This bypasses the need for actual mouse cursor simulation over widgets
        # We assume the drag would have reached the subplot_widget

        # Manually create and dispatch drag enter, move, and drop events to subplot_widget
        # This is what QDrag would do internally if mouse was moved over subplot_widget

        # 1. Simulate Drag Enter on subplot_widget
        # Map a point from draggable_item to global, then to subplot_widget
        # For simplicity, let's use a fixed point on subplot_widget
        enter_pos_subplot = QPoint(10,10) # Local to subplot_widget
        drag_enter_event = QDragEnterEvent(enter_pos_subplot, drag_instance.supportedActions(), drag_instance.mimeData(), event.buttons(), event.modifiers())
        QApplication.sendEvent(subplot_widget, drag_enter_event) # Dispatch event

        if drag_enter_event.isAccepted():
            # 2. Simulate Drag Move on subplot_widget (optional if enter is enough for accept)
            move_pos_subplot = QPoint(15,15)
            drag_move_event = QDragMoveEvent(move_pos_subplot, drag_instance.supportedActions(), drag_instance.mimeData(), event.buttons(), event.modifiers())
            QApplication.sendEvent(subplot_widget, drag_move_event)

            if drag_move_event.isAccepted():
                 # 3. Simulate Drop on subplot_widget
                drop_event_sim = QDropEvent(move_pos_subplot, drag_instance.possibleActions(), drag_instance.mimeData(), event.buttons(), event.modifiers())
                drop_event_sim.setDropAction(action) # Set the proposed action
                QApplication.sendEvent(subplot_widget, drop_event_sim)
                if drop_event_sim.isAccepted():
                    return action # Simulate successful drop action
        return Qt.IgnoreAction # Simulate drag was ignored or cancelled

    mocker.patch.object(QDrag, 'exec_', side_effect=mock_drag_exec)

    # This mouseMove should trigger draggable_item.mouseMoveEvent, which starts QDrag
    qtbot.mouseMove(draggable_item, QPoint(drag_start_point_local.x() + QApplication.startDragDistance() + 5, drag_start_point_local.y()))

    # No explicit mouseRelease needed on subplot_widget if QDrag.exec_ is handling it.
    # The mock_drag_exec simulates the drop.

    # 3. Verification (should be the same as before)
    assert len(subplot_widget._traces) == 1, "One trace should be added to _traces list."
    custom_plot_item = subplot_widget._traces[0]
    assert isinstance(custom_plot_item, CustomPlotItem), "_traces item should be a CustomPlotItem."

    assert custom_plot_item.text().startswith(trace_name), \
        f"Label text should start with trace name. Got: '{custom_plot_item.text()}'"

    assert subplot_widget._labels.count() == 1, "One label widget should be in FlowLayout."
    label_widget_in_layout = subplot_widget._labels.itemAt(0).widget()
    assert label_widget_in_layout == custom_plot_item, "Label in layout should be the same instance."

    pg_plot_item = None
    for item_in_graph in subplot_widget.pw.getPlotItem().items: # Renamed 'item' to 'item_in_graph'
        if isinstance(item_in_graph, pyqtgraph.PlotDataItem) and item_in_graph.name() == trace_name:
            pg_plot_item = item_in_graph
            break
    assert pg_plot_item is not None, f"PlotDataItem with name '{trace_name}' not found in pyqtgraph PlotItem."

    assert np.array_equal(pg_plot_item.yData, y_data), "Y-data in PlotDataItem does not match source."
    assert np.array_equal(pg_plot_item.xData, time_data), "X-data in PlotDataItem does not match source."

    expected_color_str = SubPlotWidget.COLORS[0]
    assert pg_plot_item.opts['pen'].color().name() == expected_color_str, "PlotDataItem pen color incorrect."
    label_palette_color = custom_plot_item.palette().color(QPalette.WindowText)
    assert label_palette_color.name() == expected_color_str, "Label text color incorrect."

def test_reorder_custom_plot_item_same_subplot(subplot_widget_setup, mocker):
    '''Test reordering a CustomPlotItem (trace) within the same SubPlotWidget.'''
def test_reorder_custom_plot_item_same_subplot(subplot_widget_setup, qtbot, mocker):
    '''Test reordering a CustomPlotItem (trace) within the same SubPlotWidget using qtbot.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup
    common_time_data = np.array([0.0, 0.1, 0.2])
    traces_to_add = {
        "TraceA": np.array([1,2,3]),
        "TraceB": np.array([4,5,6]),
        "TraceC": np.array([7,8,9])
    }
    added_items = _add_traces_to_subplot(subplot_widget, traces_to_add, common_time_data)
    _assert_trace_order_and_colors(subplot_widget, ["TraceA", "TraceB", "TraceC"]) # Initial state

    label_to_drag = added_items["TraceA"]
    assert label_to_drag._subplot_widget == subplot_widget

    qtbot.addWidget(subplot_widget)
    subplot_widget.show()
    qtbot.waitExposed(subplot_widget)
    # Ensure label_to_drag (CustomPlotItem) is also processed by layout if it affects geometry
    # CustomPlotItems are children of subplot_widget's flow_layout_widget
    QApplication.processEvents()


    # 2. Mocking Strategy
    # Mock _get_drop_index to control where the item is inserted.
    # Moving "TraceA" (index 0) to the end (index 2).
    mocker.patch.object(subplot_widget, '_get_drop_index', return_value=2)

    def mock_drag_exec_for_reorder(drag_instance, supported_actions, default_action=Qt.IgnoreAction):
        # Determine drop point within the label area (flow_layout_widget)
        # This point is relative to subplot_widget
        drop_y_in_labels = subplot_widget.flow_layout_widget.height() // 2 if subplot_widget.flow_layout_widget.height() > 0 else 10
        drop_point_on_subplot = QPoint(10, drop_y_in_labels)

        # Simulate DragEnter
        enter_event = QDragEnterEvent(
            drop_point_on_subplot, supported_actions, drag_instance.mimeData(),
            Qt.LeftButton, Qt.NoModifier
        )
        mocker.patch.object(enter_event, 'source', return_value=drag_instance.source(), create=True)
        QApplication.sendEvent(subplot_widget, enter_event)
        if not enter_event.isAccepted(): return Qt.IgnoreAction

        # Simulate DragMove
        move_event = QDragMoveEvent(
            drop_point_on_subplot, supported_actions, drag_instance.mimeData(),
            Qt.LeftButton, Qt.NoModifier
        )
        mocker.patch.object(move_event, 'source', return_value=drag_instance.source(), create=True)
        QApplication.sendEvent(subplot_widget, move_event)
        if not move_event.isAccepted(): return Qt.IgnoreAction

        # Simulate DropEvent
        drop_event = QDropEvent(
            drop_point_on_subplot, supported_actions, drag_instance.mimeData(),
            Qt.LeftButton, Qt.NoModifier, QEvent.Drop
        )
        mocker.patch.object(drop_event, 'source', return_value=drag_instance.source(), create=True)
        drop_event.setDropAction(Qt.MoveAction)
        QApplication.sendEvent(subplot_widget, drop_event)

        return Qt.MoveAction if drop_event.isAccepted() else Qt.IgnoreAction

    mocker.patch('PyQt5.QtGui.QDrag.exec_', side_effect=mock_drag_exec_for_reorder)

    # 3. Simulate Drag with qtbot
    # Ensure label_to_drag has a valid size for press/move operations
    if label_to_drag.size().isEmpty(): # CustomPlotItem might not have a size if layout not fully processed
        label_to_drag.adjustSize() # Give it a size based on its content
        QApplication.processEvents() # Allow size adjustment to take effect

    press_pos = QPoint(label_to_drag.width() // 4, label_to_drag.height() // 4)
    # Ensure move is sufficient to trigger drag
    move_offset = QPoint(QApplication.startDragDistance() + 5, 0)
    move_pos = press_pos + move_offset

    qtbot.mousePress(label_to_drag, Qt.LeftButton, pos=press_pos)
    qtbot.mouseMove(label_to_drag, pos=move_pos)
    # mouseMove on label_to_drag triggers its mouseMoveEvent, which calls the mocked QDrag.exec_

    # 4. Verification
    _assert_trace_order_and_colors(subplot_widget, ["TraceB", "TraceC", "TraceA"])

def test_move_custom_plot_item_between_subplots(qtbot, mocker): # Removed qapp, using qtbot now
    '''Test moving a CustomPlotItem from one SubPlotWidget to another using qtbot.'''
    source_mock_area = MockPlotAreaWidget()
    target_mock_area = MockPlotAreaWidget()
    source_subplot = SubPlotWidget(parent=source_mock_area, object_name_override="subplot_source")
    target_subplot = SubPlotWidget(parent=target_mock_area, object_name_override="subplot_target")

    qtbot.addWidget(source_mock_area) # Add parent areas for proper cleanup by qtbot if not explicitly deleted
    qtbot.addWidget(target_mock_area)
    # Subplots are children of mock_areas, so adding them explicitly to qtbot might be redundant
    # if mock_areas are properly managed, but it's harmless.
    qtbot.addWidget(source_subplot)
    qtbot.addWidget(target_subplot)

    try:
        # 1. Setup
        source_subplot.show()
        qtbot.waitExposed(source_subplot)
        target_subplot.show()
        qtbot.waitExposed(target_subplot)
        QApplication.processEvents() # Ensure layouts are processed

        trace_name = "MovableTrace"
        time_data = np.array([0.0, 0.1, 0.2])
        y_data = np.array([10, 20, 30])

        # Use _add_traces_to_subplot for consistency, even for one trace
        added_to_source = _add_traces_to_subplot(source_subplot, {trace_name: (time_data, y_data)})
        label_to_drag = added_to_source[trace_name]

        # Initial verification
        assert len(source_subplot._traces) == 1
        assert source_subplot._traces[0].trace.name() == trace_name
        assert len(target_subplot._traces) == 0
        assert label_to_drag._subplot_widget == source_subplot

        # 2. Mocking and Spies
        mocker.patch.object(target_subplot, '_get_drop_index', return_value=0)

        spy_disconnect = mocker.spy(source_subplot.parent().plot_manager().timeValueChanged, 'disconnect')
        spy_connect = mocker.spy(target_subplot.parent().plot_manager().timeValueChanged, 'connect')

        def mock_drag_exec_for_move(drag_instance, supported_actions, default_action=None): # defaultAction can be Qt.IgnoreAction
            QApplication.processEvents() # Ensure target_subplot geometry is up-to-date

            # Drop point in target_subplot's label area (flow_layout_widget)
            drop_y_in_labels_target = target_subplot.flow_layout_widget.height() // 2 if target_subplot.flow_layout_widget.height() > 0 else 10
            drop_point_on_target = QPoint(10, drop_y_in_labels_target)

            # Simulate DragEnter on target_subplot
            enter_event = QDragEnterEvent(drop_point_on_target, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier)
            mocker.patch.object(enter_event, 'source', return_value=drag_instance.source(), create=True)
            QApplication.sendEvent(target_subplot, enter_event)
            if not enter_event.isAccepted(): return Qt.IgnoreAction

            # Simulate DragMove on target_subplot
            move_event = QDragMoveEvent(drop_point_on_target, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier)
            mocker.patch.object(move_event, 'source', return_value=drag_instance.source(), create=True)
            QApplication.sendEvent(target_subplot, move_event)
            if not move_event.isAccepted(): return Qt.IgnoreAction

            # Simulate DropEvent on target_subplot
            drop_event = QDropEvent(drop_point_on_target, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier, QEvent.Drop)
            mocker.patch.object(drop_event, 'source', return_value=drag_instance.source(), create=True)
            drop_event.setDropAction(Qt.MoveAction) # Assume MoveAction for this test
            QApplication.sendEvent(target_subplot, drop_event)

            return Qt.MoveAction if drop_event.isAccepted() else Qt.IgnoreAction

        mocker.patch('PyQt5.QtGui.QDrag.exec_', side_effect=mock_drag_exec_for_move)

        # 3. Simulate Drag with qtbot
        if label_to_drag.size().isEmpty():
            label_to_drag.adjustSize()
            QApplication.processEvents()

        press_pos = QPoint(label_to_drag.width() // 4, label_to_drag.height() // 4)
        move_offset = QPoint(QApplication.startDragDistance() + 5, 0)
        move_pos = press_pos + move_offset

        qtbot.mousePress(label_to_drag, Qt.LeftButton, pos=press_pos)
        qtbot.mouseMove(label_to_drag, pos=move_pos)

        # 4. Verification
        # Source Subplot
        assert len(source_subplot._traces) == 0, "Source subplot should have no traces after move"
        assert source_subplot._labels.count() == 0, "Source subplot should have no labels after move"

        # Target Subplot
        assert len(target_subplot._traces) == 1, "Target subplot should have one trace after move"
        assert target_subplot._traces[0] == label_to_drag, "Moved trace instance should be in target's _traces"
        assert label_to_drag._subplot_widget == target_subplot, "Moved trace's _subplot_widget should point to target"

        assert target_subplot._labels.count() == 1, "Target subplot should have one label in layout"
        assert target_subplot._labels.itemAt(0).widget() == label_to_drag, "Moved label should be in target's layout"

        # Verify color using the helper (expects a list of names)
        _assert_trace_order_and_colors(target_subplot, [trace_name]) # Checks color for COLORS[0]

        # Signal Connection Verification
        spy_disconnect.assert_called_once_with(label_to_drag.on_time_changed)
        spy_connect.assert_called_once_with(label_to_drag.on_time_changed)

    finally:
        # 5. Cleanup
        # Rely on qtbot to manage widgets added via qtbot.addWidget()
        # Explicitly delete if not relying solely on qtbot or if issues arise with teardown.
        # For safety, especially with manually created parent widgets that might not be added to qtbot:
        source_subplot.deleteLater()
        target_subplot.deleteLater()
        source_mock_area.deleteLater()
        target_mock_area.deleteLater()

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

def test_drag_custom_plot_item_to_plot_area_appends(subplot_widget_setup, qtbot, mocker):
    '''Test dragging a CustomPlotItem to the plot graph area appends it to the end, using qtbot.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup
    common_time_data = np.array([0.0, 0.1, 0.2])
    traces_to_add = {
        "TraceX": np.array([1,2,3]),
        "TraceY": np.array([4,5,6]),
        "TraceZ": np.array([7,8,9])
    }
    added_items = _add_traces_to_subplot(subplot_widget, traces_to_add, common_time_data)
    _assert_trace_order_and_colors(subplot_widget, ["TraceX", "TraceY", "TraceZ"]) # Initial state

    label_to_drag = added_items["TraceX"]

    qtbot.addWidget(subplot_widget)
    subplot_widget.show()
    qtbot.waitExposed(subplot_widget)
    QApplication.processEvents() # Ensure layout is processed

    # 2. Mocking Strategy (Do NOT mock _get_drop_index)
    def mock_drag_exec_for_append(drag_instance, supported_actions, default_action=None):
        QApplication.processEvents() # Ensure subplot_widget's geometry is updated.

        # Drop position must be in the plot area (pw), relative to subplot_widget
        plot_area_center_in_pw = subplot_widget.pw.rect().center()
        drop_point_in_plot_area = subplot_widget.pw.mapToParent(plot_area_center_in_pw)

        # Ensure this point is actually below the flow_layout_widget to trigger append logic
        if drop_point_in_plot_area.y() < subplot_widget.flow_layout_widget.geometry().bottom():
            # print(f"Warning: Calculated drop point Y {drop_point_in_plot_area.y()} was not below "
            #       f"flow_layout bottom {subplot_widget.flow_layout_widget.geometry().bottom()}. Adjusting.")
            drop_point_in_plot_area.setY(subplot_widget.flow_layout_widget.geometry().bottom() + 10)


        # Simulate DragEnter
        enter_event = QDragEnterEvent(drop_point_in_plot_area, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier)
        mocker.patch.object(enter_event, 'source', return_value=drag_instance.source(), create=True)
        QApplication.sendEvent(subplot_widget, enter_event)
        if not enter_event.isAccepted(): return Qt.IgnoreAction

        # Simulate DragMove
        # Spy on _hide_drop_indicator to check if it's called when dragging over plot area
        spy_hide_indicator = mocker.spy(subplot_widget, '_hide_drop_indicator')
        move_event = QDragMoveEvent(drop_point_in_plot_area, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier)
        mocker.patch.object(move_event, 'source', return_value=drag_instance.source(), create=True)
        QApplication.sendEvent(subplot_widget, move_event)
        spy_hide_indicator.assert_called_once() # Check indicator is hidden
        if not move_event.isAccepted(): return Qt.IgnoreAction

        # Simulate DropEvent
        drop_event = QDropEvent(drop_point_in_plot_area, supported_actions, drag_instance.mimeData(), Qt.LeftButton, Qt.NoModifier, QEvent.Drop)
        mocker.patch.object(drop_event, 'source', return_value=drag_instance.source(), create=True)
        drop_event.setDropAction(Qt.MoveAction)
        QApplication.sendEvent(subplot_widget, drop_event)

        return Qt.MoveAction if drop_event.isAccepted() else Qt.IgnoreAction

    mocker.patch('PyQt5.QtGui.QDrag.exec_', side_effect=mock_drag_exec_for_append)

    # 3. Simulate Drag with qtbot
    if label_to_drag.size().isEmpty():
        label_to_drag.adjustSize()
        QApplication.processEvents()

    press_pos = QPoint(label_to_drag.width() // 2, label_to_drag.height() // 2) # Center for press
    # Ensure move is sufficient to trigger drag; using a slightly larger offset
    move_offset = QPoint(QApplication.startDragDistance() + 10, QApplication.startDragDistance() + 10)
    move_pos = press_pos + move_offset

    qtbot.mousePress(label_to_drag, Qt.LeftButton, pos=press_pos)
    qtbot.mouseMove(label_to_drag, pos=move_pos)

    # 4. Verification
    _assert_trace_order_and_colors(subplot_widget, ["TraceY", "TraceZ", "TraceX"])


def test_drag_unrecognized_mime_type_is_ignored(subplot_widget_setup, qtbot, mocker):
    '''Test that SubPlotWidget ignores drag/drop with unrecognized mime types using qtbot.'''
    subplot_widget = subplot_widget_setup

    # 1. Setup
    initial_trace_name = "InitialTrace"
    # Use _add_traces_to_subplot for consistency, even for one trace
    _add_traces_to_subplot(subplot_widget, {initial_trace_name: np.array([1,2])}, common_time_data=np.array([0.0, 0.1]))

    unrecognized_item = MockDraggableUnrecognizedItem()

    qtbot.addWidget(subplot_widget)
    qtbot.addWidget(unrecognized_item)
    subplot_widget.show()
    unrecognized_item.show()
    qtbot.waitExposed(subplot_widget)
    qtbot.waitExposed(unrecognized_item)
    QApplication.processEvents()

    # 2. Mocking Strategy for QDrag.exec_
    # This flag will be set if the mock function is actually called.
    mock_drag_exec_called = False

    def mock_drag_exec_for_unrecognized(drag_instance, supported_actions, default_action=None):
        nonlocal mock_drag_exec_called
        mock_drag_exec_called = True

        QApplication.processEvents()
        target_point = subplot_widget.rect().center()

        # Simulate DragEnter
        enter_event = QDragEnterEvent(
            target_point, supported_actions, drag_instance.mimeData(),
            Qt.LeftButton, Qt.NoModifier
        )
        mocker.patch.object(enter_event, 'source', return_value=drag_instance.source(), create=True)
        QApplication.sendEvent(subplot_widget, enter_event)
        assert not enter_event.isAccepted(), "dragEnterEvent should have ignored unrecognized mime type"

        # Simulate DropEvent
        drop_event = QDropEvent(
            target_point, supported_actions, drag_instance.mimeData(),
            Qt.LeftButton, Qt.NoModifier, QEvent.Drop
        )
        mocker.patch.object(drop_event, 'source', return_value=drag_instance.source(), create=True)
        drop_event.setDropAction(Qt.MoveAction)
        QApplication.sendEvent(subplot_widget, drop_event)
        assert not drop_event.isAccepted(), "dropEvent should have ignored unrecognized mime type"

        return Qt.IgnoreAction

    mocker.patch('PyQt5.QtGui.QDrag.exec_', side_effect=mock_drag_exec_for_unrecognized)

    # 3. Simulate Drag with qtbot
    press_pos = QPoint(unrecognized_item.width() // 4, unrecognized_item.height() // 4)
    move_pos = QPoint(press_pos.x() + QApplication.startDragDistance() + 5, press_pos.y())

    qtbot.mousePress(unrecognized_item, Qt.LeftButton, pos=press_pos)
    qtbot.mouseMove(unrecognized_item, pos=move_pos)

    assert mock_drag_exec_called, "Mocked QDrag.exec_ was not called, drag initiation failed."

    # 4. Verification (in main test body)
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
