import abc
import uuid

import six
from pyrsistent import field
from pyrsistent import PRecord
from pyrsistent import PVector
from pyrsistent import pvector
from pyrsistent import v


class TaskConfig(PRecord):
    uuid = field(type=uuid.UUID, initial=uuid.uuid4)
    name = field(type=str, initial="default")
    image = field(type=str, initial="ubuntu:xenial")
    cmd = field(type=str, initial="/bin/true")
    cpus = field(type=float,
                 initial=0.1,
                 invariant=lambda c: (c > 0, 'cpus > 0'))
    mem = field(type=float,
                initial=32.0,
                invariant=lambda m: (m >= 32, 'mem is >= 32'))
    disk = field(type=float,
                 initial=10.0,
                 invariant=lambda d: (d > 0, 'disk > 0'))
    volumes = field(type=PVector, initial=v(), factory=pvector)
    ports = field(type=PVector, initial=v(), factory=pvector)
    cap_add = field(type=PVector, initial=v(), factory=pvector)
    ulimit = field(type=PVector, initial=v(), factory=pvector)
    # TODO: containerization + containerization_args ?
    docker_parameters = field(type=PVector, initial=v(), factory=pvector)

    def task_id(self):
        return "{}.{}".format(self.name, str(self.uuid))


@six.add_metaclass(abc.ABCMeta)
class TaskExecutor(object):
    @abc.abstractmethod
    def run(self, task_config):
        pass

    @abc.abstractmethod
    def kill(self, task_id):
        pass
