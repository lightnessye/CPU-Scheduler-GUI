"""main.py
程序入口：创建调度算法演示窗口并进入 Tk 主循环。

运行方式：python main.py

说明：
- 本文件只负责“入口配置”，不包含任何界面细节，也不触碰调度算法逻辑；
  算法实现位于 scheduler.py，界面渲染位于 ui.py。
"""
import sys

from ui import SchedulerApp


def _enable_dpi_awareness():
    """在 Windows 高分屏下开启 DPI 感知，避免字体发虚。

    非 Windows 平台或调用失败时静默跳过，不影响程序正常运行。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Windows 10 1703+ 推荐的 API，设置失败再退回旧接口
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main():
    """初始化并运行 GUI 主程序。"""
    _enable_dpi_awareness()
    app = SchedulerApp()      # 窗口尺寸等配置集中在 ui.py 中
    app.run()


if __name__ == "__main__":
    main()
