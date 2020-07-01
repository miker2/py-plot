# This Python file uses the following encoding: utf-8
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import QSize, QVariant
from PyQt5.QtGui import QPalette

import pyqtgraph as pg

import pickle

from data import DataFileWidget
from data import DataItem

class PlotTool(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(640, 480))
        self.setWindowTitle("Drag/Drop example")
        self.setObjectName("PlotTool")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QHBoxLayout(main_widget)

        data_file_widget = DataFileWidget(self)
        layout.addWidget(data_file_widget)

        layout.addWidget(MyPlotWidget())

        # Set up two "files"
        data_file_widget.openFile("test_data1.csv")
        data_file_widget.openFile("test_data2.csv")
        data_file_widget.openFile("test_data3.csv")

        
class MyPlotWidget(QWidget):
    COLORS=('#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00', '#a65628', '#D4C200', '#f781bf')
    def __init__(self):
        QWidget.__init__(self)

        vBox = QVBoxLayout(self)

        self._labels = QHBoxLayout()
        #self._labels.setSpacing(0)
        self._labels.addStretch(1)
        vBox.addLayout(self._labels)

        self.pw = pg.PlotWidget()
        vBox.addWidget(self.pw)

        self.pw.setBackground('w')
        self.pw.showGrid(x=True, y=True)

        self.setAcceptDrops(True)
        self.pw.setAcceptDrops(True)

        #self.pw.getPlotItem().addLegend()

        self.cidx = 0

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-DataItem"):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        data = e.mimeData()
        bstream = data.retrieveData("application/x-DataItem", QVariant.ByteArray)
        selected = pickle.loads(bstream)

        name = f"{e.source().filename} : {selected.var_name}"
        
        print(type(selected.data))
        item = self.pw.getPlotItem().plot(x=selected.time.to_numpy(),
                                          y=selected.data.to_numpy(),
                                          pen=pg.mkPen(color=MyPlotWidget.COLORS[self.cidx],
                                                       width=2),
                                          name=name)
        label = self.makeLabel(item)
        self._labels.insertWidget(self._labels.count()-1, label)
        e.source().onClose.connect(lambda : self.removeItem(item, label))
        
        self.pw.autoRange()
        self.cidx = (self.cidx + 1) % len(MyPlotWidget.COLORS)
        e.accept()

    def makeLabel(self, plot_item):
        label = QLabel(plot_item.name())
        label.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))

        palette = QPalette()
        color = plot_item.opts['pen'].color()
        palette.setColor(QPalette.WindowText, color)
        label.setPalette(palette)

        return label

    def removeItem(self, item, label):
        self.pw.removeItem(item)
        self._labels.removeWidget(label)
        # self._labels.takeAt(self._labels.indexOf(label))
        label.deleteLater()
        

if __name__ == "__main__":
    MainEventThread = QApplication([])

    MainApplication = PlotTool()
    MainApplication.show()

    MainEventThread.exec()
