
PRIORITY_HIGH = 100
PRIORITY_NORMAL = 0
PRIORITY_LOW = -100


class EventSource:
    def __init__(self, events=None):
        events = events or []
        self.events = {}
        for e in events:
            self.events[e] = PriorityDispatcher()

    def hook(self, obj, prefix=None):
        prefix = prefix or '_handle_'
        for e in self.events:
            attr = prefix + e
            if hasattr(obj, attr):
                self.events[e].register(getattr(obj, attr))


class PriorityDispatcher:
    def __init__(self):
        self.handlers = {
            PRIORITY_HIGH: [],
            PRIORITY_NORMAL: [],
            PRIORITY_LOW: []
        }

        self._veto = False

    def __add__(self, other):
        self.register(other)
        return self

    def __sub__(self, other):
        self.unregister(other)
        return self

    def __call__(self, *args, **kwargs):
        return self.dispatch(*args)

    def __len__(self):
        return sum([len(h) for h in self.handlers.values()])

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
