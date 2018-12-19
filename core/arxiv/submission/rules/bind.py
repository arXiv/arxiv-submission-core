
def bind_event(event_type: type):
    def deco(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return deco
