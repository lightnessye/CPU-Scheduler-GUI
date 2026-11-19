"""ui.py
Tkinter 图形界面模块：进程输入区、算法选择区、甘特可视化区、调度结果区。

界面本身不实现调度算法，全部调度计算交给 scheduler.py，
本模块只负责：收集输入 -> 调用算法 -> 在 Canvas 上绘图 -> 展示结果。

【本次改版要点】
1. 彻底放弃原生复古灰外观：全面改用 ttk 控件库，并配置一套浅色现代配色
   （窗口背景 #F5F7FA、卡片纯白 #FFFFFF、分割线 #E4E7ED）。
2. 布局：窗口放大到 1100x750；上半部分用 ttk.LabelFrame 卡片分别包裹
   “进程输入区”与“算法选择区”，正文统一使用微软雅黑（Microsoft YaHei），
   标题字号加大。
3. 按钮：使用 ttk.Button 的自定义样式区分主次（开始模拟=蓝 #409EFF，
   添加进程=绿 #67C23A，重置=灰 #909399，删除=红 #F56C6C），
   通过 style.map 实现鼠标悬停（active 状态）变色。
4. 甘特图：仍为纯 Canvas 手工绘制，但每条时间片按 PID 分配不同的莫兰迪
   柔和色，色块内部居中显示进程 ID，色块上方标注该时间片的时间区间，
   下方绘制带数字刻度的时间轴；CPU 空闲段保持灰色并叠加斜线填充。
5. 结果区：ttk.Treeview，表头加粗、所有列内容居中对齐。
6. 高分屏适配：所有像素级尺寸都通过 px() 按系统 DPI 换算，
   窗口在高 DPI 屏幕上等比放大而不会挤压变形（字体由 Tk 自动换算）。

【重要约束】
scheduler.py 中的纯算法逻辑完全未作任何改动，本模块仅负责界面渲染。
"""
import math
import math   # 用于 math.isfinite：拦截 "nan"、"inf" 这类能转 float 但非法的输入

import tkinter as tk
from tkinter import ttk, messagebox

import scheduler
from scheduler import Process

# ---------------------------------------------------------------------------
# DPI 缩放：以 96 DPI（100% 缩放）为设计基准
# ---------------------------------------------------------------------------

SCALE = 1.0     # 当前系统的实际缩放系数，SchedulerApp 初始化时按 DPI 计算


def px(*values):
    """把设计稿中的像素值换算为当前系统 DPI 下的实际像素。

    用法：
        px(18)            -> 单个像素值
        px(14, 8, 14, 10) -> 四元组（直接用于 ttk 的 padding / pack 的 padx）
    """
    if len(values) == 1 and isinstance(values[0], (tuple, list)):
        values = tuple(values[0])
    if len(values) == 1:
        return int(round(values[0] * SCALE))
    return tuple(int(round(v * SCALE)) for v in values)


# ---------------------------------------------------------------------------
# 配色方案（浅色现代风）
# ---------------------------------------------------------------------------

C = {
    "bg":          "#F5F7FA",  # 窗口背景（浅灰蓝）
    "card":        "#FFFFFF",  # 卡片纯白
    "card_soft":   "#FAFBFC",  # 卡片内的浅色表格底
    "border":      "#E4E7ED",  # 卡片描边 / 分割线
    "text":        "#303133",  # 主文字
    "text_sub":    "#909399",  # 次要文字
    "text_light":  "#C0C4CC",  # 占位/禁用文字
    "primary":     "#409EFF",  # 主色（开始模拟按钮）
    "primary_h":   "#66B1FF",  # 主色悬停
    "primary_p":   "#3A8EE6",  # 主色按下
    "success":     "#67C23A",  # 成功色（添加进程按钮）
    "success_h":   "#85CE61",
    "success_p":   "#5CAB2A",
    "info":        "#909399",  # 中性色（重置按钮）
    "info_h":      "#A6A9AD",
    "info_p":      "#787B7F",
    "danger":      "#F56C6C",  # 危险色（删除按钮）
    "danger_h":    "#F78989",
    "danger_p":    "#E45656",
    "head_bg":     "#EDF1F7",  # 表头底色
    "head_bg_h":   "#E1E8F3",  # 表头悬停
    "row_alt":     "#F4F7FB",  # 表格交替行（略深，便于逐行阅读）
    "select":      "#EAF3FF",  # 选中行
    "idle":        "#EDEFF3",  # 空闲时段底色
    "idle_line":   "#C9CFDA",  # 空闲时段斜线
    "axis":        "#C0C4CC",  # 时间轴
    "grid":        "#F2F5FA",  # 纵向网格线
}

