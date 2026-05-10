import time

class tqdm:
    def __init__(self, iterable=None, desc=None, total=None, unit=None, ncols=80):
        self.iterable = iterable if iterable is not None else []  # 待迭代对象
        self.desc = desc or "处理中 🚀"
        self.total = total or len(self.iterable)  # 总处理数量
        self.current = 0  # 当前处理数量
        self.unit = unit or "项"  # 单位描述
        self.ncols = ncols  # 进度条宽度
        self.start_time = time.time()  # 开始时间
        self.completed = False  # 是否完成标记

    def __iter__(self):
        # 迭代器接口，遍历待处理对象并更新进度
        for item in self.iterable:
            self.update(1)
            yield item
        self.close()

    def update(self, n=1):
        # 更新进度条（n：本次更新数量）
        if self.completed:
            return
        self.current += n
        if self.current > self.total:
            self.current = self.total  # 防止进度超过100%
        
        elapsed = time.time() - self.start_time  # 已耗时
        rate = self.current / elapsed if elapsed > 0 else 0  # 处理速率
        percent = (self.current / self.total) * 100 if self.total > 0 else 0  # 进度百分比
        
        # 构建文本进度条
        bar_length = max(1, self.ncols - 50)  # 进度条主体长度
        filled_length = int(bar_length * self.current / self.total) if self.total > 0 else 0
        bar = "\u2588" * filled_length + "-" * (bar_length - filled_length)  # 进度条样式
        
        # 进度信息文本
        info = (
            f"{self.desc}: |{bar}| {self.current}/{self.total} {self.unit} "
            f"({percent:.1f}%) | {rate:.1f} {self.unit}/秒 ⏱️"
        )
        print(f"\r{info.ljust(self.ncols)}", end="", flush=True)  # 实时刷新进度条
        
    def close(self):
        # 关闭进度条，输出完成信息
        if self.completed:
            return
        self.completed = True
        elapsed = time.time() - self.start_time
        final_msg = f"{self.desc.replace('处理中 🚀', '完成 ✅')}: 完成 {self.current}/{self.total} 项，耗时 {elapsed:.2f}秒 ⏱️"
        print(f"\r{final_msg.ljust(self.ncols)}")
        print()