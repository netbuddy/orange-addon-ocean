from os.path import join, dirname
from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import OWWidget, Input

from AnyQt.QtWidgets import QTreeWidget, \
    QWidget, QPushButton, QListView, QVBoxLayout
from AnyQt.QtGui import QIcon

from Orange.widgets.utils.itemmodels import VariableListModel
from orangecontrib.ocean.widgets.echarts import Echarts
from Orange.data import Table, Domain, DiscreteVariable, Variable, \
    ContinuousVariable

class OWLineChartEcharts(OWWidget):
    name = '折线图'
    description = "采用echarts绘制折线图."
    icon = 'icons/linechart.svg'
    priority = 90

    class Inputs:
        data = Input("Data", Table)

    attrs = settings.Setting({})  # Maps data.name -> [attrs]

    attr_x = ''
    attr_y = ''

    def __init__(self):
        self.data = None
        # A model for displaying python list like objects in Qt item view classes
        # 用于表示下拉框数据列表的模型
        self.varmodel = VariableListModel(parent=self)
        vbox = gui.vBox(self)
        # 从输入数据字段列表选取x轴的下拉框
        self.cb_attr_x = gui.comboBox(vbox, self, 'attr_x',
                     label='x轴:',
                     orientation='horizontal',
                     model=self.varmodel,
                     sendSelectedValue=True)
        # 从输入数据字段列表选取y轴的下拉框
        self.cb_attr_y = gui.comboBox(vbox, self, 'attr_y',
                     label='y轴:',
                     orientation='horizontal',
                     model=self.varmodel,
                     sendSelectedValue=True)
        # 按钮
        self.draw_button = QPushButton('绘制折线图', self)
        self.draw_button.clicked.connect(self.linechart_plot)
        # 在控制区域放置控制部件
        self.controlArea.layout().addWidget(vbox)
        self.controlArea.layout().addWidget(self.draw_button)
        # 创建Echarts部件
        self.chart = Echarts(self)
        # 在显示区域放置Echarts部件
        self.mainArea.layout().addWidget(self.chart)

    def linechart_plot(self):
        # Echarts的参数选项
        options = {
            'xAxis': {
                'data': self.data.get_column_view(self.attr_x)[0].tolist(),
            },
            'yAxis': {
                'scale': 'true'
            },
            'dataZoom': [
                {
                    'type': 'inside'
                },
            ],
            'series': [{
                'symbolSize': 10,
                'data': self.data.get_column_view(self.attr_y)[0].tolist(),
                'type': 'line'
            }]
        };
        # 绘制图形
        self.chart.chart(options=options)

    @Inputs.data
    def set_data(self, data):
        new_data = None if data is None else data
        if new_data is not None and self.data is not None \
                and new_data.domain == self.data.domain:
            self.data = new_data
            for config in self.configs:
                config.selection_changed()
            return

        self.data = data = None if data is None else data
        if data is None:
            self.varmodel.clear()
            self.chart.clear()
            return

        self.varmodel.wrap([var for var in data.domain.variables
                            if var.is_continuous])

if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication
    from orangecontrib.timeseries import ARIMA, VAR

    a = QApplication([])
    ow = OWLineChartEcharts()

    table = Table("iris")
    ow.set_data(table)

    ow.show()
    a.exec()
