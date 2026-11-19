"""ui.py
Tkinter 图形界面模块：输入区、算法选择区、控制区、甘特图可视化区、结果区。

界面本身不实现调度算法，全部调度计算交给 scheduler.py，
本模块只负责：收集输入 -> 调用算法 -> 在 Canvas 上绘图 -> 展示结果。
"""
import math   # 用于 math.isfinite：拦截 "nan"、"inf" 这类能转 float 但非法的输入

import tkinter as tk
from tkinter import ttk, messagebox

import scheduler
from scheduler import Process

# 进程颜色调色板：按添加顺序依次分配，超出后循环使用
COLORS = [
    "#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#B07AA1",
    "#76B7B2", "#EDC948", "#FF9DA7", "#9C755F", "#BAB0AC",
]

# 算法下拉框选项：(显示文字, 传给 scheduler 的算法 key, 是否需要时间片)
ALGORITHMS = (
    ("FCFS（先来先服务）", "FCFS", False),
    ("SJF（短作业优先·非抢占）", "SJF", False),
    ("RR（时间片轮转）", "RR", True),
)

# 甘特图画布的固定尺寸与布局参数（配合 900x650 的窗口）
CANVAS_WIDTH = 860
CANVAS_HEIGHT = 195
LEFT_PAD = 50        # 画布左侧留白（时间轴从 x=50 开始）
RIGHT_PAD = 30       # 画布右侧留白
BAR_TOP = 50         # 矩形条顶部的 y 坐标（上方留出标注 PID 的空间）
BAR_HEIGHT = 45      # 矩形条高度
AXIS_Y = 148         # 时间轴基线的 y 坐标
IDLE_COLOR = "#e3e3e3"   # 空闲时段的浅灰色


