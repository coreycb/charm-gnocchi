# Copyright 2017 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import charms_openstack.charm as charm
import charms.reactive as reactive

import charm.openstack.gnocchi as gnocchi  # noqa

import charmhelpers.contrib.storage.linux.ceph as ceph_helper
import charmhelpers.core.hookenv as hookenv

charm.use_defaults(
    'charm.installed',
    'shared-db.connected',
    'identity-service.connected',
    'identity-service.available',  # enables SSL support
    'config.changed',
    'update-status')

required_interfaces = ['coordinator-memcached.available',
                       'shared-db.available',
                       'identity-service.available',
                       'storage-ceph.pools.available']


@reactive.when_not_all(*required_interfaces)
def disable_services():
    with charm.provide_charm_instance() as charm_class:
        charm_class.disable_services()


@reactive.when(*required_interfaces)
def render_config(*args):
    """Render the configuration for charm when all the interfaces are
    available.
    """
    with charm.provide_charm_instance() as charm_class:
        charm_class.enable_services()
        charm_class.render_with_interfaces(args)
        charm_class.enable_webserver_site()
        charm_class.assess_status()
    reactive.set_state('config.rendered')


# db_sync checks if sync has been done so rerunning is a noop
@reactive.when('config.rendered')
def init_db():
    with charm.provide_charm_instance() as charm_class:
        charm_class.db_sync()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as charm_class:
        charm_class.configure_ha_resources(hacluster)
        charm_class.assess_status()


@reactive.when('storage-ceph.connected')
def storage_ceph_connected(ceph):
    ceph.create_pool(hookenv.service_name())


@reactive.when('storage-ceph.available')
def configure_ceph(ceph):
    ceph_helper.ensure_ceph_keyring(service=hookenv.service_name(),
                                    key=ceph.key(),
                                    user='gnocchi',
                                    group='gnocchi')


@reactive.when_not('storage-ceph.connected')
def storage_ceph_disconnected():
    ceph_helper.delete_keyring(hookenv.service_name())


@reactive.when('metric-service.connected')
@reactive.when('config.rendered')
def provide_gnocchi_url(metric_service):
    with charm.provide_charm_instance() as charm_class:
        metric_service.set_gnocchi_url(charm_class.public_url)
