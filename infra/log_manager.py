import time

class LogItem:
    def __init__(self, timestamp, environment, action, result, success_rate):
        self.timestamp = timestamp
        self.environment = environment
        self.action = action
        self.result = result
        self.success_rate = success_rate

class Logger:
    def __init__(self, stm=None, capsule_manager=None):
        self.stm = stm
        self.capsule_manager = capsule_manager

    def log(self, log_item):
        if self.stm:
            self.stm.insert_log(log_item.__dict__)

    def flush(self):
        pass

    def collect_error(self, error_type, message, exc_info, context):
        if self.capsule_manager:
            self.capsule_manager.add_error_log_capsule(message, str(exc_info), context.get("module"))

    def log_agent_action(self, environment, action, result, success_rate):
        self.log(LogItem(time.time(), environment, action, result, success_rate))