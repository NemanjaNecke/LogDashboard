import os
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem,
    QSplitter, QFileDialog, QToolBar, QAction, QMessageBox, QMainWindow, QApplication, QComboBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from lxml import etree

# Mapping from FREB version to its transformation XSL file.
TRANSFORMATIONS = {
    "2008R2": os.path.join("resources", "freb", "2008R2.xsl"),
    "2012": os.path.join("resources", "freb", "2012.xsl"),
    "2012R2": os.path.join("resources", "freb", "2012R2.xsl"),
    "2016": os.path.join("resources", "freb", "2016.xsl"),
    "2019": os.path.join("resources", "freb", "2019.xsl"),
    "2022": os.path.join("resources", "freb", "2022.xsl"),
}

class FrebViewerDock(QDockWidget):
    def __init__(self, xml_path=None, parent=None):
        """
        Main FREB viewer.
        If xml_path is provided, load it immediately.
        Otherwise, a “no file loaded” message is shown.
        """
        super().__init__("FREB Trace Viewer", parent)
        self.xml_path = xml_path  # may be None initially
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.initUI()
        if self.xml_path:
            self.processXml()
        else:
            self.showNoFileMessage()

    def initUI(self):
        # Toolbar with two actions: Open FREB and Compare FREB.
        self.toolbar = QToolBar("FREB Actions", self)
        open_action = QAction("Open FREB File", self)
        open_action.triggered.connect(self.openFrebFile)
        self.toolbar.addAction(open_action)

        compare_action = QAction("Compare FREB", self)
        compare_action.triggered.connect(self.compareFrebFile)
        self.toolbar.addAction(compare_action)

        # Add a combo box for selecting the transformation version.
        self.versionCombo = QComboBox(self)
        self.versionCombo.addItems(list(TRANSFORMATIONS.keys()))
        self.versionCombo.setCurrentText("2008R2")  # default selection
        # Whenever the user picks a different version, re-transform the file (if loaded).
        self.versionCombo.currentIndexChanged.connect(self.onVersionChanged)
        self.toolbar.addWidget(self.versionCombo)

        # File browser to list all XML files from the folder.
        self.fileBrowser = QListWidget()
        self.fileBrowser.itemDoubleClicked.connect(self.onFileDoubleClicked)

        # Main tab widget for three views:
        #  (1) Request Summary
        #  (2) Request Details (has its own sub-tabs)
        #  (3) Compact View
        self.mainTab = QTabWidget()
        self.summaryView = QWebEngineView(self)
        self.detailsTab = QTabWidget(self)  # <--- sub-tabs will go here
        self.compactView = QWebEngineView(self)
        self.mainTab.addTab(self.summaryView, "Request Summary")
        self.mainTab.addTab(self.detailsTab, "Request Details")
        self.mainTab.addTab(self.compactView, "Compact View")

        # Splitter: file browser on left, tab widget on right
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.fileBrowser)
        self.splitter.addWidget(self.mainTab)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)

        # Central widget layout.
        central = QWidget()
        vlayout = QVBoxLayout(central)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.addWidget(self.toolbar)
        vlayout.addWidget(self.splitter)
        central.setLayout(vlayout)
        self.setWidget(central)

    def showNoFileMessage(self):
        html = ("<html><body><h2>No FREB file loaded</h2>"
                "<p>Use the toolbar button above to open a FREB XML file.</p></body></html>")
        self.summaryView.setHtml(html)
        self.compactView.setHtml(html)
        self.detailsTab.clear()
        placeholder = self.createWebView(html)
        self.detailsTab.addTab(placeholder, "Details")

    def openFrebFile(self):
        xml_file, _ = QFileDialog.getOpenFileName(self, "Open FREB XML File", "", "XML Files (*.xml)")
        if xml_file:
            self.xml_path = xml_file
            self.processXml()

    def compareFrebFile(self):
        # Compare with another FREB file by opening a new compare window.
        if not self.xml_path:
            QMessageBox.warning(self, "No File Loaded", "Please load a FREB file first.")
            return
        folder = os.path.dirname(self.xml_path)
        compare_file, _ = QFileDialog.getOpenFileName(self, "Select FREB File to Compare", folder, "XML Files (*.xml)")
        if compare_file:
            compare_window = FrebCompareWindow(self.xml_path, compare_file)
            compare_window.show()

    def onFileDoubleClicked(self, item: QListWidgetItem):
        file_path = item.data(Qt.UserRole)
        self.xml_path = file_path
        self.processXml()

    def onVersionChanged(self):
        """Re-run processXml() if a file is already loaded."""
        if self.xml_path:
            self.processXml()

    def processXml(self):
        """
        1. Update file list in the left-hand browser.
        2. Parse the XML and run the chosen XSL transform for the Summary and (optionally) Compact tabs.
        3. Build 7 sub-tabs in the 'Request Details' tab using Python-based logic (like your original approach).
        """
        folder = os.path.dirname(self.xml_path)
        self.populateFileBrowser(folder)

        # Attempt to parse the XML
        try:
            tree = etree.parse(self.xml_path)
            root = tree.getroot()
        except Exception as e:
            error_html = f"<html><body><h1>Error loading XML:</h1><p>{e}</p></body></html>"
            self.summaryView.setHtml(error_html)
            self.compactView.setHtml(error_html)
            self.detailsTab.clear()
            placeholder = self.createWebView(error_html)
            self.detailsTab.addTab(placeholder, "Details")
            return

        # --- 1) Transform for Request Summary (Tab #1) ---
        selected_version = self.versionCombo.currentText()
        xsl_file = TRANSFORMATIONS.get(selected_version)
        if not xsl_file or not os.path.exists(xsl_file):
            error_html = (
                f"<html><body><h1>Error:</h1>"
                f"<p>XSL file for version {selected_version} not found.</p></body></html>"
            )
            self.summaryView.setHtml(error_html)
        else:
            try:
                xsl_tree = etree.parse(xsl_file)
                transform = etree.XSLT(xsl_tree)
                result = transform(tree)
                html = str(result)
            except Exception as e:
                html = f"<html><body><h1>Error transforming XML:</h1><p>{e}</p></body></html>"
            self.summaryView.setHtml(html)

        # --- 2) Build Request Details (sub-tabs) with Python logic ---
        # Extract event_data from the FREB XML so we can build the sub-tabs
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        events = root.findall("ev:Event", ns)
        prev_time = None
        event_data = []
        for event in events:
            time_elem = event.find("ev:System/ev:TimeCreated", ns)
            time_str = time_elem.get("SystemTime") if time_elem is not None else None
            current_time = None
            if time_str:
                # Some FREBs use 'Z' at the end; we can safely replace it
                time_str_clean = time_str.replace("Z", "+00:00")
                current_time = datetime.fromisoformat(time_str_clean)
            duration = 0
            if prev_time and current_time:
                duration = (current_time - prev_time).total_seconds() * 1000  # ms
            prev_time = current_time

            level = event.findtext("ev:System/ev:Level", default="N/A", namespaces=ns)
            event_data.append({
                "time": time_str,
                "duration": duration,
                "level": level,
                "event": event
            })

        # Clear out whatever was in detailsTab; build sub-tabs
        self.detailsTab.clear()
        complete_html = self.build_complete_request_trace_html(event_data)
        filter_html = self.build_filter_notifications_html(event_data)
        module_html = self.build_module_notifications_html(event_data)
        performance_html = self.build_performance_view_html(event_data)
        auth_html = self.build_authentication_authorization_html(event_data)
        aspx_html = self.build_aspx_page_traces_html(event_data)
        custom_html = self.build_custom_module_traces_html(event_data)
        fastcgi_html = self.build_fastcgi_module_html(event_data)

        self.detailsTab.addTab(self.createWebView(complete_html), "Complete Request Trace")
        self.detailsTab.addTab(self.createWebView(filter_html), "Filter Notifications")
        self.detailsTab.addTab(self.createWebView(module_html), "Module Notifications")
        self.detailsTab.addTab(self.createWebView(performance_html), "Performance View")
        self.detailsTab.addTab(self.createWebView(auth_html), "Authentication Authorization")
        self.detailsTab.addTab(self.createWebView(aspx_html), "ASP.Net Page Traces")
        self.detailsTab.addTab(self.createWebView(custom_html), "Custom Module Traces")
        self.detailsTab.addTab(self.createWebView(fastcgi_html), "FastCGI Module")

        # --- 3) Compact View (Tab #3) ---
        # Option A: Also run XSL to produce the compact view
        # self.compactView.setHtml(html)
        # Option B: Use your python-based "compact" approach:
        compact_html = self.build_compact(event_data)
        self.compactView.setHtml(compact_html)

    def populateFileBrowser(self, folder):
        self.fileBrowser.clear()
        if os.path.isdir(folder):
            for filename in os.listdir(folder):
                if filename.lower().endswith(".xml"):
                    full_path = os.path.join(folder, filename)
                    item = QListWidgetItem(filename)
                    item.setData(Qt.UserRole, full_path)
                    self.fileBrowser.addItem(item)

    def createWebView(self, html_content):
        view = QWebEngineView()
        view.setHtml(html_content)
        return view

    # ==========================
    #  (Below) Methods for building each sub-tab's HTML in Python
    # ==========================

    def build_complete_request_trace_html(self, event_data):
        """
        This example uses an expand/collapse approach for each event,
        as in your prior code snippet.
        """
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    .event-container { margin-bottom: 10px; border: 1px solid #ddd; }
    .event-header { padding: 8px; background-color: #f5f5f5; cursor: pointer; display: flex; justify-content: space-between; }
    .event-details { padding: 8px; display: none; }
    .severity { padding: 2px 5px; border-radius: 3px; }
    .severity-critical { background-color: #990000; color: white; }
    .severity-error { background-color: #ffcccc; }
    .severity-warning { background-color: #fff3cd; }
    .data-table { width: 100%; border-collapse: collapse; }
    .data-table td, .data-table th { border: 1px solid #ddd; padding: 4px; }
    .toggle { font-weight: bold; margin-right: 10px; }
</style>
<script>
function toggleDetails(id) {
    const details = document.getElementById('details_' + id);
    const toggle = document.getElementById('toggle_' + id);
    if (details.style.display === 'none') {
        details.style.display = 'block';
        toggle.textContent = '-';
    } else {
        details.style.display = 'none';
        toggle.textContent = '+';
    }
}
</script>
</head>
<body>
<h1>Complete Request Trace</h1>"""

        for idx, event in enumerate(event_data, 1):
            evt = event["event"]
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            rendering = evt.find("ev:RenderingInfo", namespaces=ns)
            opcode = rendering.findtext("ev:Opcode", default="N/A", namespaces=ns) if rendering is not None else "N/A"
            severity = self.get_severity(event["level"])

            # Gather additional <Data> elements
            data_elements = {}
            for data in evt.findall("ev:EventData/ev:Data", namespaces=ns):
                name = data.get("Name", "")
                if name not in ["ContextId", "ConnId"]:
                    data_elements[name] = data.text or ""

            data_rows = "\n".join(
                f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in data_elements.items()
            )

            html_content += f"""
<div class="event-container">
  <div class="event-header" onclick="toggleDetails({idx})">
    <div>
      <span class="toggle" id="toggle_{idx}">+</span>
      <span>{idx}. {opcode}</span>
    </div>
    <div>
      <span class="severity {severity['class']}">{severity['label']}</span>
      <span>{time_str}</span>
    </div>
  </div>
  <div class="event-details" id="details_{idx}" style="display:none;">
    <table class="data-table">
      <tbody>
        {data_rows}
        <tr><th>Duration</th><td>{event['duration']:.2f} ms</td></tr>
      </tbody>
    </table>
  </div>
</div>"""

        html_content += "</body></html>"
        return html_content

    def build_filter_notifications_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        filtered = []
        for e in event_data:
            evt = e["event"]
            filter_name = evt.findtext("ev:EventData/ev:Data[@Name='FilterName']", namespaces=ns)
            if filter_name:  # means it's a filter notification event
                filtered.append(e)
        rows = []
        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            rendering = evt.find("ev:RenderingInfo", namespaces=ns)
            opcode = rendering.findtext("ev:Opcode", default="N/A", namespaces=ns) if rendering is not None else "N/A"
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            datas = []
            for d in evt.findall("ev:EventData/ev:Data", namespaces=ns):
                datas.append(f'{d.get("Name")}: {d.text or ""}')
            data_summary = ", ".join(datas)
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td><td>{data_summary}</td></tr>")

        headers = ["No.", "Opcode", "Time", "Data"]
        return self.build_table_html("Filter Notifications", headers, rows)

    def build_module_notifications_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        filtered = []
        for e in event_data:
            evt = e["event"]
            module = evt.findtext("ev:EventData/ev:Data[@Name='ModuleName']", namespaces=ns)
            notification = evt.findtext("ev:EventData/ev:Data[@Name='Notification']", namespaces=ns)
            if module and notification:
                filtered.append(e)

        html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    .notification-table { width: 100%; border-collapse: collapse; }
    .notification-table th, .notification-table td { border: 1px solid #ddd; padding: 8px; }
    .details-row td { padding: 0 !important; }
    .nested-table { width: 100%; background-color: #f9f9f9; }
    .nested-table td { padding: 4px 8px; }
</style>
</head>
<body>
<h1>Module Notifications</h1>
<table class="notification-table">
    <thead>
    <tr>
        <th>No.</th>
        <th>Module</th>
        <th>Notification</th>
        <th>Duration (ms)</th>
    </tr>
    </thead>
    <tbody>"""

        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            module = evt.findtext("ev:EventData/ev:Data[@Name='ModuleName']", namespaces=ns)
            notification = evt.findtext("ev:EventData/ev:Data[@Name='Notification']", namespaces=ns)
            data_elements = []
            for data in evt.findall("ev:EventData/ev:Data", namespaces=ns):
                nm = data.get("Name")
                if nm not in ["ModuleName", "Notification"]:
                    data_elements.append((nm, data.text or ""))
            data_rows = "\n".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data_elements)
            html_content += f"""
    <tr>
        <td>{idx}</td>
        <td>{module}</td>
        <td>{notification}</td>
        <td>{event['duration']:.2f}</td>
    </tr>
    <tr class="details-row">
        <td colspan="4">
        <table class="nested-table">
            <tbody>
            {data_rows}
            </tbody>
        </table>
        </td>
    </tr>"""

        html_content += "</tbody></table></body></html>"
        return html_content

    def build_performance_view_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        rows = []
        for idx, e in enumerate(event_data, 1):
            evt = e["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            duration = e["duration"]
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{duration:.2f}</td></tr>")

        headers = ["No.", "Event", "Duration (ms)"]
        return self.build_table_html("Performance View", headers, rows)

    def build_authentication_authorization_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        filtered = []
        for e in event_data:
            evt = e["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="", namespaces=ns)
            # e.g., "AUTH_SUCCESS", "SECURITY_START", etc.
            if opcode.startswith("AUTH_") or opcode.startswith("SECURITY_"):
                filtered.append(e)
        rows = []
        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            datas = []
            for d in evt.findall("ev:EventData/ev:Data", namespaces=ns):
                datas.append(f'{d.get("Name")}: {d.text or ""}')
            data_summary = ", ".join(datas)
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td><td>{data_summary}</td></tr>")

        headers = ["No.", "Opcode", "Time", "Data"]
        return self.build_table_html("Authentication & Authorization", headers, rows)

    def build_aspx_page_traces_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        # e.g., AspNetPageTraceWarnEvent, AspNetPageTraceWriteEvent
        filtered = []
        for e in event_data:
            opcode = e["event"].findtext("ev:RenderingInfo/ev:Opcode", default="", namespaces=ns)
            if opcode in ("AspNetPageTraceWarnEvent", "AspNetPageTraceWriteEvent"):
                filtered.append(e)

        rows = []
        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            datas = []
            for d in evt.findall("ev:EventData/ev:Data", namespaces=ns):
                datas.append(f'{d.get("Name")}: {d.text or ""}')
            data_summary = ", ".join(datas)
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td><td>{data_summary}</td></tr>")

        headers = ["No.", "Opcode", "Time", "Data"]
        return self.build_table_html("ASP.Net Page Traces", headers, rows)

    def build_custom_module_traces_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        # e.g., "ModuleDiag"
        filtered = []
        for e in event_data:
            opcode = e["event"].findtext("ev:RenderingInfo/ev:Opcode", default="", namespaces=ns)
            if "ModuleDiag" in opcode:
                filtered.append(e)

        rows = []
        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            module = evt.findtext("ev:EventData/ev:Data[@Name='ModuleName']", namespaces=ns) or "N/A"
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td><td>{module}</td></tr>")

        headers = ["No.", "Opcode", "Time", "Module"]
        return self.build_table_html("Custom Module Traces", headers, rows)

    def build_fastcgi_module_html(self, event_data):
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        # e.g., "FASTCGI_..."
        filtered = []
        for e in event_data:
            opcode = e["event"].findtext("ev:RenderingInfo/ev:Opcode", default="", namespaces=ns)
            if opcode.startswith("FASTCGI_"):
                filtered.append(e)

        rows = []
        for idx, event in enumerate(filtered, 1):
            evt = event["event"]
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            time_str = event["time"][11:23] if (event["time"] and len(event["time"]) > 11) else "N/A"
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td></tr>")

        headers = ["No.", "Opcode", "Time"]
        return self.build_table_html("FastCGI Module", headers, rows)

    def build_compact(self, event_data):
        """
        Builds a "compact" view table with: No., Opcode, Time
        """
        ns = {"ev": "http://schemas.microsoft.com/win/2004/08/events/event"}
        rows = []
        for idx, e in enumerate(event_data, 1):
            evt = e["event"]
            time_str = e["time"][11:23] if (e["time"] and len(e["time"]) > 11) else "N/A"
            opcode = evt.findtext("ev:RenderingInfo/ev:Opcode", default="N/A", namespaces=ns)
            rows.append(f"<tr><td>{idx}</td><td>{opcode}</td><td>{time_str}</td></tr>")

        headers = ["No.", "Opcode", "Time"]
        return self.build_table_html("Compact View", headers, rows)

    def build_table_html(self, title, headers, rows):
        """
        Helper for building table-based HTML quickly.
        """
        header_html = "".join([f"<th>{h}</th>" for h in headers])
        rows_html = "".join(rows)
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #333; padding: 4px; }}
    th {{ background-color: #ddd; }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
  </style>
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
  <table>
    <thead><tr>{header_html}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""

    def get_severity(self, level):
        """
        Helper to label severity levels (like 'Critical', 'Error', 'Warning')
        to style them differently in the HTML trace.
        """
        severity_map = {
            '1': {'label': 'Critical', 'class': 'severity-critical'},
            '2': {'label': 'Error',    'class': 'severity-error'},
            '3': {'label': 'Warning',  'class': 'severity-warning'},
            '4': {'label': 'Info',     'class': ''},
            '5': {'label': 'Verbose',  'class': ''},
        }
        return severity_map.get(level, {'label': 'N/A', 'class': ''})


# --- Compare Window and Panel Implementation ---

class FrebComparePanel(QWidget):
    """
    A compare panel consists of its own toolbar (with an "Open FREB File" button and a
    combo box to select the transformation version) and a QWebEngineView that displays
    the transformed FREB file.
    """
    def __init__(self, initial_xml_path=None, parent=None):
        super().__init__(parent)
        self.xml_path = initial_xml_path
        self.initUI()
        if self.xml_path:
            self.loadFile()

    def initUI(self):
        layout = QVBoxLayout(self)
        # Toolbar for this panel
        self.toolbar = QToolBar("Panel Actions", self)
        open_action = QAction("Open FREB File", self)
        open_action.triggered.connect(self.openFrebFile)
        self.toolbar.addAction(open_action)

        # Combo box for transformation version
        self.transformCombo = QComboBox(self)
        self.transformCombo.addItems(list(TRANSFORMATIONS.keys()))
        layout.addWidget(self.toolbar)
        self.toolbar.addWidget(self.transformCombo)

        # When user changes version, reload the file (if any) to re-transform
        self.transformCombo.currentIndexChanged.connect(self.loadFile)

        # Web view for displaying transformed HTML
        self.webView = QWebEngineView(self)
        layout.addWidget(self.webView)
        self.setLayout(layout)

    def openFrebFile(self):
        xml_file, _ = QFileDialog.getOpenFileName(self, "Open FREB XML File", "", "XML Files (*.xml)")
        if xml_file:
            self.xml_path = xml_file
            self.loadFile()

    def loadFile(self):
        if not self.xml_path:
            self.webView.setHtml("<html><body><h2>No FREB file loaded</h2></body></html>")
            return
        try:
            tree = etree.parse(self.xml_path)
        except Exception as e:
            error_html = f"<html><body><h1>Error loading XML:</h1><p>{e}</p></body></html>"
            self.webView.setHtml(error_html)
            return

        selected_version = self.transformCombo.currentText()
        xsl_file = TRANSFORMATIONS.get(selected_version)
        if not xsl_file or not os.path.exists(xsl_file):
            error_html = f"<html><body><h1>Error:</h1><p>XSL file for version {selected_version} not found.</p></body></html>"
            self.webView.setHtml(error_html)
            return

        try:
            xsl_tree = etree.parse(xsl_file)
            transform = etree.XSLT(xsl_tree)
            result = transform(tree)
            html = str(result)
        except Exception as e:
            html = f"<html><body><h1>Error transforming XML:</h1><p>{e}</p></body></html>"

        self.webView.setHtml(html)


class FrebCompareWindow(QMainWindow):
    def __init__(self, xml_path1=None, xml_path2=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare FREB Files")
        # Create two independent compare panels, side by side.
        self.panel1 = FrebComparePanel(xml_path1)
        self.panel2 = FrebComparePanel(xml_path2)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.panel1)
        splitter.addWidget(self.panel2)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

