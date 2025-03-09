# Log Dashboard

**Log Dashboard** is a modular desktop application designed for viewing, analyzing, and comparing log files. It supports **IIS logs**, **EVTX logs**, and **Customer Generic logs** in a single unified interface. With a modern, dark-themed UI built using PyQt5 and qdarkstyle, the app provides a flexible and intuitive experience for log analysis.

## Features

- **Modular Approach:**  
  At startup, the user is prompted to select which modules to load:
  - **IIS Module:** View, parse, and analyze IIS log files.
  - **EVTX Module:** Open and inspect Windows Event Logs (EVTX).
  - **GENERIC Module:** Load and view custom log formats.
- **Always Available Components:**  
  - **Timeline Dock:** Visualize log events on a timeline and jump to specific times.
  - **DB Manager Dock:** Manage databases and stored logs.
  - **Log Dock:** View detailed logs and debugging information.
- **Advanced Analysis Tools:**  
  Analyze IIS logs and generate Excel reports. Compare log reports and review detailed statistics.
- **Modern UI:**  
  Utilizes PyQt5 for the GUI and qdarkstyle for an attractive dark theme.

## Requirements

- Python 3.12 (or compatible)
- PyQt5
- qdarkstyle
- pandas
- Other dependencies as listed in [`requirements.txt`](requirements.txt)

## Installation

1. **Clone the repository:**

   ```
   git clone https://github.com/yourusername/LogDashboard.git
   cd LogDashboard
  ```

2. **Create and activate a virtual environment:**

- **On Windows:**

  ```
  python -m venv venv
  venv\Scripts\activate
  ```

- **On macOS/Linux:**

  ```
  python3 -m venv venv
  source venv/bin/activate
  ```
3. **Install dependencies:**

  ```
  pip install -r requirements.txt
  ```

4. **Run the application:**

  ```
  python logdashboard/main.py
  ```

## Usage
**Module Selection:**  
When you start the application, a dialog will prompt you to choose which modules to load (IIS, EVTX, GENERIC). The Timeline, DB Manager, and Log Dock are always available.

**Opening Logs:**

- Use the **File** menu to open log files or databases.
- The **IIS** menu allows you to open and analyze IIS logs.
- The **EVTX** menu provides options for EVTX logs.
- The **GENERIC** menu is for custom log types.

**Analysis and Reporting:**  
The IIS module includes analysis tools. You can run log analysis, generate Excel reports, select specific sheets, and compare report data—all from within the application.

## Building an Executable

To build a standalone executable using PyInstaller, run the following command from the folder that contains the `logdashboard` folder:


```
pyinstaller --onedir --name LogDashboard --add-data "logdashboard/resources;logdashboard/resources" --add-data "logdashboard/utilities/html;logdashboard/utilities/html" logdashboard/main.py
```
This creates a dist/LogDashboard folder containing the executable.

Project Structure
```
logdashboard/
├── main.py
├── __init__.py
├── data/
│   └── log_parsers/       # Parsers for EVTX, GENERIC, and IIS logs
├── db/                   # Sample databases and logs
├── logs/                 # Application log files
├── resources/            # Icons, XSL stylesheets, and other assets
├── services/             # Core logic (analyze, controllers, logging, SQL workers)
├── ui/                   # GUI components (docks, dialogs, module selection)
│   ├── components/
│   │   ├── charts/
│   │   ├── db_load/
│   │   ├── display_logs/
│   │   ├── startup/      # ModuleSelectionDialog for choosing modules at startup
│   │   └── timeline/
│   └── main_window.py    # Main application window
├── utilities/            # Utility scripts and HTML templates
└── venv/                 # Virtual environment folder
```
Contributing
Contributions are welcome! If you wish to enhance the application, please open an issue or submit a pull request. Make sure to follow existing code style and update tests as necessary.
