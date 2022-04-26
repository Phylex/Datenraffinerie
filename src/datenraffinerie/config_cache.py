import config_utilities as cfu
import functools


class DecoratorConfigCache():
    def __init__(self):
        """
        Make sure that the default state only has one entry per address
        and then initialize the cache. also
        """
        self.configuration = {}

    def load_default(self, default: dict) -> None:
        """
        load default state of the system into the
        cache to check against
        """
        self.configuration = default

    def write(self, write_func, protocol_object, config):
        diff = cfu.diff_dict(self.configuration, config)
        if diff is not None:
            self.configuration = cfu.update_dict(self.configuration, diff)
            write_func(protocol_object, diff)


def cache_write(Cache):
    def write_decorator(func):
        @functools.wraps(func)
        def write_wrapper(*args, **kwargs):
            return Cache.write(func, *args, **kwargs)
        return write_wrapper
    return write_decorator


class ConfigCache():
    def __init__(self):
        self.cache = {}

    def set_default(self, default: dict):
        self.cache = default

    def cache_write(self, config):
        diff = cfu.diff_dict(self.cache, config)
        if diff is not None:
            self.cache = cfu.update_dict(self.cache, diff)
            return diff


if __name__ == "__main__":
    testcache = DecoratorConfigCache()

    class protocol(object):
        def __init__(self):
            pass

        @cache_write(testcache)
        def write(self, config):
            print(f'Update actually written {config}')

    default = {'a': 1, 'b': 2, 'c': 3}
    update = {'a': 1, 'd': 4, 'b': 5}

    test = protocol()
    testcache.load_default(default)
    print(f'Default cache state: {default}')
    print(f'Uncached update: {update}')
    test.write(update)
