import time

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from api.config import GlobalConst as gc


def sec2time(seconds: int) -> str:
    """
    将秒数转换为时分秒格式的字符串。
    
    Args:
        seconds: 要转换的秒数
        
    Returns:
        格式化的时间字符串，格式为 "h:mm:ss" 或 "mm:ss"，如果秒数为0则返回"--:--"
    """
    hours = int(seconds / 3600)
    minutes = int(seconds % 3600 / 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}"
    if seconds > 0:
        return f"{minutes:02}:{secs:02}"
    return "--:--"


def show_progress(task_name: str, start_position: int, duration: int, 
                 total_length: int, speed: float) -> None:
    """
    显示任务进度条，模拟任务进度。
    
    Args:
        task_name: 当前执行的任务名称
        start_position: 起始位置（以秒为单位）
        duration: 任务持续时间（以秒为单位）
        total_length: 任务总长度（以秒为单位）
        speed: 任务执行速度
        
    Returns:
        None
    """
    console = Console()
    start_time = time.time()
    expected_end_time = start_time + (duration / speed)
    with Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:.0f}/{task.total:.0f}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(task_name, total=total_length, completed=start_position)
        while time.time() < expected_end_time:
            current_position = start_position + int((time.time() - start_time) * speed)
            progress.update(task_id, completed=min(current_position, total_length))
            time.sleep(gc.THRESHOLD)
