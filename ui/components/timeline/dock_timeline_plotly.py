import os
import hashlib
import sqlite3
from datetime import datetime, timedelta
import logging
import numpy as np  # For fast histogram and sampling/filtering

from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox,
    QSizePolicy, QLabel, QDateTimeEdit, QPushButton, QInputDialog, QFileDialog, QDialog
)
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QUrl, pyqtSlot, QDateTime
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

import plotly.graph_objects as go
import plotly.io as pio
from dateutil import parser as date_parser


class JSBridge(QObject):
    """
    A simple QObject to bridge JavaScript events back to Python.
    Emits a signal with the clicked datetime string.
    """
    timeClicked = pyqtSignal(str)

    @pyqtSlot(str)
    def onPlotlyClick(self, x_value_str):
        self.timeClicked.emit(x_value_str)


class TimelineDock(QDockWidget):
    """
    A dock that displays a Plotly-based timeline of log events.
    It unifies timestamps (or events) from multiple log sources and shows each source as its own trace.
    This version computes different shades for similar source types (e.g. IIS, EVTX, GenericLog)
    and passes along additional row information to be displayed on hover.
    
    A single toggle button is used to switch between the Histogram view and a 3D scatter view.
    When the user switches to the 3D scatter view, a dialog is displayed that lets the user
    enter a threshold for time_taken. Only events with time_taken >= threshold are displayed.
    Clicking the button again returns to the Histogram view.
    """
    jumpToTimeSignal = pyqtSignal(object)  # Emitted when user clicks the timeline (datetime object)

    def __init__(self, parent=None):
        # Colors for sources
        self.source_colors = {
            'IIS': 'green',
            'evtx': 'red',
            # Additional mappings can be added here.
        }
        super().__init__("Timeline (Plotly)", parent)
        self.setObjectName("TimelineDock")
        self.logger = logging.getLogger('TimelineDock')
        self.logger.setLevel(logging.DEBUG)
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        # Dictionaries to hold events.
        self.timestamp_dict = {}  # current events (possibly filtered)
        self.original_timestamp_dict = {}  # backup of original events

        # Default scatter threshold (e.g., only show events with time_taken >= threshold)
        self.scatter_threshold = 0

        # Flag: currently showing histogram (True) or 3D scatter (False)
        self.showing_histogram = True

        # Main container and layout.
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Control Panel ---
        self.control_panel = QWidget()
        cp_layout = QHBoxLayout(self.control_panel)
        cp_layout.setContentsMargins(5, 5, 5, 5)
        cp_layout.setSpacing(10)

        # (Source selection and time span controls remain as before.)
        cp_layout.addWidget(QLabel("Source:"))
        self.source_combo = QDockWidget()  # placeholder, not used for toggle in this example
        self.source_combo = QComboBox()
        cp_layout.addWidget(self.source_combo)

        cp_layout.addWidget(QLabel("Start:"))
        self.source_start_edit = QDateTimeEdit()
        self.source_start_edit.setCalendarPopup(True)
        self.source_start_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        cp_layout.addWidget(self.source_start_edit)

        cp_layout.addWidget(QLabel("End:"))
        self.source_end_edit = QDateTimeEdit()
        self.source_end_edit.setCalendarPopup(True)
        self.source_end_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        cp_layout.addWidget(self.source_end_edit)

        self.set_span_btn = QPushButton("Set Source Span")
        self.set_span_btn.clicked.connect(self.setSourceSpan)
        cp_layout.addWidget(self.set_span_btn)

        self.reset_span_btn = QPushButton("Reset Source Span")
        self.reset_span_btn.clicked.connect(self.resetSourceSpan)
        cp_layout.addWidget(self.reset_span_btn)

        self.remove_source_btn = QPushButton("Remove Source")
        self.remove_source_btn.clicked.connect(self.removeSourceTimestamps)
        cp_layout.addWidget(self.remove_source_btn)

        # NEW: Toggle button for switching views.
        self.toggle_view_btn = QPushButton("Show 3D Scatter")
        self.toggle_view_btn.clicked.connect(self.toggleView)
        cp_layout.addWidget(self.toggle_view_btn)

        cp_layout.addStretch()
        main_layout.addWidget(self.control_panel)

        # --- WebEngineView for Plotly graph ---
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.web_view)
        profile = self.web_view.page().profile()
        profile.downloadRequested.connect(self.onDownloadRequested)
        self.setWidget(container)

        # Setup QWebChannel for JS-to-Python communication.
        self.channel = QWebChannel()
        self.js_bridge = JSBridge()
        self.channel.registerObject("bridge", self.js_bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.js_bridge.timeClicked.connect(self.emitJumpToTimeSignal)
        self.source_combo.currentIndexChanged.connect(self.onSourceChanged)

    def onDownloadRequested(self, download_item):
        """
        Called whenever a file download is triggered in QWebEngineView.
        For Plotly's "Download plot as png", we prompt the user for a save path
        and then accept the download with that path.
        """
        # By default, Plotly tries to "download" a data URL.
        # We override it with our own "Save As" file dialog:
        suggested_file = download_item.suggestedFileName() or "plot.png"

        file_dialog = QFileDialog(self, "Save Plot", "", "PNG Files (*.png);;All Files (*)")
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.selectFile(suggested_file)

        if file_dialog.exec_() == QDialog.Accepted:
            file_path = file_dialog.selectedFiles()[0]
            if file_path:
                download_item.setPath(file_path)
                download_item.accept()
                self.logger.info(f"Plot will be saved to: {file_path}")
            else:
                self.logger.info("Save canceled: no file path selected.")
        else:
            self.logger.info("Save canceled: user closed dialog without selecting a file.")
            
    def onSourceChanged(self, index):
        """
        When the selected source changes, update the Start/End edits with the min/max
        timestamps for that source.
        """
        source = self.source_combo.itemText(index) # type: ignore
        if source in self.timestamp_dict and self.timestamp_dict[source]:
            ts_list = []
            for ev in self.timestamp_dict[source]:
                if isinstance(ev, (tuple, list)):
                    ts_list.append(ev[0])
                elif isinstance(ev, dict):
                    ts_list.append(ev.get("timestamp"))
                else:
                    ts_list.append(ev)
            start_qdt = QDateTime.fromSecsSinceEpoch(int(min(ts_list)))
            end_qdt = QDateTime.fromSecsSinceEpoch(int(max(ts_list)))
            self.source_start_edit.setDateTime(start_qdt)
            self.source_end_edit.setDateTime(end_qdt)

    def refreshSourceCombo(self):
        current_source = self.source_combo.currentText()
        self.source_combo.clear()
        for src in self.timestamp_dict.keys():
            self.source_combo.addItem(src)
        index = self.source_combo.findText(current_source)
        if index >= 0:
            self.source_combo.setCurrentIndex(index)

    def addTimestamps(self, source_name: str, events: list):
        if not events:
            self.logger.warning(f"No events provided by '{source_name}'.")
            return
        self.timestamp_dict[source_name] = events[:]
        self.original_timestamp_dict[source_name] = events[:]
        self.logger.debug(f"Added {len(events)} events from '{source_name}'.")
        self.refreshSourceCombo()
        self.updateView()

    def removeTimestamps(self, source_name: str):
        if source_name in self.timestamp_dict:
            del self.timestamp_dict[source_name]
        if source_name in self.original_timestamp_dict:
            del self.original_timestamp_dict[source_name]
        self.logger.debug(f"Removed events for source '{source_name}'.")
        self.refreshSourceCombo()
        self.updateView()

    @pyqtSlot()
    def removeSourceTimestamps(self):
        source = self.source_combo.currentText()
        if source:
            self.removeTimestamps(source)

    @pyqtSlot()
    def setSourceSpan(self):
        source = self.source_combo.currentText()
        if not source:
            QMessageBox.warning(self, "No Source Selected", "Please select a source.")
            return
        start_dt = self.source_start_edit.dateTime().toPyDateTime()
        end_dt = self.source_end_edit.dateTime().toPyDateTime()
        if start_dt >= end_dt:
            QMessageBox.warning(self, "Invalid Time Range", "Start time must be before end time.")
            return
        original_events = self.original_timestamp_dict.get(source, [])
        new_events = []
        for ev in original_events:
            if isinstance(ev, (tuple, list)):
                ts = ev[0]
            elif isinstance(ev, dict):
                ts = ev.get("timestamp")
            else:
                ts = ev
            if start_dt.timestamp() <= ts <= end_dt.timestamp():
                new_events.append(ev)
        self.timestamp_dict[source] = new_events
        self.logger.debug(f"Source '{source}' span set to {len(new_events)} events (filtered from {len(original_events)}).")
        self.updateView()

    @pyqtSlot()
    def resetSourceSpan(self):
        source = self.source_combo.currentText()
        if not source:
            QMessageBox.warning(self, "No Source Selected", "Please select a source.")
            return
        if source in self.original_timestamp_dict:
            self.timestamp_dict[source] = self.original_timestamp_dict[source][:]
            self.logger.debug(f"Source '{source}' span reset to full range ({len(self.timestamp_dict[source])} events).")
            self.updateView()
            ts_list = []
            for ev in self.timestamp_dict[source]:
                if isinstance(ev, (tuple, list)):
                    ts_list.append(ev[0])
                elif isinstance(ev, dict):
                    ts_list.append(ev.get("timestamp"))
                else:
                    ts_list.append(ev)
            if ts_list:
                start_qdt = QDateTime.fromSecsSinceEpoch(int(min(ts_list)))
                end_qdt = QDateTime.fromSecsSinceEpoch(int(max(ts_list)))
                self.source_start_edit.setDateTime(start_qdt)
                self.source_end_edit.setDateTime(end_qdt)
        else:
            QMessageBox.warning(self, "No Backup Found", "No original events available to reset.")

    def green_shade_for_source(self, source: str) -> str:
        h = hashlib.md5(source.encode('utf-8')).hexdigest()
        hash_val = int(h[:2], 16)
        green_val = int(50 + (hash_val / 255.0) * (255 - 50))
        return f"rgb(0, {green_val}, 0)"

    def red_shade_for_source(self, source: str) -> str:
        h = hashlib.md5(source.encode('utf-8')).hexdigest()
        hash_val = int(h[:2], 16)
        red_val = int(50 + (hash_val / 255.0) * (255 - 50))
        return f"rgb({red_val}, 0, 0)"

    def yellow_shade_for_source(self, source: str) -> str:
        h = hashlib.md5(source.encode('utf-8')).hexdigest()
        hash_val = int(h[:2], 16)
        yellow_val = int(50 + (hash_val / 255.0) * (255 - 10))
        return f"rgb({yellow_val + 40}, {yellow_val}, 50)"

    def updateView(self):
        """
        Update the view based on the current toggle state.
        """
        if self.showing_histogram:
            self.updateHistogramTimeline()
        else:
            self.update2DScatterTimeline()

    @pyqtSlot()
    def toggleView(self):
        """
        Toggles between Histogram and 2D Scatter views.
        When switching to 2D Scatter, a dialog asks the user for a time_taken threshold.
        """
        if self.showing_histogram:
            # Switch to 2D scatter; ask for threshold.
            threshold, ok = QInputDialog.getDouble(
                self,
                "2D Scatter Threshold",
                "Enter time_taken threshold (only events with time_taken >= threshold will be shown):",
                value=self.scatter_threshold, min=0
            )
            if ok:
                self.scatter_threshold = threshold
                self.showing_histogram = False
                self.toggle_view_btn.setText("Show Histogram")
                self.logger.info(f"Switching to 2D Scatter view with threshold: {self.scatter_threshold}")
                self.update2DScatterTimeline()
            else:
                # User cancelled: remain in histogram view.
                self.logger.info("User cancelled threshold input. Staying in Histogram view.")
        else:
            # Switch back to histogram.
            self.showing_histogram = True
            self.toggle_view_btn.setText("Show 2D Scatter")
            self.logger.info("Switching to Histogram view.")
            self.updateHistogramTimeline()

    def update2DScatterTimeline(self):
        """
        Creates a 2D scatter plot using Plotly's Scattergl.
        Only events with time_taken >= self.scatter_threshold are plotted.
        Each source is its own trace. The x-axis is the datetime, y-axis is time_taken (ms).
        """

        max_points = 5000  # maximum number of points per source
        fig = go.Figure()

        for src, events in self.timestamp_dict.items():
            if not events:
                continue

            # We'll collect x=datetimes, y=time_taken, plus hover_text
            x_vals = []
            y_vals = []
            hover_texts = []

            for ev in events:
                # If ev is a tuple/list: (timestamp, time_taken)
                # If ev is a dict: use ev["timestamp"], ev["time_taken"]
                if isinstance(ev, (tuple, list)):
                    ts, value = ev[0], ev[1]
                elif isinstance(ev, dict):
                    ts = ev.get("timestamp")
                    value = ev.get("time_taken", 0)
                else:
                    # If it's just a float (timestamp) or something
                    ts = ev
                    value = 0

                # Convert the time_taken to float (handle None or string)
                try:
                    numeric_value = float(value)
                except Exception:
                    numeric_value = 0

                if numeric_value >= self.scatter_threshold:
                    # Convert timestamp (epoch) to a Python datetime
                    dt_obj = datetime.fromtimestamp(ts)

                    x_vals.append(dt_obj)
                    y_vals.append(numeric_value)

                    # Build hover text showing both time and time_taken
                    dt_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                    hover_texts.append(f"Timestamp: {dt_str}<br>Time Taken: {numeric_value} ms")

            if not x_vals:
                continue  # No events in this source passed the threshold

            # If there are too many points, sample them to max_points
            if len(x_vals) > max_points:
                indices = np.linspace(0, len(x_vals) - 1, max_points, dtype=int)
                x_vals = [x_vals[i] for i in indices]
                y_vals = [y_vals[i] for i in indices]
                hover_texts = [hover_texts[i] for i in indices]

            # Choose a color for this source
            # We can reuse your "green_shade_for_source", "red_shade_for_source", etc.
            if 'IIS' in src.upper():
                color = self.green_shade_for_source(src)
            elif 'EVTX' in src.upper():
                color = self.red_shade_for_source(src)
            elif src.startswith("GenericLog:"):
                color = self.yellow_shade_for_source(src)
            else:
                color = 'blue'

            # Add a Scattergl trace for this source
            fig.add_trace(go.Scattergl(
                x=x_vals,
                y=y_vals,
                mode='markers',
                marker=dict(size=5, color=color, opacity=0.8),
                name=src,
                text=hover_texts,     # The hover text for each point
                hoverinfo='text'
            ))

        # Configure layout
        fig.update_layout(
            title=f"2D Scatter Timeline (time_taken >= {self.scatter_threshold})",
            xaxis=dict(title='Time'),
            yaxis=dict(title='Time Taken (ms)'),
            template='plotly_dark',
            margin=dict(l=50, r=50, t=50, b=50),
        )

        # Convert to HTML and display in the QWebEngineView
        plot_html = pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id='plotly-div')
        self.loadPlotHtml(plot_html)

    def updateHistogramTimeline(self):
        """
        Merges the events from all sources into a histogram view.
        Each source is shown as its own trace (using binned counts) with custom hover text.
        Uses NumPy to compute the histogram quickly.
        """
        fig = go.Figure()
        for src, events in self.timestamp_dict.items():
            if not events:
                continue
            counts, bins, bin_info = self.histogramData(events)
            bins_datetime = [datetime.fromtimestamp(ts) for ts in bins[:-1]]
            if 'IIS' in src.upper():
                color = self.green_shade_for_source(src)
            elif 'EVTX' in src.upper():
                color = self.red_shade_for_source(src)
            elif src.startswith("GenericLog:"):
                color = self.yellow_shade_for_source(src)
            else:
                color = 'blue'
            hover_text = []
            for cnt, info_list in zip(counts, bin_info):
                text = f"Count: {cnt}"
                if info_list:
                    details = "<br>".join(info_list)
                    text += f"<br>Details: {details}"
                hover_text.append(text)
            fig.add_trace(go.Scatter(
                x=bins_datetime,
                y=counts,
                mode='markers',
                marker=dict(size=8, color=color, opacity=0.8),
                name=src,
                text=hover_text,
                hoverinfo='text'
            ))
        fig.update_layout(
            title="Consolidated Log Timeline (Histogram)",
            xaxis=dict(title='Time'),
            yaxis=dict(title='Number of Events'),
            hovermode='closest',
            margin=dict(l=50, r=50, t=50, b=50),
            template='plotly_dark'
        )
        plot_html = pio.to_html(fig, include_plotlyjs=False, full_html=False, div_id='plotly-div')
        self.loadPlotHtml(plot_html)

    def loadPlotHtml(self, plot_html: str):
        """
        Loads the given Plotly HTML into the timeline view.
        """
        html_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..',
            'utilities', 'html',
            'timeline.html'
        ))
        if not os.path.exists(html_file_path):
            self.logger.error(f"Timeline HTML file not found at: {html_file_path}")
            QMessageBox.critical(self, "File Error", f"Timeline HTML file not found:\n{html_file_path}")
            return
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
        final_html = html_template.replace('{{plot}}', plot_html)
        self.web_view.setHtml(
            final_html,
            baseUrl=QUrl.fromLocalFile(os.path.abspath(os.path.dirname(html_file_path)) + '/')
        )
        self.logger.info("Timeline updated with new data.")

    def histogramData(self, events):
        """
        Uses NumPy to compute the histogram.
        Expects each event to be a tuple (timestamp, time_taken) – only the timestamp is used.
        A fixed bin width of 60 seconds is used.
        Returns counts (as a list), bins (as a list), and an empty bin_info list.
        """
        if not events:
            self.logger.info("histogramData: No events provided.")
            return [], [], []
        self.logger.info("histogramData: Starting to process %d events using NumPy.", len(events))
        timestamps = np.array([ev if isinstance(ev, (float, int)) else ev[0] for ev in events], dtype=np.float64)
        min_ts = timestamps.min()
        max_ts = timestamps.max()
        delta = max_ts - min_ts
        bin_width = 60
        num_bins = int(np.ceil(delta / bin_width))
        bins = np.linspace(min_ts, min_ts + num_bins * bin_width, num_bins + 1)
        counts, _ = np.histogram(timestamps, bins=bins)
        bin_info = [[] for _ in range(num_bins)]
        self.logger.info("histogramData: Computed %d bins.", num_bins)
        return counts.tolist(), bins.tolist(), bin_info

    def displayEmptyTimeline(self):
        """
        Displays an empty timeline with a "No data available" annotation.
        """
        fig = go.Figure(
            data=[],
            layout=go.Layout(
                title="Log Timeline",
                xaxis=dict(title="Time"),
                yaxis=dict(title="Number of Events"),
                annotations=[{
                    "text": "No data available.",
                    "xref": "paper", "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20}
                }]
            )
        )
        plot_html = pio.to_html(fig, include_plotlyjs=False, full_html=False)
        self.loadPlotHtml(plot_html)

    def displayErrorTimeline(self, message):
        """
        Displays an error message within the timeline view.
        """
        fig = go.Figure(
            data=[],
            layout=go.Layout(
                title="Log Timeline - Error",
                xaxis=dict(title="Time"),
                yaxis=dict(title="Number of Events"),
                annotations=[{
                    "text": f"Error: {message}",
                    "xref": "paper", "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "red"}
                }]
            )
        )
        plot_html = pio.to_html(fig, include_plotlyjs=False, full_html=False)
        self.loadPlotHtml(plot_html)

    @pyqtSlot(str)
    def emitJumpToTimeSignal(self, x_str):
        """
        Parses the clicked x-value from the timeline and emits jumpToTimeSignal.
        """
        try:
            dt = date_parser.parse(x_str)
            self.logger.debug(f"Emitting jumpToTimeSignal with datetime: {dt}")
            self.jumpToTimeSignal.emit(dt)
        except Exception as e:
            self.logger.error(f"Could not parse datetime from '{x_str}': {e}")
            self.displayErrorTimeline(f"Could not parse datetime from '{x_str}': {e}")
