from PyQt5.QtCore import QRunnable, pyqtSignal, QObject

class TimestampsWorkerSignals(QObject):
    finished = pyqtSignal(list)  # emit list of timestamps
    error = pyqtSignal(str)

class TimestampsWorker(QRunnable):
    def __init__(self, db_manager, table_name="iis_logs"):
        super().__init__()
        self.db_manager = db_manager
        self.table_name = table_name
        self.signals = TimestampsWorkerSignals()

    def run(self):
        try:
            timestamps = self.db_manager.get_all_timestamps(self.table_name)
            self.signals.finished.emit(timestamps)
        except Exception as e:
            self.signals.error.emit(str(e))