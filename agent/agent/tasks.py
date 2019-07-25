from .runner import AsyncProcessRunner
from .foo import FooProcess

AsyncProcessRunner.prepare(FooProcess)
