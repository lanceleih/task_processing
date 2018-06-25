import time
from typing import List
from typing import Union

import addict
from pyrsistent import thaw

from task_processing.interfaces.event import Event
from task_processing.interfaces.event import task_event
from task_processing.plugins.mesos.config import MesosPodConfig
from task_processing.plugins.mesos.config import MesosTaskConfig
from task_processing.plugins.mesos.mesos_executor import ConfigType

# https://github.com/apache/mesos/blob/master/include/mesos/mesos.proto


def _make_mesos_command_info(task_config: MesosTaskConfig) -> addict.Dict:
    return addict.Dict(
        value=task_config.cmd,
        uris=[addict.Dict(value=uri, extract=False) for uri in task_config.uris],
        environment=addict.Dict(
            variables=[addict.Dict(name=k, value=v) for k, v in task_config.environment.items()],
        )
    )


def _make_mesos_container_info(task_config: MesosTaskConfig) -> addict.Dict:
    container_info = addict.Dict(
        type=task_config.containerizer,
        volumes=thaw(task_config.volumes),
    )
    port_mappings = [addict.Dict(host_port=task_config.ports[0].begin, container_port=8888)]
    if container_info.type == 'DOCKER':
        container_info.docker = addict.Dict(
            image=task_config.image,
            network='BRIDGE',
            port_mappings=port_mappings,
            parameters=thaw(task_config.docker_parameters),
            force_pull_image=(not task_config.use_cached_image),
        )
    elif container_info.type == 'MESOS':
        # container_info.network_infos = addict.Dict(port_mappings=port_mappings, protocol='IPv4')
        # if task_config.cni_network:
        #     container_info.network_infos.name = task_config.cni_network
        # For this to work, image_providers needs to be set to 'docker' on mesos agents (as opposed
        # to 'appc' or 'oci'; we're still running docker images, we're just using the UCR to do it).
        if 'image' in task_config:
            container_info.mesos.image = addict.Dict(
                type='DOCKER',  # not 'APPC' or 'OCI'
                docker=addict.Dict(name=task_config.image),
                cached=task_config.use_cached_image,
            )
    return container_info


def _make_mesos_executor_info(
    pod_config: MesosPodConfig,
    framework_id: str,
    role: str,
) -> addict.Dict:
    port_mappings = [addict.Dict(host_port=32000, container_port=8888)]
    return addict.Dict(
        type='DEFAULT',
        executor_id=addict.Dict(value=f'executor-{pod_config.task_id}'),
        framework_id=addict.Dict(value=framework_id),
        resources=_make_mesos_resources(pod_config, role),
        container=addict.Dict(
            type='MESOS',
            network_infos=addict.Dict(port_mappings=port_mappings,
                                      protocol='IPv4', name='yelp-compose'),
        ),
    )


def _make_mesos_resources(
    task_config: Union[MesosTaskConfig, MesosPodConfig],
    role: str,
) -> List[addict.Dict]:
    resource_list = [
        addict.Dict(
            name='cpus',
            type='SCALAR',
            role=role,
            scalar=addict.Dict(value=task_config.cpus),
        ),
        addict.Dict(
            name='mem',
            type='SCALAR',
            role=role,
            scalar=addict.Dict(value=task_config.mem)
        ),
        addict.Dict(
            name='disk',
            type='SCALAR',
            role=role,
            scalar=addict.Dict(value=task_config.disk)
        ),
        addict.Dict(
            name='gpus',
            type='SCALAR',
            role=role,
            scalar=addict.Dict(value=task_config.gpus)
        ),
    ]
    if task_config.ports:
        resource_list.append(addict.Dict(
            name='ports',
            type='RANGES',
            role=role,
            ranges=addict.Dict(range=thaw(task_config.ports)),
        ))
    return resource_list


def _make_mesos_task_info(
    task_config: MesosTaskConfig,
    agent_id: str,
    role: str,
) -> addict.Dict:
    return addict.Dict(
        task_id=addict.Dict(value=task_config.task_id),
        agent_id=addict.Dict(value=agent_id),
        name=f'executor-{task_config.task_id}',
        command=_make_mesos_command_info(task_config),
        container=_make_mesos_container_info(task_config),
        resources=_make_mesos_resources(task_config, role),
    )


def make_mesos_task_operation(
    task_config: ConfigType,
    *,
    agent_id: str,
    framework_id: str,
    role: str,
) -> addict.Dict:
    return addict.Dict(
        type='LAUNCH',
        launch=addict.Dict(
            task_infos=_make_mesos_task_info(task_config, agent_id, role),
        ),
    )


def make_mesos_pod_operation(
    pod_config: ConfigType,
    *,
    agent_id: str,
    framework_id: str,
    role: str,
) -> addict.Dict:
    task_infos = [
        _make_mesos_task_info(task_config, agent_id, role)
        for task_config in pod_config.tasks
    ]

    return addict.Dict(
        type='LAUNCH_GROUP',
        launch_group=addict.Dict(
            executor=_make_mesos_executor_info(pod_config, framework_id, role),
            task_group=addict.Dict(tasks=task_infos),
        )
    )


MESOS_STATUS_MAP = {
    'TASK_STARTING':
    addict.Dict(platform_type='starting', terminal=False),
    'TASK_RUNNING':
    addict.Dict(platform_type='running', terminal=False),
    'TASK_FINISHED':
    addict.Dict(platform_type='finished', terminal=True, success=True),
    'TASK_FAILED':
    addict.Dict(platform_type='failed', terminal=True, success=False),
    'TASK_KILLED':
    addict.Dict(platform_type='killed', terminal=True, success=False),
    'TASK_LOST':
    addict.Dict(platform_type='lost', terminal=True, success=False),
    'TASK_STAGING':
    addict.Dict(platform_type='staging', terminal=False),
    'TASK_ERROR':
    addict.Dict(platform_type='error', terminal=True, success=False),
    'TASK_KILLING':
    addict.Dict(platform_type='killing', terminal=False),
    'TASK_DROPPED':
    addict.Dict(platform_type='dropped', terminal=True, success=False),
    'TASK_UNREACHABLE':
    addict.Dict(platform_type='unreachable', terminal=False),
    'TASK_GONE':
    addict.Dict(platform_type='gone', terminal=True, success=False),
    'TASK_GONE_BY_OPERATOR':
    addict.Dict(platform_type='gone_by_operator', terminal=True, success=False),
    'TASK_UNKNOWN':
    addict.Dict(platform_type='unknown', terminal=False)
}


def mesos_update_to_event(mesos_status: addict.Dict, task_config: ConfigType) -> Event:
    kwargs = dict(
        raw=mesos_status,
        task_id=task_config.task_id,
        task_config=task_config,
        timestamp=time.time(),
    )
    kwargs.update(MESOS_STATUS_MAP[mesos_status.state])
    return task_event(**kwargs)
