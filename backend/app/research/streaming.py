import asyncio
from collections import defaultdict


class StreamManager:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, task_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[task_id].add(queue)
        return queue

    async def publish(self, task_id: str, payload: dict[str, object]) -> None:
        for queue in list(self._subscribers.get(task_id, set())):
            await queue.put(payload)

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(task_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(task_id, None)

