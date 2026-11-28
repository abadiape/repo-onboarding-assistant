import os, pkg.models
from .models import (
    Order,
)
from missing_dependency import unknown


class Service:
    class Nested:
        async def run(self):
            import pkg.models

    def _helper(self):
        def inner():
            return None
        return inner