# 莫兰迪柔和色板：按 PID 依次分配，让甘特图条带不再单调
MORANDI = [
    "#8FA9BF",  # 雾霭蓝
    "#C4A484",  # 焦糖棕
    "#9DB29B",  # 鼠尾草绿
    "#C09090",  # 陈玫瑰
    "#A79AB4",  # 淡紫
    "#86B0AC",  # 青瓷绿
    "#C3B187",  # 燕麦黄
    "#C69E97",  # 陶土粉
    "#9C8F7E",  # 岩灰褐
    "#B0A79B",  # 暖灰
]

# 字体候选：优先微软雅黑，取不到时由 Tk 自动回退
FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", "PingFang SC")

# 算法下拉框选项：(显示文字, 传给 scheduler 的算法 key, 是否需要时间片)
ALGORITHMS = (
    ("FCFS（先来先服务）", "FCFS", False),
    ("SJF（短作业优先·非抢占）", "SJF", False),
    ("RR（时间片轮转）", "RR", True),
)

# 每种算法的简介，切换下拉框时同步刷新（纯展示文字）
ALGO_DESC = {
    "FCFS": "先来先服务（FCFS）：进程按到达时间先后进入就绪队列，队首进程一旦开始执行"
            "便一直运行到结束，中途不会被抢占。",
    "SJF": "短作业优先（SJF·非抢占）：每次都从就绪队列中挑选服务时间最短的进程执行，"
           "平均等待时间最优，但长进程可能被长期推迟。",
    "RR": "时间片轮转（RR）：就绪队列按 FIFO 轮流调度，每个进程最多连续执行一个时间片，"
          "时间片用完仍未完成则排到队尾，公平性良好。",
}

# 甘特图下方的说明文字
GANTT_HINT = ("说明：斜线灰色区域表示 CPU 空闲时段；色块内文字为进程 ID；"
              "色块上方为该时间片的起止时刻；下方为时间轴刻度。")

# 窗口尺寸（设计稿基准 96 DPI，实际像素由 px() 按 DPI 换算）
WIN_W, WIN_H = 1100, 750

# 甘特图画布的高度（宽度随窗口自适应）
CANVAS_HEIGHT = 148

# 甘特图布局常量（设计稿像素，实际使用时统一走 px()）
LEFT_PAD = 46        # 画布左侧留白（时间轴从 x=46 开始）
RIGHT_PAD = 26       # 画布右侧留白
BAR_HEIGHT = 44      # 进程条高度
TICK_STEP_RULES = ((6, 1), (16, 2), (36, 5), (80, 10), (1e9, 20))  # 总时长->刻度间隔


# ---------------------------------------------------------------------------
# 颜色与几何小工具（纯外观辅助，不参与任何调度逻辑）
# ---------------------------------------------------------------------------

