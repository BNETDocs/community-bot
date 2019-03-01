
PRIORITY_HIGH = 100
PRIORITY_NORMAL = 0
PRIORITY_LOW = -100


class PriorityDispatcher:
    def __init__(self):
        self.handlers = {
            PRIORITY_HIGH: [],
            PRIORITY_NORMAL: [],
            PRIORITY_LOW: []
        }

        self._veto = False

    # This function allows additional priority levels to be added. Higher levels take precedence.
    def register(self, callback, priority=PRIORITY_NORMAL):
        if priority not in self.handlers:
            self.handlers[priority] = []
        self.handlers[priority].append(callback)
        return callback

    def unregister(self, callback):
        count = 0
        for handlers in self.handlers.values():
            if callback in handlers:
                handlers.remove(callback)
                count += 1
        return count

    # Returns FALSE if the event is veto'd by one of the handlers.
    def dispatch(self, *args):
        for priority, handlers in sorted(self.handlers.items(), reverse=True):
            if self._veto:
                self._veto = False
                return False

            for handler in handlers:
                handler(*args)
        return True

    def veto(self):
        self._veto = True