class SchedulerApp:
    """CPU 进程调度算法演示程序主窗口。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CPU 进程调度算法演示（FCFS / SJF / RR）")
        self.root.resizable(False, False)

        # ---- 程序内部状态 ----
        self.processes = []        # 已添加的进程（Process 对象，保持添加顺序）
        self.proc_by_iid = {}      # 列表行号 iid -> Process 对象
        self._seq = 0              # 自增序号，保证行号和排序稳定键唯一
        self.pid_color = {}        # pid -> 甘特图颜色
        self._color_i = 0          # 下一个使用的调色板下标
        self.algorithm = tk.StringVar(value=ALGORITHMS[0][0])  # 下拉框当前显示的文字
        self.quantum_var = tk.StringVar(value="2")     # RR 时间片（默认 2）
        self.sim_result = None     # 最近一次模拟的结果

        # ---- 依次构建五个区域 ----
        self._build_input_area()
        self._build_algorithm_area()
        self._build_control_area()
        self._build_canvas_area()
        self._build_result_area()
        self._center_window()

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------

    def _build_input_area(self):
        """输入区（顶部）：三个输入框 + 添加按钮 + 已添加进程表格。"""
        frame = tk.LabelFrame(self.root, text="输入区：添加进程（列表实时显示，可选中删除）")
        frame.pack(side="top", fill="x", padx=10, pady=(8, 2))

        # 第一行：PID / 到达时间 / 服务时间 三个输入框 + 添加按钮
        tk.Label(frame, text="进程ID：").grid(row=0, column=0, padx=(8, 2), pady=6)
        self.pid_entry = tk.Entry(frame, width=12)
        self.pid_entry.grid(row=0, column=1, padx=2, pady=6)

        tk.Label(frame, text="到达时间：").grid(row=0, column=2, padx=(10, 2))
        self.arrival_entry = tk.Entry(frame, width=8)
        self.arrival_entry.grid(row=0, column=3, padx=2)

        tk.Label(frame, text="服务时间：").grid(row=0, column=4, padx=(10, 2))
        self.service_entry = tk.Entry(frame, width=8)
        self.service_entry.grid(row=0, column=5, padx=2)

        tk.Button(frame, text="添加进程", width=10,
                  command=self.add_process).grid(row=0, column=6, padx=(14, 8))

        # 在时间输入框按回车也能直接添加，方便连续录入
        self.pid_entry.bind("<Return>", lambda e: self.arrival_entry.focus_set())
        self.arrival_entry.bind("<Return>", lambda e: self.service_entry.focus_set())
        self.service_entry.bind("<Return>", lambda e: self.add_process())

        # 第二行：已添加进程表格 + 删除按钮
        list_row = tk.Frame(frame)
        list_row.grid(row=1, column=0, columnspan=7, sticky="ew",
                      padx=8, pady=(2, 8))
        columns = ("pid", "arrival", "service")
        self.process_tree = ttk.Treeview(list_row, columns=columns,
                                         show="headings", height=3)
        self.process_tree.heading("pid", text="进程ID")
        self.process_tree.heading("arrival", text="到达时间")
        self.process_tree.heading("service", text="服务时间")
        self.process_tree.column("pid", width=260, anchor="center")
        self.process_tree.column("arrival", width=190, anchor="center")
        self.process_tree.column("service", width=190, anchor="center")
        self.process_tree.pack(side="left", fill="x", expand=True)

        tk.Button(list_row, text="删除选中进程", width=13,
                  command=self.delete_process).pack(side="left", padx=(6, 0), anchor="n")

    def _build_algorithm_area(self):
        """算法选择区：下拉框选择调度算法，选中 RR 时才显示时间片输入框。"""
        frame = tk.LabelFrame(self.root, text="算法选择")
        frame.pack(side="top", fill="x", padx=10, pady=2)

        tk.Label(frame, text="调度算法：").grid(row=0, column=0, padx=(10, 4), pady=6)
        self.algo_combo = ttk.Combobox(
            frame,
            values=[item[0] for item in ALGORITHMS],
            textvariable=self.algorithm,
            state="readonly",           # 只能从列表里选，避免输入非法算法名
            width=26,
        )
        self.algo_combo.grid(row=0, column=1, padx=4, pady=6)
        self.algo_combo.current(0)      # 默认选中第一项 FCFS
        self.algo_combo.bind("<<ComboboxSelected>>", self._on_algorithm_change)

        # 时间片输入框：仅 RR 选中时显示（初始隐藏，因为默认 FCFS）
        self.quantum_label = tk.Label(frame, text="时间片：")
        self.quantum_label.grid(row=0, column=2, padx=(16, 2))
        self.quantum_entry = tk.Entry(frame, width=6, textvariable=self.quantum_var)
        self.quantum_entry.grid(row=0, column=3, padx=2)
        self.quantum_label.grid_remove()
        self.quantum_entry.grid_remove()

    def _build_control_area(self):
        """控制区：开始模拟 / 重置两个按钮。"""
        frame = tk.Frame(self.root)
        frame.pack(side="top", fill="x", padx=10, pady=2)
        tk.Button(frame, text="开始模拟", width=14, font=("Microsoft YaHei", 10, "bold"),
                  command=self.start_simulation).pack(side="left", padx=6, pady=2)
        tk.Button(frame, text="重置", width=14,
                  command=self.reset).pack(side="left", padx=6, pady=2)

    def _build_canvas_area(self):
        """可视化区（中部）：用 Canvas 绘制 CPU 甘特图。"""
        frame = tk.LabelFrame(self.root, text="可视化区：CPU 甘特图")
        frame.pack(side="top", fill="x", padx=10, pady=2)
        self.canvas = tk.Canvas(frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
                                bg="white", highlightthickness=1,
                                highlightbackground="#aaaaaa")
        self.canvas.pack(padx=6, pady=6)

    def _build_result_area(self):
        """结果区（底部）：各进程等待时间、周转时间及平均值。"""
        frame = tk.LabelFrame(self.root, text="结果区：调度指标")
        frame.pack(side="top", fill="both", expand=True, padx=10, pady=(2, 8))

        columns = ("pid", "arrival", "service", "finish", "waiting", "turnaround")
        self.result_tree = ttk.Treeview(frame, columns=columns,
                                        show="headings", height=4)
        for col, text, w in (
                ("pid", "进程ID", 130), ("arrival", "到达时间", 120),
                ("service", "服务时间", 120), ("finish", "完成时间", 120),
                ("waiting", "等待时间", 120), ("turnaround", "周转时间", 120)):
            self.result_tree.heading(col, text=text)
            self.result_tree.column(col, width=w, anchor="center")
        self.result_tree.pack(side="top", fill="both", expand=True, padx=6, pady=(6, 2))

        self.avg_label = tk.Label(frame, text="平均等待时间：--    平均周转时间：--",
                                  font=("Microsoft YaHei", 10, "bold"), fg="#1f4e79")
        self.avg_label.pack(side="bottom", pady=(0, 6))

    def _center_window(self):
        """把 900x650 的窗口放到屏幕中央。"""
        self.root.update_idletasks()
        w, h = 1100, 800
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def add_process(self):
        """读取输入框并校验，把新进程加入列表并实时显示在表格中。

        校验顺序（全部通过才允许添加，任何一项失败都会用
        messagebox.showerror 弹出红色错误提示框并立即拦截）：
        1. 进程ID不能为空（不再自动编号）；
        2. 到达时间/服务时间不能留空，且必须是有效数字；
        3. 到达时间/服务时间不能为负数，服务时间还必须大于 0；
        4. 进程ID不能与已添加的进程重复。
        """
        # ---- 第 1 步：读取三个输入框的内容，并去掉首尾空白字符 ----
        pid = self.pid_entry.get().strip()
        arrival_text = self.arrival_entry.get().strip()
        service_text = self.service_entry.get().strip()

        # ---- 第 2 步：进程ID 为空 → 红色错误弹窗并拦截 ----
        if not pid:
            messagebox.showerror("输入错误", "进程ID不能为空，请输入进程标识！")
            return

        # ---- 第 3 步：到达时间/服务时间 留空或含非数字字符 → 弹窗拦截 ----
        # float() 无法解析空字符串、纯字母（如 "abc"）等非法内容，
        # 会抛出 ValueError，这里统一捕获并提示用户输入有效数字。
        try:
            arrival = float(arrival_text)
            service = float(service_text)
        except ValueError:
            messagebox.showerror("输入错误",
                                 "请输入有效的数字！到达时间和服务时间必须是数字！")
            return

        # ---- 第 4 步：拦截 "nan"、"inf" 这类特殊输入 ----
        # 它们能通过 float() 转换不报错，但不是合法的调度时间，
        # 会让后续排序/绘图出现异常，因此用 math.isfinite 提前挡掉。
        if not (math.isfinite(arrival) and math.isfinite(service)):
            messagebox.showerror("输入错误", "请输入有效的数字！")
            return

        # ---- 第 5 步：负数拦截（时间轴从 0 开始，负时间没有物理意义） ----
        if arrival < 0:
            messagebox.showerror("输入错误", "到达时间不能为负数，请输入有效的数字！")
            return
        if service < 0:
            messagebox.showerror("输入错误", "服务时间不能为负数，请输入有效的数字！")
            return

        # ---- 第 6 步：服务时间为 0 的进程没有工作量，同样拦截 ----
        if service == 0:
            messagebox.showerror("输入错误", "服务时间必须大于 0！")
            return

        # ---- 第 7 步：进程ID 查重，防止同名进程干扰调度统计 ----
        if any(p.pid == pid for p in self.processes):
            messagebox.showerror("输入错误", f"进程 {pid} 已存在，请换一个标识！")
            return

        # ---- 全部校验通过：创建进程对象并加入内部列表 ----
        proc = Process(pid=pid, arrival=arrival, service=service, index=self._seq)
        self._seq += 1
        self.processes.append(proc)

        # 给新 pid 分配一个固定颜色（同名进程始终保持同色，便于对照）
        if pid not in self.pid_color:
            self.pid_color[pid] = COLORS[self._color_i % len(COLORS)]
            self._color_i += 1

        # 把新进程插入"已添加进程"表格，实现列表实时刷新
        iid = str(proc.index)
        self.proc_by_iid[iid] = proc
        self.process_tree.insert("", "end", iid=iid,
                                 values=(pid, f"{arrival:g}", f"{service:g}"))

        # ---- 添加成功后自动清空三个输入框，方便连续录入下一个进程 ----
        self.pid_entry.delete(0, "end")
        self.arrival_entry.delete(0, "end")
        self.service_entry.delete(0, "end")
        self.pid_entry.focus_set()   # 焦点自动回到 PID 输入框

        # 进程列表发生变化，旧的模拟结果作废，清空甘特图与结果表
        self._clear_outputs()

    def delete_process(self):
        """删除列表中选中的进程（支持多选，逐行准确删除）。"""
        selection = self.process_tree.selection()
        # 未选中任何行 → 弹窗提示，不执行任何删除操作
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的进程！")
            return
        # 遍历所有选中的行号：同步移除 Treeview 中的行、
        # 行号映射表（proc_by_iid）以及内部进程列表，保证三处数据一致
        for iid in selection:
            proc = self.proc_by_iid.pop(iid, None)
            if proc is not None and proc in self.processes:
                self.processes.remove(proc)
            self.process_tree.delete(iid)
        # 进程列表变化后，旧的模拟结果作废
        self._clear_outputs()

    def _current_algorithm(self):
        """返回 (算法 key, 是否需要时间片)，由下拉框当前显示文字映射得到。"""
        display = self.algorithm.get()
        for label, key, need_quantum in ALGORITHMS:
            if label == display:
                return key, need_quantum
        return "FCFS", False

    def _on_algorithm_change(self, event=None):
        """切换算法：只有 RR 需要时间片，选中 RR 时才显示时间片输入框。"""
        _, need_quantum = self._current_algorithm()
        if need_quantum:
            self.quantum_label.grid()
            self.quantum_entry.grid()
        else:
            self.quantum_label.grid_remove()
            self.quantum_entry.grid_remove()

    def start_simulation(self):
        """按所选算法运行调度模拟，并刷新甘特图与结果表。"""
        if not self.processes:
            messagebox.showwarning("提示", "请先添加至少一个进程！")
            return

        algo, _ = self._current_algorithm()
        if algo == "FCFS":
            result = scheduler.fcfs(self.processes)
        elif algo == "SJF":
            result = scheduler.sjf(self.processes)
        else:   # RR：校验时间片
            try:
                quantum = float(self.quantum_var.get().strip())
            except ValueError:
                messagebox.showerror("输入错误", "时间片必须是数字！")
                return
            if quantum <= 0:
                messagebox.showerror("输入错误", "时间片必须是正数！")
                return
            result = scheduler.rr(self.processes, quantum)

        self.sim_result = result
        self.draw_gantt(result)
        self.fill_results(result)

    def reset(self):
        """重置：清空进程列表、甘特图与结果，时间片恢复默认值 2。"""
        self.processes.clear()
        self.proc_by_iid.clear()
        self._seq = 0
        for iid in self.process_tree.get_children():
            self.process_tree.delete(iid)
        self.pid_entry.delete(0, "end")
        self.arrival_entry.delete(0, "end")
        self.service_entry.delete(0, "end")
        self.quantum_var.set("2")
        self.algo_combo.current(0)     # 算法恢复默认 FCFS
        self._on_algorithm_change()    # 同步隐藏时间片输入框
        self._clear_outputs()

    def _clear_outputs(self):
        """清空甘特图与结果表（进程列表变化后调用，避免新旧数据不一致）。"""
        self.canvas.delete("all")
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)
        self.avg_label.config(text="平均等待时间：--    平均周转时间：--")
        self.sim_result = None

    # ------------------------------------------------------------------
    # 甘特图绘制与结果展示
    # ------------------------------------------------------------------

    def draw_gantt(self, result):
        """在 Canvas 上绘制甘特图。

        坐标换算：plot 宽度 / 总时长 = 每单位时间的像素数；
        空闲时段画浅灰色矩形并标"空闲"，进程时段画各自颜色矩形；
        矩形上方标注 PID，下方画带刻度数字的时间轴。
        """
        canvas = self.canvas
        canvas.delete("all")
        total = result.total_time
        if total <= 0:
            return

        plot_w = CANVAS_WIDTH - LEFT_PAD - RIGHT_PAD
        scale = plot_w / total

        def x_of(t):
            """时间 t -> 画布 x 坐标。"""
            return LEFT_PAD + t * scale

        # 1) 先画时间段矩形（含空闲段），时间轴最后画在最上层
        for seg in result.segments:
            x1, x2 = x_of(seg.start), x_of(seg.end)
            if seg.pid is None:
                # 空闲段：浅灰色矩形，中间标注"空闲"
                canvas.create_rectangle(x1, BAR_TOP, x2, BAR_TOP + BAR_HEIGHT,
                                        fill=IDLE_COLOR, outline="#9a9a9a")
                if x2 - x1 >= 30:
                    canvas.create_text((x1 + x2) / 2, BAR_TOP + BAR_HEIGHT / 2,
                                       text="空闲", fill="#777777",
                                       font=("Microsoft YaHei", 9))
            else:
                # 进程段：该进程的专属颜色
                color = self.pid_color.get(seg.pid, COLORS[0])
                canvas.create_rectangle(x1, BAR_TOP, x2, BAR_TOP + BAR_HEIGHT,
                                        fill=color, outline="#333333")
                # 矩形上方标注 PID（矩形太窄时省略，避免文字重叠）
                if x2 - x1 >= 26:
                    canvas.create_text((x1 + x2) / 2, BAR_TOP - 12,
                                       text=seg.pid, fill="#222222",
                                       font=("Microsoft YaHei", 10, "bold"))

        # 2) 画时间轴与刻度数字
        canvas.create_line(LEFT_PAD, AXIS_Y, LEFT_PAD + plot_w, AXIS_Y,
                           fill="black", width=2)
        step = self._tick_step(total)
        t = 0.0
        while True:
            tx = x_of(t)
            canvas.create_line(tx, AXIS_Y, tx, AXIS_Y + 6, fill="black")
            label = str(int(t)) if abs(t - round(t)) < 1e-9 else f"{t:g}"
            canvas.create_text(tx, AXIS_Y + 18, text=label,
                               font=("Microsoft YaHei", 8), fill="black")
            if t >= total - 1e-9:
                break
            t = min(t + step, total)   # 保证最后一个刻度正好落在总时长上

    @staticmethod
    def _tick_step(total):
        """根据总时长选择刻度间隔，避免刻度数字挤在一起。"""
        if total <= 12:
            return 1
        if total <= 30:
            return 2
        if total <= 80:
            return 5
        return 10

    def fill_results(self, result):
        """把模拟结果填入结果表，并更新平均值标签。

        Bug 修复：每次填充前先清空结果表中已有的全部行，
        保证连续多次点击"开始模拟"时，底部结果区不会不断追加旧数据。
        """
        # ---- 先清空结果表旧行，再插入本次模拟的新数据 ----
        for iid in self.result_tree.get_children():
            self.result_tree.delete(iid)

        for r in result.results:
            self.result_tree.insert("", "end", values=(
                r.pid,
                f"{r.arrival:g}",
                f"{r.service:g}",
                f"{r.finish:.2f}",
                f"{r.waiting:.2f}",
                f"{r.turnaround:.2f}"))
        self.avg_label.config(
            text=(f"平均等待时间：{result.avg_waiting:.2f}"
                  f"    平均周转时间：{result.avg_turnaround:.2f}"))

    # ------------------------------------------------------------------

    def run(self):
        """进入 Tk 主循环。"""
        self.root.mainloop()