def _hex_to_rgb(color):
    """#RRGGBB -> (r, g, b)"""
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _blend(c1, c2, t):
    """在两个颜色之间线性插值，t 取 0~1。"""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    t = max(0.0, min(1.0, t))
    return "#%02X%02X%02X" % (
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def _shade(color, amount):
    """amount > 0 提亮（向白色靠拢），amount < 0 压暗（向黑色靠拢）。"""
    if amount >= 0:
        return _blend(color, "#FFFFFF", amount)
    return _blend(color, "#000000", -amount)


def _text_on(color):
    """根据背景色亮度选择前景文字颜色，保证色块上的文字始终清晰可读。"""
    r, g, b = _hex_to_rgb(color)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#FFFFFF" if lum < 0.68 else "#3A3A3A"


def _fill_round_rect(canvas, x0, y0, x1, y1, r, fill, outline=None, width=1):
    """在画布上填充一个圆角矩形（可选描边）。"""
    r = max(0.0, min(float(r), (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline="")
    canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline="")
    for ax0, ay0, start in ((x0, y0, 90), (x1 - 2 * r, y0, 0),
                            (x0, y1 - 2 * r, 180), (x1 - 2 * r, y1 - 2 * r, 270)):
        canvas.create_arc(ax0, ay0, ax0 + 2 * r, ay0 + 2 * r,
                          start=start, extent=90, style="pieslice",
                          fill=fill, outline="")
    if outline:   # 需要描边时再补一圈轮廓
        for ax0, ay0, start in ((x0, y0, 90), (x1 - 2 * r, y0, 0),
                                (x0, y1 - 2 * r, 180), (x1 - 2 * r, y1 - 2 * r, 270)):
            canvas.create_arc(ax0, ay0, ax0 + 2 * r, ay0 + 2 * r,
                              start=start, extent=90, style="arc",
                              outline=outline, width=width)
        canvas.create_line(x0 + r, y0, x1 - r, y0, fill=outline, width=width)
        canvas.create_line(x0 + r, y1, x1 - r, y1, fill=outline, width=width)
        canvas.create_line(x0, y0 + r, x0, y1 - r, fill=outline, width=width)
        canvas.create_line(x1, y0 + r, x1, y1 - r, fill=outline, width=width)


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

class SchedulerApp:
    """CPU 进程调度算法演示程序主窗口。"""

    def __init__(self):
        global SCALE

        self.root = tk.Tk()
        self.root.title("CPU 进程调度算法演示 · FCFS / SJF / RR")
        self.root.configure(bg=C["bg"])

        # 高分屏适配：按系统实际 DPI 计算缩放系数，
        # 之后所有像素尺寸都经过 px() 换算，保证界面等比不变形
        SCALE = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.root.minsize(px(WIN_W), px(WIN_H))

        # ---- 字体：统一使用微软雅黑，字号按层级适当加大 ----------------
        # 字体单位是“磅”，由 Tk 按系统 DPI 自动换算成像素，无需手动缩放
        fam = self._detect_family()
        self.F = {
            "h1":         (fam, 16, "bold"),   # 页面主标题
            "h2":         (fam, 12, "bold"),   # 卡片标题
            "label":      (fam, 10),           # 表单标签
            "label_bold": (fam, 10, "bold"),
            "body":       (fam, 10),           # 正文 / 表格内容
            "small":      (fam, 9),            # 辅助说明
            "tiny":       (fam, 9),            # 坐标轴刻度
            "btn":        (fam, 10, "bold"),   # 按钮
            "bar":        (fam, 10, "bold"),   # 甘特图条上的 PID
            "bar_small":  (fam, 8, "bold"),    # 窄条上的 PID
        }

        self._setup_style()   # 仅配置外观

        # ---- 程序内部状态（原有逻辑，完全不变）----
        self.processes = []        # 已添加的进程（Process 对象，保持添加顺序）
        self.proc_by_iid = {}      # 列表行号 iid -> Process 对象
        self._seq = 0              # 自增序号，保证行号和排序稳定键唯一
        self.pid_color = {}        # pid -> 甘特图颜色
        self._color_i = 0          # 下一个使用的调色板下标
        self.algorithm = tk.StringVar(value=ALGORITHMS[0][0])  # 下拉框当前显示的文字
        self.quantum_var = tk.StringVar(value="2")     # RR 时间片（默认 2）
        self.sim_result = None     # 最近一次模拟的结果

        # ---- 四个功能分区 ----
        self._build_header()
        self._build_top_row()      # 上半部分：输入区 + 算法区（左右并排）
        self._build_canvas_area()
        self._build_result_area()
        self._on_algorithm_change()  # 初始化算法简介文字
        self._center_window()

    # ------------------------------------------------------------------
    # 外观样式（不参与任何调度逻辑）
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_family():
        """检测可用字体，取不到时返回默认字体名（交给 Tk 回退）。"""
        try:
            import tkinter.font as tkfont
            available = {f.lower() for f in tkfont.families()}
            for cand in FONT_CANDIDATES:
                if cand.lower() in available:
                    return cand
        except Exception:
            pass
        return FONT_CANDIDATES[0]

    def _setup_style(self):
        """统一配置浅色现代风格的 ttk 样式。"""
        style = ttk.Style(self.root)
        try:
            # clam 主题允许自定义配色，Windows 默认主题会忽略大部分颜色设置
            style.theme_use("clam")
        except tk.TclError:
            pass

        # ---- 卡片容器（ttk.LabelFrame 作为“卡片”，带浅色描边）----
        style.configure("Card.TLabelframe",
                        background=C["card"],
                        bordercolor=C["border"],
                        lightcolor=C["border"],
                        darkcolor=C["border"],
                        borderwidth=px(1),
                        relief="solid")
        style.configure("Card.TLabelframe.Label",
                        background=C["card"],
                        foreground=C["text"],
                        font=self.F["h2"])

        # ---- 输入框 ----
        style.configure("Modern.TEntry",
                        fieldbackground=C["card"],
                        background=C["card"],
                        foreground=C["text"],
                        bordercolor=C["border"],
                        lightcolor=C["border"],
                        darkcolor=C["border"],
                        borderwidth=px(1),
                        relief="solid",
                        padding=px(8, 7),
                        insertcolor=C["text"],
                        font=self.F["body"])
        # 聚焦时边框高亮为主色，形成清晰的输入反馈
        style.map("Modern.TEntry",
                  bordercolor=[("focus", C["primary"])],
                  lightcolor=[("focus", C["primary"])],
                  darkcolor=[("focus", C["primary"])])

        # ---- 下拉框 ----
        style.configure("Modern.TCombobox",
                        fieldbackground=C["card"],
                        background=C["card"],
                        foreground=C["text"],
                        bordercolor=C["border"],
                        lightcolor=C["border"],
                        darkcolor=C["border"],
                        arrowcolor=C["text_sub"],
                        borderwidth=px(1),
                        relief="solid",
                        padding=px(8, 6),
                        font=self.F["body"])
        style.map("Modern.TCombobox",
                  bordercolor=[("focus", C["primary"])],
                  lightcolor=[("focus", C["primary"])],
                  darkcolor=[("focus", C["primary"])],
                  arrowcolor=[("active", C["primary"])])
        # 下拉列表（弹出层属于 Toplevel，需要用 option_add 设置）
        self.root.option_add("*TCombobox*Listbox.background", C["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", C["primary"])
        self.root.option_add("*TCombobox*Listbox.font", self.F["body"])

        # ---- 按钮：按语义区分颜色，并配置悬停/按下变色 ----
        # active 状态即鼠标悬停，pressed 为按下
        for name, base, hover, pressed in (
                ("Primary", C["primary"], C["primary_h"], C["primary_p"]),
                ("Success", C["success"], C["success_h"], C["success_p"]),
                ("Info",    C["info"],    C["info_h"],    C["info_p"]),
                ("Danger",  C["danger"],  C["danger_h"],  C["danger_p"])):
            style.configure(f"{name}.TButton",
                            background=base,
                            foreground="#FFFFFF",
                            bordercolor=base,
                            lightcolor=base,
                            darkcolor=base,
                            focuscolor=base,       # 聚焦时不再画虚线框
                            focusthickness=0,
                            borderwidth=0,
                            relief="flat",
                            padding=px(16, 8),
                            font=self.F["btn"])
            style.map(f"{name}.TButton",
                      background=[("disabled", "#C0C4CC"),
                                  ("pressed", pressed),
                                  ("active", hover)],
                      foreground=[("disabled", "#F0F2F5")])

        # ---- 表格：表头加粗、内容居中 ----
        style.configure("Modern.Treeview",
                        background=C["card"],
                        fieldbackground=C["card"],
                        foreground=C["text"],
                        borderwidth=0,
                        relief="flat",
                        rowheight=px(28),
                        font=self.F["body"])
        style.configure("Modern.Treeview.Heading",
                        background=C["head_bg"],
                        foreground="#4A5568",
                        font=self.F["label_bold"],   # 表头加粗
                        relief="flat",
                        borderwidth=0,
                        padding=px(8, 8))
        style.map("Modern.Treeview.Heading",
                  background=[("active", C["head_bg_h"])])
        style.map("Modern.Treeview",
                  background=[("selected", C["select"])],
                  foreground=[("selected", C["primary"])])

        # ---- 滚动条（细窄现代风）----
        style.configure("Modern.Vertical.TScrollbar",
                        background=C["border"],
                        troughcolor=C["card_soft"],
                        bordercolor=C["card_soft"],
                        arrowcolor=C["text_sub"],
                        borderwidth=0,
                        relief="flat",
                        width=px(12))
        style.map("Modern.Vertical.TScrollbar",
                  background=[("active", C["text_light"])])

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------

    def _build_header(self):
        """顶部标题栏：主标题 + 副标题说明。"""
        header = tk.Frame(self.root, bg=C["bg"])
        header.pack(side="top", fill="x", padx=px(22), pady=px(10, 2))

        tk.Label(header, text="CPU 进程调度算法演示", bg=C["bg"],
                 fg=C["text"], font=self.F["h1"]).pack(side="left")
        tk.Label(header, text="FCFS · SJF · RR   |   输入进程 → 选择算法 → 运行模拟",
                 bg=C["bg"], fg=C["text_sub"], font=self.F["small"]
                 ).pack(side="left", padx=px(16, 0), pady=px(6, 0))

    def _build_top_row(self):
        """上半部分容器：把“进程输入区”和“算法选择区”并排放在一行，
        节省纵向空间，让甘特图与结果表有足够的显示高度。"""
        top = tk.Frame(self.root, bg=C["bg"])
        top.pack(side="top", fill="x", padx=px(18), pady=px(0, 8))
        # 左侧输入区占 3 份，右侧算法区占 2 份
        top.grid_columnconfigure(0, weight=3, uniform="toprow")
        top.grid_columnconfigure(1, weight=2, uniform="toprow")
        top.grid_rowconfigure(0, weight=1)

        self._build_input_area(top)
        self._build_algorithm_area(top)

    def _build_input_area(self, parent):
        """进程输入区卡片：三个输入框 + 添加按钮 + 已添加进程列表。"""
        card = ttk.LabelFrame(parent, text="  进程输入区  ",
                              style="Card.TLabelframe", padding=px(14, 6, 14, 8))
        card.grid(row=0, column=0, sticky="nsew", padx=px(0, 8))
        frame = tk.Frame(card, bg=C["card"])
        frame.pack(fill="both", expand=True)

        # ---- 第一行：PID / 到达时间 / 服务时间 + 添加进程按钮 ----
        tk.Label(frame, text="进程ID", bg=C["card"], fg=C["text"],
                 font=self.F["label"]).grid(row=0, column=0, sticky="w",
                                            padx=px(0, 6), pady=px(0, 8))
        self.pid_entry = ttk.Entry(frame, width=8, style="Modern.TEntry")
        self.pid_entry.grid(row=0, column=1, padx=px(0, 12), pady=px(0, 8))

        tk.Label(frame, text="到达时间", bg=C["card"], fg=C["text"],
                 font=self.F["label"]).grid(row=0, column=2, sticky="w",
                                            padx=px(0, 6), pady=px(0, 8))
        self.arrival_entry = ttk.Entry(frame, width=5, style="Modern.TEntry")
        self.arrival_entry.grid(row=0, column=3, padx=px(0, 12), pady=px(0, 8))

        tk.Label(frame, text="服务时间", bg=C["card"], fg=C["text"],
                 font=self.F["label"]).grid(row=0, column=4, sticky="w",
                                            padx=px(0, 6), pady=px(0, 8))
        self.service_entry = ttk.Entry(frame, width=5, style="Modern.TEntry")
        self.service_entry.grid(row=0, column=5, padx=px(0, 14), pady=px(0, 8))

        # 添加进程按钮（绿色系）
        ttk.Button(frame, text="添加进程", command=self.add_process,
                   style="Success.TButton").grid(row=0, column=6, sticky="e",
                                                 pady=px(0, 8))

        # 在时间输入框按回车也能直接添加，方便连续录入（逻辑不变）
        self.pid_entry.bind("<Return>", lambda e: self.arrival_entry.focus_set())
        self.arrival_entry.bind("<Return>", lambda e: self.service_entry.focus_set())
        self.service_entry.bind("<Return>", lambda e: self.add_process())

        # ---- 第二行：已添加进程表格 + 删除按钮 ----
        list_row = tk.Frame(frame, bg=C["card"])
        list_row.grid(row=1, column=0, columnspan=7, sticky="ew")
        frame.columnconfigure(0, weight=1)

        columns = ("pid", "arrival", "service")
        self.process_tree = ttk.Treeview(list_row, columns=columns,
                                         show="headings", height=4,
                                         style="Modern.Treeview")
        self.process_tree.tag_configure("evenrow", background=C["card"])
        self.process_tree.tag_configure("oddrow", background=C["row_alt"])
        self.process_tree.heading("pid", text="进程ID", anchor="center")
        self.process_tree.heading("arrival", text="到达时间", anchor="center")
        self.process_tree.heading("service", text="服务时间", anchor="center")
        self.process_tree.column("pid", width=px(150), anchor="center", stretch=True)
        self.process_tree.column("arrival", width=px(100), anchor="center", stretch=True)
        self.process_tree.column("service", width=px(100), anchor="center", stretch=True)
        self.process_tree.pack(side="left", fill="both", expand=True)

        # 删除选中进程按钮（红色系），放在表格右侧
        ttk.Button(list_row, text="删除选中", command=self.delete_process,
                   style="Danger.TButton").pack(side="right", anchor="n",
                                                padx=px(10, 0), pady=px(0, 2))

    def _build_algorithm_area(self, parent):
        """算法选择区卡片：算法下拉框 + RR 时间片 + 开始模拟/重置按钮 + 算法简介。"""
        card = ttk.LabelFrame(parent, text="  算法选择与运行控制  ",
                              style="Card.TLabelframe", padding=px(14, 6, 14, 8))
        card.grid(row=0, column=1, sticky="nsew")
        frame = tk.Frame(card, bg=C["card"])
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        # ---- 调度算法下拉框 ----
        tk.Label(frame, text="调度算法", bg=C["card"], fg=C["text"],
                 font=self.F["label"]).grid(row=0, column=0, sticky="w",
                                            padx=px(0, 8), pady=px(0, 8))
        self.algo_combo = ttk.Combobox(
            frame,
            values=[item[0] for item in ALGORITHMS],
            textvariable=self.algorithm,
            state="readonly",           # 只能从列表里选，避免输入非法算法名
            width=22,
            style="Modern.TCombobox",
        )
        self.algo_combo.grid(row=0, column=1, sticky="w", pady=px(0, 8))
        self.algo_combo.current(0)      # 默认选中第一项 FCFS
        self.algo_combo.bind("<<ComboboxSelected>>", self._on_algorithm_change)

        # 时间片输入框：仅 RR 选中时显示（初始隐藏，因为默认 FCFS）
        self.quantum_label = tk.Label(frame, text="时间片", bg=C["card"],
                                      fg=C["text"], font=self.F["label"])
        self.quantum_label.grid(row=1, column=0, sticky="w", padx=px(0, 8),
                                 pady=px(0, 8))
        self.quantum_entry = ttk.Entry(frame, width=7, textvariable=self.quantum_var,
                                       style="Modern.TEntry")
        self.quantum_entry.grid(row=1, column=1, sticky="w", pady=px(0, 8))
        self.quantum_label.grid_remove()
        self.quantum_entry.grid_remove()

        # ---- 运行控制按钮 ----
        btn_box = tk.Frame(frame, bg=C["card"])
        btn_box.grid(row=2, column=0, columnspan=2, sticky="w", pady=px(2, 10))
        # 开始模拟按钮（主色蓝，最醒目）
        ttk.Button(btn_box, text="开始模拟", command=self.start_simulation,
                   style="Primary.TButton", padding=px(24, 9)
                   ).pack(side="left", padx=px(0, 10))
        # 重置按钮（中性灰）
        ttk.Button(btn_box, text="重置", command=self.reset,
                   style="Info.TButton").pack(side="left")

        # ---- 当前算法简介（纯说明文字，宽度自适应换行）----
        self.algo_desc = tk.Label(
            frame, text="", bg=C["card"], fg=C["text_sub"],
            font=self.F["small"], justify="left", anchor="w")
        self.algo_desc.grid(row=3, column=0, columnspan=2, sticky="ew")
        # 依据卡片实际宽度动态设置折行宽度，避免文字溢出卡片
        self.algo_desc.bind("<Configure>",
                             lambda e: self._fit_wrap(self.algo_desc))

    @staticmethod
    def _fit_wrap(label):
        """让文字标签按当前宽度自动折行（宽度变化时触发）。"""
        width = label.winfo_width()
        if width > 60:
            target = max(200, width - px(8))
            if abs(int(label.cget("wraplength")) - target) > 4:
                label.config(wraplength=target)

    def _build_canvas_area(self):
        """甘特可视化区卡片：Canvas 绘制 CPU 甘特图。"""
        card = ttk.LabelFrame(self.root, text="  甘特可视化区  ",
                              style="Card.TLabelframe", padding=px(14, 6, 14, 6))
        card.pack(side="top", fill="x", padx=px(18), pady=px(0, 8))
        body = tk.Frame(card, bg=C["card"])
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, height=px(CANVAS_HEIGHT), bg=C["card"],
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", expand=True)

        # 底部提示：说明斜线区域代表 CPU 空闲
        hint = tk.Label(body, text=GANTT_HINT, bg=C["card"], fg=C["text_sub"],
                        font=self.F["small"], justify="left", anchor="w")
        hint.pack(fill="x", pady=px(4, 0))
        hint.bind("<Configure>", lambda e: self._fit_wrap(hint))

        # 窗口尺寸变化时按新宽度重绘甘特图
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_result_area(self):
        """调度结果区卡片：各进程等待时间、周转时间及平均值。"""
        card = ttk.LabelFrame(self.root, text="  调度结果区  ",
                              style="Card.TLabelframe", padding=px(14, 6, 14, 8))
        card.pack(side="top", fill="both", expand=True, padx=px(18), pady=px(0, 10))
        frame = tk.Frame(card, bg=C["card"])
        frame.pack(fill="both", expand=True)

        columns = ("pid", "arrival", "service", "finish", "waiting", "turnaround")
        self.result_tree = ttk.Treeview(frame, columns=columns,
                                        show="headings", height=4,
                                        style="Modern.Treeview")
        self.result_tree.tag_configure("evenrow", background=C["card"])
        self.result_tree.tag_configure("oddrow", background=C["row_alt"])
        for col, text, w in (
                ("pid", "进程ID", 120), ("arrival", "到达时间", 120),
                ("service", "服务时间", 120), ("finish", "完成时间", 120),
                ("waiting", "等待时间", 120), ("turnaround", "周转时间", 120)):
            # 表头与内容统一居中对齐，表头字体加粗
            self.result_tree.heading(col, text=text, anchor="center")
            self.result_tree.column(col, width=px(w), anchor="center", stretch=True)

        # 底部汇总条：浅色标签展示平均指标（先 pack 底部，保证横跨整行）
        chip = tk.Frame(frame, bg=C["card"])
        chip.pack(side="bottom", fill="x", pady=px(10, 0))
        self.avg_label = tk.Label(
            chip, text="平均等待时间：--        平均周转时间：--",
            font=self.F["label_bold"], fg=C["primary"],
            bg="#EAF3FF", padx=px(22), pady=px(8))
        self.avg_label.pack(side="left")

        # 表格主体 + 右侧细滚动条
        self.result_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical",
                            command=self.result_tree.yview,
                            style="Modern.Vertical.TScrollbar")
        sb.pack(side="right", fill="y", padx=px(6, 0))
        self.result_tree.configure(yscrollcommand=sb.set)

    def _center_window(self):
        """把窗口放到屏幕中央（设计尺寸 1100x750，按 DPI 等比放大）。"""
        self.root.update_idletasks()
        w, h = px(WIN_W), px(WIN_H)
        w, h = 1100, 800
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

    # ------------------------------------------------------------------
    # 事件处理（原有逻辑，完全不变）
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
            self.pid_color[pid] = MORANDI[self._color_i % len(MORANDI)]
            self._color_i += 1

        # 把新进程插入"已添加进程"表格，实现列表实时刷新
        iid = str(proc.index)
        self.proc_by_iid[iid] = proc
        # 交替行色仅用于视觉（tag 不影响任何数据或调度）
        row_tag = ("oddrow",) if proc.index % 2 else ("evenrow",)
        self.process_tree.insert("", "end", iid=iid,
                                 values=(pid, f"{arrival:g}", f"{service:g}"),
                                 tags=row_tag)
        # 清空输入框，便于连续录入
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
        """切换算法：只有 RR 需要时间片，选中 RR 时才显示时间片输入框；
        同时刷新卡片底部的算法简介文字。"""
        key, need_quantum = self._current_algorithm()
        if need_quantum:
            self.quantum_label.grid()
            self.quantum_entry.grid()
        else:
            self.quantum_label.grid_remove()
            self.quantum_entry.grid_remove()
        self.algo_desc.config(text=ALGO_DESC.get(key, ""))

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
        self.avg_label.config(text="平均等待时间：--        平均周转时间：--")
        self.sim_result = None

    def _on_canvas_resize(self, event=None):
        """画布尺寸变化时按新宽度重绘甘特图（窗口可缩放）。"""
        if self.sim_result is not None:
            self.draw_gantt(self.sim_result)

    # ------------------------------------------------------------------
    # 甘特图绘制与结果展示（仅渲染层，算法数据来自 scheduler.py）
    # ------------------------------------------------------------------

    def draw_gantt(self, result):
        """在 Canvas 上绘制甘特图。

        坐标换算：plot 宽度 / 总时长 = 每单位时间的像素数；
        空闲时段画灰色并叠加斜线填充；进程时段按 PID 分配莫兰迪柔和色，
        色块内部居中显示进程 ID，上方标注该时间片起止时刻，
        下方绘制带数字刻度的时间轴；画布顶部绘制颜色图例。
        """
        canvas = self.canvas
        canvas.delete("all")
        if result is None:
            return
        total = result.total_time
        if total <= 0:
            return

        width = canvas.winfo_width()
        if width <= 1:                       # 画布尚未完成布局时用默认值
            width = px(WIN_W - 60)
        height = canvas.winfo_height()
        if height <= 1:
            height = px(CANVAS_HEIGHT)

        left = px(LEFT_PAD)
        plot_w = max(px(160), width - left - px(RIGHT_PAD))
        scale = plot_w / total

        def x_of(t):
            """时间 t -> 画布 x 坐标。"""
            return left + t * scale

        # ---------- 1) 顶部图例：每个 PID 一枚色块 ----------
        pids = []
        for seg in result.segments:
            if seg.pid and seg.pid not in pids:
                pids.append(seg.pid)
        legend_top = px(8)
        per_row = max(1, int(plot_w // px(84)))       # 每行最多放多少个图例
        legend_rows = max(1, (len(pids) + per_row - 1) // per_row)
        for i, pid in enumerate(pids):
            row, col = divmod(i, per_row)
            lx = left + col * px(84)
            ly = legend_top + row * px(20)
            color = self.pid_color.get(pid, MORANDI[0])
            _fill_round_rect(canvas, lx, ly, lx + px(14), ly + px(11), px(3), color)
            canvas.create_text(lx + px(21), ly + px(5), text=pid, anchor="w",
                               fill=C["text"], font=self.F["small"])

        # ---------- 2) 布局各行 y 坐标 ----------
        legend_bottom = legend_top + legend_rows * px(20)
        label_y = legend_bottom + px(14)             # 时间区间标注行
        bar_top = label_y + px(18)                  # 色块顶部
        bar_h = px(BAR_HEIGHT)
        axis_y = bar_top + bar_h + px(24)           # 时间轴基线
        # 空间不足时压缩条高，保证坐标轴始终画得下
        if axis_y + px(26) > height:
            bar_h = max(px(26), bar_h - px(14))
            axis_y = bar_top + bar_h + px(20)

        # ---------- 3) 刻度与纵向网格线 ----------
        step = self._tick_step(total)
        ticks = []
        t = 0.0
        while True:
            ticks.append(t)
            if t >= total - 1e-9:
                break
            t = min(t + step, total)

        for tv in ticks:                        # 竖向浅色网格线
            xv = x_of(tv)
            canvas.create_line(xv, bar_top - px(6), xv, axis_y,
                               fill=C["grid"], width=1)

        # ---------- 4) 时间片色块 ----------
        for seg in result.segments:
            x1, x2 = x_of(seg.start), x_of(seg.end)
            w = x2 - x1
            if w < 1:
                continue
            if seg.pid is None:
                self._draw_idle(canvas, x1, bar_top, x2, bar_top + bar_h)
                if w >= px(34):                # 空闲段中央标注“空闲”
                    canvas.create_text((x1 + x2) / 2, bar_top + bar_h / 2,
                                       text="空闲", fill=C["text_sub"],
                                       font=self.F["small"])
            else:
                color = self.pid_color.get(seg.pid, MORANDI[0])
                _fill_round_rect(canvas, x1, bar_top, x2, bar_top + bar_h,
                                 px(6), color, outline=_shade(color, -0.10), width=1)
                if w >= px(22):                # 色块内部居中显示进程 ID
                    font = self.F["bar"] if w >= px(40) else self.F["bar_small"]
                    canvas.create_text((x1 + x2) / 2, bar_top + bar_h / 2,
                                       text=seg.pid, fill=_text_on(color),
                                       font=font)
                if w >= px(58):                # 色块上方标注该时间片起止时刻
                    canvas.create_text((x1 + x2) / 2, label_y,
                                       text=f"{seg.start:g} ~ {seg.end:g}",
                                       fill=C["text_sub"], font=self.F["tiny"])

        # ---------- 5) 时间轴基线与刻度数字 ----------
        canvas.create_line(left, axis_y, left + plot_w, axis_y,
                           fill=C["axis"], width=1)
        for tv in ticks:
            xv = x_of(tv)
            canvas.create_line(xv, axis_y, xv, axis_y + px(6), fill=C["axis"])
            label = str(int(tv)) if abs(tv - round(tv)) < 1e-9 else f"{tv:g}"
            canvas.create_text(xv, axis_y + px(15), text=label,
                               font=self.F["tiny"], fill=C["text_sub"])

    def _draw_idle(self, canvas, x0, y0, x1, y1):
        """绘制空闲时间段：灰色底 + 斜线填充，直观表达“CPU 无事可做”。"""
        # 灰色底
        canvas.create_rectangle(x0, y0, x1, y1, fill=C["idle"], outline="")
        # 45 度斜线，逐条计算与矩形的交集后绘制
        step = px(9)
        h = y1 - y0
        c = x0 - h
        while c <= x1 + h:
            xs = max(c, x0)
            xe = min(c + h, x1)
            if xe > xs:
                canvas.create_line(xs, y1 - (xs - c), xe, y1 - (xe - c),
                                   fill=C["idle_line"], width=1)
            c += step
        # 最后补边框，保证斜线不越界
        canvas.create_rectangle(x0, y0, x1, y1, outline=C["idle_line"], width=1)

    @staticmethod
    def _tick_step(total):
        """根据总时长选择刻度间隔，避免刻度数字挤在一起。"""
        for limit, step in TICK_STEP_RULES:
            if total <= limit:
                return step
        return 20

    def fill_results(self, result):
        """把模拟结果填入结果表，并更新平均值标签。"""
        for i, r in enumerate(result.results):
            row_tag = ("oddrow",) if i % 2 else ("evenrow",)  # 交替行色，仅外观
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
                f"{r.turnaround:.2f}"), tags=row_tag)
        self.avg_label.config(
            text=(f"平均等待时间：{result.avg_waiting:.2f}"
                  f"        平均周转时间：{result.avg_turnaround:.2f}"))

    # ------------------------------------------------------------------

    def run(self):
        """进入 Tk 主循环。"""
        self.root.mainloop()
