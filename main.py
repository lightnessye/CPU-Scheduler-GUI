"""main.py
程序入口：创建调度算法演示窗口并进入 Tk 主循环。

运行方式：python main.py
"""
from ui import SchedulerApp


def main():
    app = SchedulerApp()
    app.run()


if __name__ == "__main__":
    main()
