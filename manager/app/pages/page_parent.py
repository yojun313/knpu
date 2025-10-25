from ui.finder import openFileResult
from PyQt5.QtWidgets import QMessageBox
from services.logging import * 
from ui.status import unregister_thread, printStatus

class Manager_Page:
    def __init__(self):
        pass
    
    def worker_finished(self, success: bool, message: str, path: str = None):
        if success:
            openFileResult(self.main, message, path)
        else:
            QMessageBox.warning(self.main, "실패", f"작업을 실패했습니다.\n{message}")
    
    def worker_failed(self, error_message: str):
        QMessageBox.critical(self.main, "오류 발생", f"오류가 발생했습니다:\n{error_message}")
        programBugLog(self.main, error_message)
    
    def connectWorkerForDownloadDialog(self, worker, downloadDialog, thread_name):
        worker.progress.connect(lambda val, msg: (
            downloadDialog.update_progress(val), 
            downloadDialog.update_text_signal.emit(msg)
        ))
        worker.finished.connect(
            lambda ok, msg, path: (
                downloadDialog.complete_task(ok),
                self.worker_finished(ok, msg, path),
                unregister_thread(thread_name),
                printStatus(self.main)
            )
        )
        worker.error.connect(
            lambda err: (
                downloadDialog.complete_task(False),
                self.worker_failed(err),
                unregister_thread(thread_name),
                printStatus(self.main)
            )
        )
    def connectWorkerForStatusDialog(self, worker, statusDialog, thread_name):
        worker.message.connect(lambda msg: statusDialog.update_message(msg))
        worker.finished.connect(
            lambda ok, msg, path: (
                self.worker_finished(ok, msg, path),
                statusDialog.close(),
                unregister_thread(thread_name),
                printStatus(self.main)
            )
        )
        worker.error.connect(
            lambda err: (
                self.worker_failed(err),
                statusDialog.close(),
                unregister_thread(thread_name),
                printStatus(self.main)
            )
        )
      
      