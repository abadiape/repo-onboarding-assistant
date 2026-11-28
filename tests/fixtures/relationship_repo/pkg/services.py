from .contracts import AbstractBase, Base, Storage as Store


def retry(function):
    return function


def _private():
    pass


@retry
@unknown_decorator(option=True)
class Service(Store, AbstractBase, Base, Missing):
    pass


registry.register(Service)
registry.register(Missing)
container.add(Service)
other.add(Service)
