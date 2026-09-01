import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, 
    QWidget, QTextEdit, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal

def get_picotool_path():
    """同梱された picotool バイナリのパスを取得"""
    # PyInstaller による単一ファイル化（--onefile）時の展開先パス
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # OSに応じた実行ファイル名
    binary_name = "picotool.exe" if sys.platform == "win32" else "picotool"
    picotool_bin = os.path.join(base_path, binary_name)

    # 同梱バイナリが存在しない場合はシステムのPATHを探す
    if not os.path.exists(picotool_bin):
        picotool_bin = binary_name
        
    return picotool_bin

class FlashWorker(QThread):
    """書き込み処理を別スレッドで実行してUIフリーズを防ぐ"""
    output_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        picotool = get_picotool_path()
        cmd = [picotool, "load", self.file_path, "--ignore-partitions", "-fx"]
        
        self.output_signal.emit(f"[実行コマンド]\n{' '.join(cmd)}\n")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            for line in process.stdout:
                self.output_signal.emit(line)

            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.output_signal.emit(f"実行エラー: {str(e)}\n")
            self.finished_signal.emit(-1)

class DropArea(QLabel):
    """ドラッグ＆ドロップ受付エリア"""
    file_dropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setText("ここに .uf2 ファイルを\nドラッグ＆ドロップ")
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #888888;
                border-radius: 12px;
                background-color: #f7f9fa;
                color: #555555;
                font-size: 15px;
                font-weight: bold;
            }
            QLabel:hover {
                border-color: #007acc;
                background-color: #eef6fc;
                color: #007acc;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".uf2"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        files = event.mimeData().urls()
        if files:
            file_path = files[0].toLocalFile()
            self.file_dropped.emit(file_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Picotool Flash Wrapper")
        self.resize(460, 360)

        # メインレイアウト
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ドロップエリア
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self.start_flash)
        layout.addWidget(self.drop_area, stretch=3)

        # ログ出力エリア
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_area, stretch=4)

        self.setCentralWidget(central_widget)
        self.worker = None

    def start_flash(self, file_path):
        self.drop_area.setEnabled(False)
        self.log_area.clear()
        self.log_area.append(f"対象ファイル:\n{file_path}\n")
        
        self.worker = FlashWorker(file_path)
        self.worker.output_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.flash_finished)
        self.worker.start()

    def append_log(self, text):
        self.log_area.insertPlainText(text)
        # 自動スクロール
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def flash_finished(self, return_code):
        self.drop_area.setEnabled(True)
        if return_code == 0:
            self.append_log("\n[成功] 書き込みと再起動が完了しました。\n")
        else:
            self.append_log(f"\n[失敗] エラーコード: {return_code}\n")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
