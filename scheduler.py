"""scheduler.py
进程调度算法纯逻辑模块：FCFS、SJF（非抢占）、RR（时间片轮转）。

本模块不依赖任何界面库，只负责调度计算，可单独运行测试。
每个算法都返回 SimulationResult，其中：
    segments  —— 甘特图时间段（含 CPU 空闲段），供界面绘图；
    results   —— 每个进程的等待时间、周转时间等统计。
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Process:
    """一个进程的基本信息。

    pid      进程标识（字符串，如 "P1"）
    arrival  到达时间
    service  服务时间（进程需要的 CPU 总时长）
    index    添加进系统的顺序号，用于到达时间相同时的稳定排序
    """
    pid: str
    arrival: float
    service: float
    index: int = 0


@dataclass
class GanttSegment:
    """甘特图上的一个时间段：CPU 从 start 执行到 end。

    pid 为 None 时表示该时间段 CPU 空闲（没有进程可执行）。
    """
    start: float
    end: float
    pid: Optional[str] = None


@dataclass
class ProcessResult:
    """单个进程的调度统计结果。"""
    pid: str
    arrival: float
    service: float
    finish: float      # 完成时间
    waiting: float     # 等待时间 = 完成时间 - 到达时间 - 服务时间
    turnaround: float  # 周转时间 = 完成时间 - 到达时间


@dataclass
class SimulationResult:
    """一次完整模拟的结果汇总。"""
    algorithm: str
    total_time: float                 # 全部进程完成的时刻
    segments: list = field(default_factory=list)   # 甘特图时间段（含空闲段）
    results: list = field(default_factory=list)    # 各进程统计（按添加顺序）
    avg_waiting: float = 0.0          # 平均等待时间
    avg_turnaround: float = 0.0       # 平均周转时间


# ---------------------------------------------------------------------------
# 三个公开的调度入口
# ---------------------------------------------------------------------------

def fcfs(processes):
    """先来先服务（FCFS）：按到达时间先后依次执行，非抢占。

    到达时间相同时按添加顺序执行（稳定排序）。
    """
    segments, finish = _non_preemptive_simulate(
        processes, key=lambda p: (p.arrival, p.index))
    return _build_result("FCFS", processes, segments, finish)


def sjf(processes):
    """短作业优先（SJF，非抢占）：每次从就绪队列中选服务时间最短的进程。

    服务时间相同时，先比较到达时间，再比较添加顺序。
    """
    segments, finish = _non_preemptive_simulate(
        processes, key=lambda p: (p.service, p.arrival, p.index))
    return _build_result("SJF", processes, segments, finish)


def rr(processes, quantum):
    """时间片轮转（RR）：每个进程每次最多连续执行 quantum 时间。

    时间片用完仍未完成的进程排到就绪队列队尾。
    """
    if quantum <= 0:
        raise ValueError("时间片必须为正数")
    segments, finish = _rr_simulate(processes, quantum)
    return _build_result("RR", processes, segments, finish)


# ---------------------------------------------------------------------------
# 内部模拟实现
# ---------------------------------------------------------------------------

def _non_preemptive_simulate(processes, key):
    """FCFS 与 SJF 共用的非抢占式模拟框架。

    就绪队列的入队时机（最容易出错的地方）：
    - 就绪队列必须跨迭代保持，不能每轮清空——清空会导致
      "早到达但当时没被选中"的进程被漏掉；
    - 每个时刻先让所有"到达时间 <= 当前时刻"的进程入队；
    - 就绪队列为空但还有进程未到达时，CPU 空闲，
      时间直接跳到下一个进程的到达时刻，并记录空闲段；
    - 从就绪队列按 key 选出一个进程后一次性执行完（非抢占）。
    """
    # 按到达时间排序，便于判断"哪些进程已经到达"
    pending = sorted(processes, key=lambda p: (p.arrival, p.index))
    ready = []                     # 就绪队列：已到达且未完成的进程
    remaining = {p.pid: p.service for p in processes}
    finish = {}
    segments = []
    i = 0
    n = len(pending)
    t = 0.0                        # 当前时刻
    done = 0                       # 已完成的进程数

    while done < n:
        # 入队时机：到达时间 <= 当前时刻的进程全部进入就绪队列
        while i < n and pending[i].arrival <= t + 1e-9:
            ready.append(pending[i])
            i += 1

        if not ready:
            # CPU 空闲：跳到下一个进程的到达时刻，并记录空闲段
            next_arrival = pending[i].arrival
            segments.append(GanttSegment(t, next_arrival, None))
            t = next_arrival
            continue

        # 从就绪队列按 key 选一个进程，非抢占执行到底
        chosen = min(ready, key=key)
        ready.remove(chosen)
        segments.append(GanttSegment(t, t + remaining[chosen.pid], chosen.pid))
        t += remaining[chosen.pid]
        finish[chosen.pid] = t
        done += 1

    return segments, finish


def _rr_simulate(processes, quantum):
    """时间片轮转模拟。

    就绪队列是一个先进先出（FIFO）队列，入队时机有两处，都不能漏：
    1. 开始/空闲期间：到达时间 <= 当前时刻的进程按到达顺序入队；
    2. 某进程正在执行期间：新到达的进程也要按到达顺序入队。
    时间片用完但仍未完成的进程，重新排到队尾。
    """
    pending = sorted(processes, key=lambda p: (p.arrival, p.index))
    ready = deque()                # FIFO 就绪队列
    remaining = {p.pid: p.service for p in processes}
    finish = {}
    segments = []
    i = 0
    n = len(pending)
    t = 0.0
    done = 0

    while done < n:
        # 入队时机 1：当前时刻之前（含）到达的进程进入就绪队列
        while i < n and pending[i].arrival <= t + 1e-9:
            ready.append(pending[i])
            i += 1

        if not ready:
            # CPU 空闲：跳到下一个进程的到达时刻
            next_arrival = pending[i].arrival
            segments.append(GanttSegment(t, next_arrival, None))
            t = next_arrival
            continue

        # 取出队首进程，执行 min(时间片, 剩余服务时间)
        p = ready.popleft()
        run = min(quantum, remaining[p.pid])
        segments.append(GanttSegment(t, t + run, p.pid))
        t += run
        remaining[p.pid] -= run

        # 入队时机 2：该进程执行期间新到达的进程也要按到达顺序入队
        while i < n and pending[i].arrival <= t + 1e-9:
            ready.append(pending[i])
            i += 1

        if remaining[p.pid] > 1e-9:
            ready.append(p)        # 时间片耗尽仍未完成：排到队尾
        else:
            finish[p.pid] = t      # 执行完毕，记录完成时刻
            done += 1

    return segments, finish


# ---------------------------------------------------------------------------
# 结果整理
# ---------------------------------------------------------------------------

def _build_result(algorithm, processes, segments, finish):
    """把模拟出的时间段与完成时刻整理成 SimulationResult。"""
    # 合并相邻的同一进程时间段（RR 中同一进程可能连续两次被轮转到），
    # 只影响甘特图显示，不影响统计数据。
    merged = []
    for seg in segments:
        if merged and merged[-1].pid == seg.pid:
            merged[-1].end = seg.end
        else:
            merged.append(GanttSegment(seg.start, seg.end, seg.pid))

    results = []
    for p in processes:            # 保持添加顺序输出
        f = finish[p.pid]
        waiting = f - p.arrival - p.service   # 等待 = 完成 - 到达 - 服务
        results.append(ProcessResult(
            pid=p.pid, arrival=p.arrival, service=p.service,
            finish=f, waiting=waiting, turnaround=f - p.arrival))

    n = len(results)
    return SimulationResult(
        algorithm=algorithm,
        total_time=max(finish.values()),
        segments=merged,
        results=results,
        avg_waiting=sum(r.waiting for r in results) / n,
        avg_turnaround=sum(r.turnaround for r in results) / n,
    )
