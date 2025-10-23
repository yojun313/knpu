from ui.finder import openFileResult
from PyQt5.QtWidgets import QMessageBox
from services.logging import * 

class Manager_Page:
    def __init__(self):
        pass
    
    def worker_finished(self, success: bool, message: str, path: str = None):
        if success:
            print(path)
            openFileResult(self.main, message, path)
        else:
            QMessageBox.warning(self.main, "실패", f"작업을 실패했습니다.\n{message}")
    
    def worker_failed(self, error_message: str):
        QMessageBox.critical(self.main, "오류 발생", f"오류가 발생했습니다:\n{error_message}")
        programBugLog(self.main, error_message)
      
      