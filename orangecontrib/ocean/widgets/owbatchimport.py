import os
import warnings
from numbers import Number
from collections import OrderedDict
from os.path import join, dirname
import sys

import numpy as np
import pandas as pd

from Orange.data import TimeVariable, Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Input, Output

from AnyQt.QtWidgets import QTreeWidget, \
    QWidget, QPushButton, QListView, QVBoxLayout
from AnyQt.QtGui import QIcon, QPalette
from AnyQt.QtCore import QSize, pyqtSignal, QTimer, Slot

from AnyQt.QtWidgets import QApplication, QStyle, QFileDialog, QLabel, QGridLayout, QTextBrowser
from PyQt5.QtCore import (
    Qt, QFileInfo, QTimer, QSettings, QObject, QSize, QMimeDatabase, QMimeType
)
import Orange.data

class OWBatchImport(widget.OWWidget):
    name = '批量导入'
    description = "数据批量导入"
    icon = 'icons/batchimport.svg'
    priority = 90

    # 定义输出信号
    class Outputs:
        data = Output("Data", Orange.data.Table, doc="Table", default=True)  #输出Orange Table格式的数据
        dataFrame = Output("Data Frame", pd.DataFrame, doc="DataFrame")          #输出Pandas DataFrame格式的数据

    # 不绘制内容区域
    want_main_area = False

    def __init__(self):
        grid = QGridLayout()
        self.dir_label = QLabel("目录:", self)
        self.browse_button = QPushButton(
            "…", icon=self.style().standardIcon(QStyle.SP_DirOpenIcon),
            toolTip="Browse filesystem", autoDefault=False,
        )
        self.browse_button.clicked.connect(self.browse)
        grid.addWidget(self.dir_label, 0, 1, 1, 1)
        grid.addWidget(self.browse_button, 0, 2, 1, 1)
        self.controlArea.layout().addLayout(grid)

        box = gui.widgetBox(self.controlArea, "Info", addSpace=False)
        self.summary_text = QTextBrowser(
            verticalScrollBarPolicy=Qt.ScrollBarAsNeeded,
            readOnly=True,
        )
        self.summary_text.viewport().setBackgroundRole(QPalette.NoRole)
        self.summary_text.setFrameStyle(QTextBrowser.NoFrame)
        self.summary_text.setMinimumHeight(self.fontMetrics().ascent() * 2 + 4)
        self.summary_text.viewport().setAutoFillBackground(False)
        box.layout().addWidget(self.summary_text)

    @Slot()
    def browse(self, prefixname=None, directory=None):
        """
        Open a file dialog and select a user specified file.
        """
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录", "~/map")
        self.dir_label.setText(dir_path)

        # 将指定目录中的csv文件集合导入并转为pandas的dataframe对象
        df = self._get_data(dir_path)
        self.summary_text.setText("共载入{}条记录。".format(df.shape[0]))

        # 向数据通道发送数据
        self.Outputs.dataFrame.send(df)
        self.Outputs.data.send(pandas_to_table(df))

    def _get_data(self, dir_path):
        filecsv_list = []
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if os.path.splitext(file)[1] == '.csv':
                    filecsv_list.append(os.path.join(root, file))
        data = pd.DataFrame()
        for csv in filecsv_list:
            df_tmp = pd.read_csv(csv, header=0, encoding='utf-8')
            data = data.append(df_tmp, ignore_index=True)

        return data

from pandas.api import types as pdtypes
import Orange
def pandas_to_table(df):
    # type: (pd.DataFrame) -> Orange.data.Table
    """
    Convert a pandas.DataFrame to a Orange.data.Table instance.
    """
    index = df.index
    if not isinstance(index, pd.RangeIndex):
        df = df.reset_index()

    columns = []  # type: List[Tuple[Orange.data.Variable, np.ndarray]]

    for header, series in df.items():  # type: (Any, pd.Series)
        if pdtypes.is_categorical_dtype(series):
            coldata = series.values  # type: pd.Categorical
            categories = [str(c) for c in coldata.categories]
            var = Orange.data.DiscreteVariable.make(
                str(header), values=categories
            )
            # Remap the coldata into the var.values order/set
            coldata = pd.Categorical(
                coldata.astype("str"), categories=var.values
            )
            codes = coldata.codes
            assert np.issubdtype(codes.dtype, np.integer)
            orangecol = np.array(codes, dtype=np.float)
            orangecol[codes < 0] = np.nan
        elif pdtypes.is_datetime64_any_dtype(series):
            # Check that this converts tz local to UTC
            series = series.astype(np.dtype("M8[ns]"))
            coldata = series.values  # type: np.ndarray
            assert coldata.dtype == "M8[ns]"
            mask = np.isnat(coldata)
            orangecol = coldata.astype(np.int64) / 10 ** 9
            orangecol[mask] = np.nan
            var = Orange.data.TimeVariable.make(str(header))
            var.have_date = var.have_time = 1
        elif pdtypes.is_object_dtype(series):
            coldata = series.fillna('').values
            assert isinstance(coldata, np.ndarray)
            orangecol = coldata
            var = Orange.data.StringVariable.make(str(header))
        elif pdtypes.is_integer_dtype(series):
            coldata = series.values
            var = Orange.data.ContinuousVariable.make(str(header))
            var.number_of_decimals = 0
            orangecol = coldata.astype(np.float64)
        elif pdtypes.is_numeric_dtype(series):
            orangecol = series.values.astype(np.float64)
            var = Orange.data.ContinuousVariable.make(str(header))
        else:
            warnings.warn(
                "Column '{}' with dtype: {} skipped."
                    .format(header, series.dtype),
                UserWarning
            )
            continue
        columns.append((var, orangecol))

    cols_x = [(var, col) for var, col in columns if var.is_primitive()]
    cols_m = [(var, col) for var, col in columns if not var.is_primitive()]

    variables = [v for v, _ in cols_x]
    if cols_x:
        X = np.column_stack([a for _, a in cols_x])
    else:
        X = np.empty((df.shape[0], 0), dtype=np.float)
    metas = [v for v, _ in cols_m]
    if cols_m:
        M = np.column_stack([a for _, a in cols_m])
    else:
        M = None

    domain = Orange.data.Domain(variables, metas=metas)
    return Orange.data.Table.from_numpy(domain, X, None, M)

def main(argv=None):  # pragma: no cover
    app = QApplication(argv or [])
    w = OWBatchImport()
    w.show()
    w.raise_()
    app.exec_()
    w.saveSettings()
    w.onDeleteWidget()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
