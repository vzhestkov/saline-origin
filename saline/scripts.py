import sys


def saline_daemon():
    """
    Start the Saline.
    """

    import saline.daemon

    # Fix for setuptools generated scripts, so that it will
    # work with multiprocessing fork emulation.
    # (see multiprocessing.forking.get_preparation_data())
    if __name__ != "__main__":
        sys.modules["__main__"] = sys.modules[__name__]

    saline = saline.daemon.Saline()
    saline.start()
