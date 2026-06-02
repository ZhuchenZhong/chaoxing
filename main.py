# -*- coding: utf-8 -*-
import argparse
import enum
import sys
import threading
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from dataclasses import dataclass
from queue import PriorityQueue, ShutDown
from typing import Any

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from api.answer import Tiku
from api.base import Chaoxing, Account, StudyResult
from api.config_store import (
    load_config_from_file as load_config_sections,
    normalize_common_config,
)
from api.events import EventSink, StudyEvent, emit_event
from api.exceptions import LoginError, InputFormatError
from api.logger import logger
from api.notification import Notification
from api.live import Live
from api.live_process import LiveProcessor
from api.rich_ui import RichStudyDisplay

class ChapterResult(enum.Enum):
    SUCCESS=0,
    ERROR=1,
    NOT_OPEN=2,
    PENDING=3


def log_error(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except BaseException as e:
            logger.error(f"Error in thread {threading.current_thread().name}: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            raise

    return wrapper


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ZhuchenZhong/chaoxing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--use-cookies", action="store_true", default=None, help="使用cookies登录")

    parser.add_argument(
        "-c", "--config", type=str, default=None, help="使用配置文件运行程序"
    )
    parser.add_argument("-u", "--username", type=str, default=None, help="手机号账号")
    parser.add_argument("-p", "--password", type=str, default=None, help="登录密码")
    parser.add_argument(
        "-l", "--list", type=str, default=None, help="要学习的课程ID列表, 以 , 分隔"
    )
    parser.add_argument(
        "-s", "--speed", type=float, default=None, help="视频播放倍速 (默认1, 最大2)"
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=None, help="同时进行的章节数 (默认4, 如果一个章节有多个任务点，不会限制同时处理任务点的数量)"
    )

    parser.add_argument(
        "-v",
        "--verbose",
        "--debug",
        action="store_true",
        help="启用调试模式, 输出DEBUG级别日志",
    )
    parser.add_argument(
        "-a", "--notopen-action", type=str, default=None,
        choices=["retry", "ask", "continue"],
        help="遇到关闭任务点时的行为: retry-重试, ask-询问, continue-继续"
    )

    parser.add_argument("--auto-sign", action="store_true", help="自动签到")

    # 在解析之前捕获 -h 的行为
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()


def load_config_from_file(config_path):
    """从配置文件加载设置"""
    return load_config_sections(config_path)


def build_config_from_args(args):
    """从命令行参数构建配置"""
    common_config = {
        "use_cookies": args.use_cookies,
        "username": args.username,
        "password": args.password,
        "course_list": [item.strip() for item in args.list.split(",") if item.strip()] if args.list else None,
        "speed": args.speed,
        "jobs": args.jobs,
        "notopen_action": args.notopen_action,
    }
    return common_config, {}, {}


def init_config():
    """初始化配置"""
    args = parse_args()

    if args.config:
        common_config, tiku_config, notification_config = load_config_from_file(args.config)
    else:
        common_config, tiku_config, notification_config = build_config_from_args(args)

    arg_common_config, _, _ = build_config_from_args(args)
    for key, value in arg_common_config.items():
        if value not in (None, "", []):
            common_config[key] = value

    return normalize_common_config(common_config), tiku_config, notification_config


def init_chaoxing(common_config, tiku_config, allow_prompt=True):
    """初始化超星实例"""
    username = common_config.get("username", "")
    password = common_config.get("password", "")
    use_cookies = common_config.get("use_cookies", False)
    
    # 如果没有提供用户名密码，从命令行获取
    if (not username or not password) and not use_cookies:
        if not allow_prompt:
            raise LoginError("未配置账号密码，请在 TUI 中填写密码或启用 Cookie 登录")
        username = input("请输入你的手机号, 按回车确认\n手机号:")
        password = input("请输入你的密码, 按回车确认\n密码:")
    
    account = Account(username, password)
    
    # 设置题库
    tiku = Tiku()
    tiku.config_set(tiku_config)  # 载入配置
    tiku = tiku.get_tiku_from_config()  # 载入题库
    tiku.init_tiku()  # 初始化题库
    
    # 获取查询延迟设置
    
    # 检查大模型连接（如果使用的是大模型题库）
    # 根据配置文件中的 provider 判断是否为大模型题库
    provider = tiku_config.get('provider', '')
    provider_list = [name.strip() for name in provider.split(',') if name.strip()]
    if any(name in ['AI', 'SiliconFlow'] for name in provider_list):
        check_connection = tiku_config.get('check_llm_connection', 'true').lower() == 'true'
        if check_connection:
            logger.info(f'正在验证大模型配置 (provider={provider})...')
            if not tiku.check_llm_connection():
                logger.error('大模型连接检查失败')
                if not allow_prompt:
                    raise RuntimeError('大模型连接检查失败，TUI 非交互运行未继续')
                choice = input('大模型连接检查失败，无法准确答题，是否继续运行？(Y/n): ').strip().lower()
                # 直接回车默认继续运行
                if choice not in ('', 'y', 'yes'):
                    raise RuntimeError('用户取消运行')
                logger.info('用户选择继续运行...')

    query_delay = tiku_config.get("delay", 0)
    
    # 实例化超星API
    chaoxing = Chaoxing(account=account, tiku=tiku, query_delay=query_delay)
    
    return chaoxing

def process_job(chaoxing: Chaoxing, course: dict, job: dict, job_info: dict, speed: float,
                event_sink: EventSink | None = None) -> StudyResult:
    """处理单个任务点"""
    # 视频任务
    if job["type"] == "video":
        logger.trace(f"识别到视频任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        # 超星的接口没有返回当前任务是否为Audio音频任务
        video_result = chaoxing.study_video(
            course, job, job_info, _speed=speed, _type="Video", event_sink=event_sink
        )
        if video_result.is_failure():
            logger.warning("当前任务非视频任务, 正在尝试音频任务解码")
            video_result = chaoxing.study_video(
                course, job, job_info, _speed=speed, _type="Audio", event_sink=event_sink)
        if video_result.is_failure():
            logger.warning(
                f"出现异常任务 -> 任务章节: {course['title']} 任务ID: {job['jobid']}, 已跳过"
            )
        return video_result
    # 文档任务
    elif job["type"] == "document":
        logger.trace(f"识别到文档任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        emit_event(event_sink, StudyEvent(kind="job_start", title=job.get("name", "文档任务"), key=job["jobid"], total=1))
        result = chaoxing.study_document(course, job)
        emit_event(event_sink, StudyEvent(kind="job_done", title=job.get("name", "文档任务"), key=job["jobid"], status=result.name))
        return result
    # 测验任务
    elif job["type"] == "workid":
        logger.trace(f"识别到章节检测任务, 任务章节: {course['title']}")
        emit_event(event_sink, StudyEvent(kind="job_start", title=job.get("name", "章节检测"), key=job["jobid"], total=1))
        result = chaoxing.study_work(course, job, job_info)
        emit_event(event_sink, StudyEvent(kind="job_done", title=job.get("name", "章节检测"), key=job["jobid"], status=result.name))
        return result
    # 阅读任务
    elif job["type"] == "read":
        logger.trace(f"识别到阅读任务, 任务章节: {course['title']}")
        emit_event(event_sink, StudyEvent(kind="job_start", title=job.get("name", "阅读任务"), key=job["jobid"], total=1))
        result = chaoxing.study_read(course, job, job_info)
        emit_event(event_sink, StudyEvent(kind="job_done", title=job.get("name", "阅读任务"), key=job["jobid"], status=result.name))
        return result
    # 直播任务
    elif job["type"] == "live":
        logger.trace(f"识别到直播任务, 任务章节: {course['title']} 任务ID: {job['jobid']}")
        try:
            # 准备直播所需参数
            defaults = {
                "userid": chaoxing.get_uid(),
                "clazzId": course.get("clazzId"),
                "knowledgeid": job_info.get("knowledgeid")
            }
            
            # 创建直播对象
            live = Live(
                attachment=job,
                defaults=defaults,
                course_id=course.get("courseId")
            )
            
            # 启动直播处理线程
            thread = threading.Thread(
                target=LiveProcessor.run_live,
                args=(live, speed),
                daemon=True
            )
            thread.start()
            thread.join()  # 等待直播处理完成
            emit_event(event_sink, StudyEvent(kind="job_done", title=live.name, key=job["jobid"], status="SUCCESS"))
            return StudyResult.SUCCESS
        except Exception as e:
            logger.error(f"处理直播任务时出错: {str(e)}")
            return StudyResult.ERROR

    logger.error(f"未知任务类型: {job['type']}")
    return StudyResult.ERROR


@dataclass(order=True)
class ChapterTask:
    index: int
    point: dict[str, Any]
    result: ChapterResult = ChapterResult.PENDING
    tries: int = 0

class JobProcessor:
    def __init__(self, chaoxing: Chaoxing, course: dict[str, Any], tasks: list[ChapterTask],
                 config: dict[str, Any], event_sink: EventSink | None = None):
        if "jobs" not in config or not config["jobs"]:
            config["jobs"] = 4
        
        self.chaoxing = chaoxing
        self.course = course
        self.speed = config["speed"]
        self.max_tries = 5
        self.tasks = tasks
        self.failed_tasks: list[ChapterTask] = []
        self.task_queue: PriorityQueue[ChapterTask] = PriorityQueue()
        self.retry_queue: PriorityQueue[ChapterTask] = PriorityQueue()
        self.wait_queue: PriorityQueue[ChapterTask] = PriorityQueue()
        self.threads: list[threading.Thread] = []
        self.worker_num = config["jobs"]
        self.config = config
        self.event_sink = event_sink

    def run(self):
        for task in self.tasks:
            self.task_queue.put(task)

        for i in range(self.worker_num):
            thread = threading.Thread(target=self.worker_thread, daemon=True)
            self.threads.append(thread)
            thread.start()

        threading.Thread(target=self.retry_thread, daemon=True).start()

        self.task_queue.join()
        time.sleep(0.5)
        self.task_queue.shutdown()


    @log_error
    def worker_thread(self):
        while True:
            try:
                task = self.task_queue.get()
            except ShutDown:
                logger.info("Queue shut down")
                return

            task.result = process_chapter(self.chaoxing, self.course, task.point, self.speed, self.event_sink)

            match task.result:
                case ChapterResult.SUCCESS:
                    logger.debug("Task success: {}", task.point["title"])
                    self.task_queue.task_done()
                    logger.debug(f"unfinished task: {self.task_queue.unfinished_tasks}")

                case ChapterResult.NOT_OPEN:
                    # task.tries += 1
                    if self.config["notopen_action"] == "continue":
                        logger.warning("章节未开启: {}, 正在跳过", task.point["title"])
                        self.task_queue.task_done()
                        continue

                    if task.tries >= self.max_tries:
                        logger.error(
                            "章节未开启: {} 可能由于上一章节的章节检测未完成, 也可能由于该章节因为时效已关闭，"
                            "请手动检查完成并提交再重试。或者在配置中配置(自动跳过关闭章节/开启题库并启用提交)"
                        , task.point["title"])
                        self.task_queue.task_done()
                        continue

                    # self.wait_queue.put(task)
                    self.retry_queue.put(task)

                case ChapterResult.ERROR:
                    task.tries += 1
                    logger.warning("Retrying task {} ({}/{} attempts)", task.point["title"], task.tries,
                                   self.max_tries)
                    if task.tries >= self.max_tries:
                        logger.error("Max retries reached for task: {}", task.point["title"])
                        self.failed_tasks.append(task)
                        self.task_queue.task_done()
                        continue
                    self.retry_queue.put(task)

                case _:
                    logger.error("Invalid task state {} for task {}", task.result, task.point["title"])
                    self.failed_tasks.append(task)
                    self.task_queue.task_done()

    @log_error
    def retry_thread(self):
        try:
            while True:
                task = self.retry_queue.get()
                self.task_queue.put(task)
                # task_done is not called when a task failed and needs to be retried so if is reinserted into the queue,
                # the task num will increase by one and become more than the real task number
                self.task_queue.task_done()
                time.sleep(1) # TODO: Replace with a configurable wait time
        except ShutDown:
            pass


def process_chapter(chaoxing: Chaoxing, course:dict[str, Any], point:dict[str, Any], speed:float,
                    event_sink: EventSink | None = None) -> ChapterResult:
    """处理单个章节"""
    logger.info(f'当前章节: {point["title"]}')
    emit_event(event_sink, StudyEvent(
        kind="chapter_start",
        title=point["title"],
        course_id=str(course.get("courseId", "")),
        chapter_id=str(point.get("id", "")),
        message=f"开始章节: {point['title']}",
    ))
    if point["has_finished"]:
        logger.info(f'章节：{point["title"]} 已完成所有任务点')
        emit_event(event_sink, StudyEvent(kind="chapter_done", title=point["title"], status="SUCCESS",
                                          message=f"章节已完成: {point['title']}"))
        return ChapterResult.SUCCESS
    
    # 随机等待，避免请求过快
    chaoxing.rate_limiter.limit_rate(random_time=True,random_min=0, random_max=0.2)
    
    # 获取当前章节的所有任务点
    job_info = None
    jobs, job_info = chaoxing.get_job_list(course, point)

    # 发现未开放章节, 根据配置处理
    if job_info.get("notOpen", False):
        emit_event(event_sink, StudyEvent(kind="chapter_done", title=point["title"], status="NOT_OPEN",
                                          message=f"章节未开放: {point['title']}"))
        return ChapterResult.NOT_OPEN

    # 已经默认处理空任务，此处不需要判断
    if not jobs:
        pass

    # TODO: 个别章节很恶心，多到5个点，可以并行处理，将来会让不同课程不同章节的所有任务点共享一个队列，从而实现全局并行
    job_results:list[StudyResult]=[]
    with ThreadPoolExecutor(max_workers=5) as executor:
        for result in executor.map(lambda job: process_job(chaoxing, course, job, job_info, speed, event_sink), jobs):
            job_results.append(result)
    
    for result in job_results:
        if result.is_failure():
            emit_event(event_sink, StudyEvent(kind="chapter_done", title=point["title"], status="ERROR",
                                              message=f"章节失败: {point['title']}"))
            return ChapterResult.ERROR

    emit_event(event_sink, StudyEvent(kind="chapter_done", title=point["title"], status="SUCCESS",
                                      message=f"章节完成: {point['title']}"))
    return ChapterResult.SUCCESS



def process_course(chaoxing: Chaoxing, course:dict[str, Any], config: dict, event_sink: EventSink | None = None):
    """处理单个课程"""
    logger.info(f"开始学习课程: {course['title']}")
    emit_event(event_sink, StudyEvent(
        kind="course_start",
        title=course["title"],
        course_id=str(course.get("courseId", "")),
        message=f"开始学习课程: {course['title']}",
    ))
    
    # 获取当前课程的所有章节
    point_list = chaoxing.get_course_point(
        course["courseId"], course["clazzId"], course["cpi"]
    )

    # 为了支持课程任务回滚, 采用下标方式遍历任务点

    tasks=[]

    for i, point in enumerate(point_list["points"]):
        task = ChapterTask(point=point, index=i)
        tasks.append(task)
    p = JobProcessor(chaoxing, course, tasks, config, event_sink=event_sink)
    p.run()

def filter_courses(all_course, course_list, allow_prompt=True):
    """过滤要学习的课程"""
    if not course_list:
        if not allow_prompt:
            return all_course
        # 手动输入要学习的课程ID列表
        console = Console()
        table = Table(title="课程列表")
        table.add_column("ID", style="cyan")
        table.add_column("课程名")
        for course in all_course:
            table.add_row(str(course["courseId"]), str(course["title"]))
        console.print(table)
        try:
            course_list = Prompt.ask("请输入想要学习的课程列表，以逗号分隔；留空则学习全部").split(",")
        except Exception as e:
            raise InputFormatError("输入格式错误") from e

    # 筛选需要学习的课程
    course_task = []
    course_ids = []
    for course in all_course:
        if course["courseId"] in course_list and course["courseId"] not in course_ids:
            course_task.append(course)
            course_ids.append(course["courseId"])
    
    # 如果没有指定课程，则学习所有课程
    if not course_task:
        course_task = all_course
    
    return course_task


def run_study(common_config, tiku_config, notification_config, event_sink: EventSink | None = None,
              allow_prompt=True):
    notification = None
    try:
        common_config["speed"] = min(2.0, max(1.0, common_config.get("speed", 1.0)))
        common_config["notopen_action"] = common_config.get("notopen_action", "retry")

        chaoxing = init_chaoxing(common_config, tiku_config, allow_prompt=allow_prompt)

        notification = Notification()
        notification.config_set(notification_config)
        notification = notification.get_notification_from_config()
        notification.init_notification()

        _login_state = chaoxing.login(login_with_cookies=common_config.get("use_cookies", False))
        if not _login_state["status"]:
            raise LoginError(_login_state["msg"])

        all_course = chaoxing.get_course_list()
        course_task = filter_courses(all_course, common_config.get("course_list"), allow_prompt=allow_prompt)

        logger.info(f"课程列表过滤完毕, 当前课程任务数量: {len(course_task)}")
        for course in course_task:
            process_course(chaoxing, course, common_config, event_sink=event_sink)

        logger.info("所有课程学习任务已完成")
        emit_event(event_sink, StudyEvent(kind="summary", status="SUCCESS", message="所有课程学习任务已完成"))
        notification.send("chaoxing : 所有课程学习任务已完成")
        return True
    except BaseException as e:
        if notification:
            try:
                notification.send(f"chaoxing : 出现错误 {type(e).__name__}: {e}\n{traceback.format_exc()}")
            except Exception:
                pass
        raise


def main(default_tui=False):
    """主程序入口"""
    if default_tui and len(sys.argv) == 1 and sys.stdin.isatty():
        from api.tui import run_tui
        run_tui()
        return

    notification = None
    try:
        # 初始化配置
        common_config, tiku_config, notification_config = init_config()
        with RichStudyDisplay() as display:
            run_study(common_config, tiku_config, notification_config, event_sink=display)
        
    except SystemExit as e:
        if e.code != 0:
            logger.error(f"错误: 程序异常退出, 返回码: {e.code}")
        sys.exit(e.code)
    except KeyboardInterrupt as e:
        logger.error(f"错误: 程序被用户手动中断, {e}")
    except BaseException as e:
        logger.error(f"错误: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        try:
            if notification:
                notification.send(f"chaoxing : 出现错误 {type(e).__name__}: {e}\n{traceback.format_exc()}")
        except Exception:
            pass  # 如果通知发送失败，忽略异常
        raise e


if __name__ == "__main__":
    main()
