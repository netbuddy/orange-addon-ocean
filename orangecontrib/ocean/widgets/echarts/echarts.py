from json import dumps as json
from collections import defaultdict
from collections.abc import MutableMapping
from os.path import join, dirname

import numpy as np

from AnyQt.QtCore import QObject, pyqtSlot
from AnyQt.QtWidgets import QApplication
from Orange.widgets.utils.webview import WebviewWidget

def _Autotree():
    return defaultdict(_Autotree)


def _merge_dicts(master, update):
    """Merge dicts recursively in place (``master`` is modified)"""
    for k, v in master.items():
        if k in update:
            if isinstance(v, MutableMapping) and isinstance(update[k], MutableMapping):
                update[k] = _merge_dicts(v, update[k])
    master.update(update)
    return master


def _kwargs_options(kwargs):
    """Transforma a dict into a hierarchical dict.

    Example
    -------
    >>> (_kwargs_options(dict(a_b_c=1, a_d_e=2, x=3)) ==
    ...  dict(a=dict(b=dict(c=1), d=dict(e=2)), x=3))
    True
    """
    kwoptions = _Autotree()
    for kws, val in kwargs.items():
        cur = kwoptions
        kws = kws.split('_')
        for kw in kws[:-1]:
            cur = cur[kw]
        cur[kws[-1]] = val
    return kwoptions

class Echarts(WebviewWidget):
    """Create a Echarts webview widget.

    Parameters
    ----------
    parent: QObject
        Qt parent object, if any.
    bridge: QObject
        Exposed as ``window.pybridge`` in JavaScript.
    options: dict
        Default options for this chart. If any option's value is a string
        that starts with an empty block comment ('/**/'), the expression
        following is evaluated in JS.
    javascript: str
        Additional JavaScript code to evaluate beforehand. If you
        need something exposed in the global namespace,
        assign it as an attribute to the ``window`` object.
    debug: bool
        Enables right-click context menu and inspector tools.
    **kwargs:
        The additional options. The underscores in argument names imply
        hierarchy, e.g., keyword argument such as ``chart_type='area'``
        results in the following object, in JavaScript::

            {
                chart: {
                    type: 'area'
                }
            }

        The original `options` argument is updated with options from
        these kwargs-derived objects.
    """

    _ECHARTS_HTML = join(dirname(__file__), '_echarts', 'chart.html')

    def __init__(self,
                 parent=None,
                 bridge=None,
                 # options=None,
                 javascript='',
                 debug=False,
                 **kwargs):
        super().__init__(parent, bridge, debug=debug)
        # options = (options or {}).copy()
        # 载入网页模板，创建echarts对象
        with open(self._ECHARTS_HTML) as html:
            self.setHtml(html.read() % dict(javascript=javascript),
                         self.toFileURL(dirname(self._ECHARTS_HTML)) + '/')

    def _update_options_dict(self, options, enable_zoom, enable_select,
                             enable_point_select, enable_rect_select,
                             enable_scrollbar, kwargs):
        if enable_zoom:
            _merge_dicts(options, _kwargs_options(dict(
                mapNavigation_enableMouseWheelZoom=True,
                mapNavigation_enableButtons=False)))
        if enable_select:
            _merge_dicts(options, _kwargs_options(dict(
                chart_events_click='/**/unselectAllPoints/**/')))
        if enable_point_select:
            _merge_dicts(options, _kwargs_options(dict(
                plotOptions_series_allowPointSelect=True,
                plotOptions_series_point_events_click='/**/clickedPointSelect/**/')))
        if enable_rect_select:
            _merge_dicts(options, _kwargs_options(dict(
                chart_zoomType=enable_rect_select,
                chart_events_selection='/**/rectSelectPoints/**/')))
        if kwargs:
            _merge_dicts(options, _kwargs_options(kwargs))

        if not enable_scrollbar:
            _merge_dicts(options, {'scrollbar':
                                       {'enabled': enable_scrollbar}})

    def exposeObject(self, name, obj):
        if isinstance(obj, np.ndarray):
            # chokes on NaN values. Instead it prefers 'null' for
            # points it is not intended to show.
            obj = obj.astype(object)
            obj[np.isnan(obj)] = None
        super().exposeObject(name, obj)

    def chart(self, data=None, options=None, **kwargs):
        """ 载入数据绘制图形.
        """
        options = (options or {}).copy()
        if not isinstance(options, MutableMapping):
            raise ValueError('options must be dict')
        if kwargs:
            _merge_dicts(options, _kwargs_options(kwargs))
        # 将传入的python对象装为js对象并载入网页的上下文
        self.exposeObject('pydata', data)
        self.exposeObject('pyoption', options)
        # 执行js语句绘制图形
        self.evalJS('''
            var data = pydata;
            var option = pyoption;
            myChart.setOption(option);
        ''')

def main():
    """ A simple test. """
    app = QApplication([])

    def _on_selected_points(points):
        print(len(points), points)

    xAxis = {
        'type': 'category',
        'data': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    }
    yAxis = {
        'type': 'value'
    }
    series = [{
        'data': [820, 932, 901, 934, 1290, 1330, 1320],
        'type': 'line'
    }]
    options = {
        'xAxis': xAxis,
        'yAxis': yAxis,
        'series': series
    }
    w = Echarts(debug=True)
    w.chart(options=options)
    w.show()
    app.exec()


if __name__ == '__main__':
    main()
