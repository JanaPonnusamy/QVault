from concurrent.futures import ThreadPoolExecutor


class KnowledgeExecutor:
    """Execution abstraction for long-running research sessions. Business
    logic submits work here and never touches the scheduling mechanism, so
    swapping in Celery/RQ/RabbitMQ/a Windows service later means writing one
    new executor - no orchestrator changes."""

    def submit(self, func, *args, **kwargs):
        raise NotImplementedError


class BackgroundTaskExecutor(KnowledgeExecutor):
    """Default executor: a small process-local thread pool. Compatible with
    FastAPI (threads run fine under uvicorn) while keeping the orchestrator
    independent of FastAPI's own BackgroundTasks object."""

    def __init__(self, max_workers=2):
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="knowledge",
        )

    def submit(self, func, *args, **kwargs):
        return self._pool.submit(func, *args, **kwargs)
