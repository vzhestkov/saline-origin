import contextlib


@contextlib.contextmanager
def enlock(lock):
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
