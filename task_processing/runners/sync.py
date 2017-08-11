import logging
import time

from six.moves.queue import Queue

from task_processing.interfaces.runner import Runner

log = logging.getLogger(__name__)


class Sync(Runner):
    def __init__(self, executor):
        self.executor = executor
        self.TASK_CONFIG_INTERFACE = executor.TASK_CONFIG_INTERFACE
        self.queue = Queue()

    def kill(self, *args):
        pass

    def run(self, task_config, task_id=None):
        if task_id is None:
            task_id = self.new_task_id()

        self.executor.run(task_config, task_id)
        event_queue = self.executor.get_event_queue()

        while True:
            event = event_queue.get()

            if event.kind == 'control' and \
               event.message == 'stop':
                log.info('Stop event received: {}'.format(event))
                return event

            if event.task_id != task_id:
                event_queue.put(event)
                time.sleep(1)  # hope somebody else picks it up?
                continue

            if event.terminal:
                return event

    def stop(self):
        self.executor.stop()
