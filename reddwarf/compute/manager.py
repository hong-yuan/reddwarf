# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Openstack, LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json

from nova import flags
from nova import log as logging
from nova import exception
from nova import utils
from nova.compute import vm_states
from nova.compute import power_state
from nova.compute.manager import ComputeManager
from nova.notifier import api as notifier
from nova.volume import api as volume_api

from reddwarf import guest
from reddwarf.db import api as dbapi


flags.DEFINE_integer('reddwarf_guest_initialize_time_out', 10 * 60,
                     'Time in seconds for a guest to initialize before it is '
                     'considered a failure and aborted.')
flags.DEFINE_integer('reddwarf_instance_suspend_time_out', 3 * 60,
                     'Time in seconds for a compute instance to suspend '
                     'during when aborted before a PollTimeOut is raised.')
flags.DEFINE_integer('reddwarf_volume_time_out', 10 * 60,
                     'Time in seconds for an instance to wait for a volume '
                     'to be provisioned before aborting.')

FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)
VALID_ABORT_STATES = [
    power_state.CRASHED,
    power_state.FAILED,
    power_state.PAUSED,
    power_state.SUSPENDED,
    power_state.SHUTDOWN
]


def publisher_id(host=None):
    return notifier.publisher_id("reddwarf-compute", host)


class ReddwarfInstanceMetaData(object):
    """Represents standard Reddwarf instance metadata."""

    def __init__(self, db, context, instance_id):
        """Populates volume, volume_mount_point and databases properties."""
        metadata = db.instance_metadata_get(context, instance_id)
        # There shouldn't be exceptions coming from below mean the instances
        # REST API is misbehaving and sending invalid data.
        # Grabs the volume for this instance with its mount_point, or None.
        self.volume_id = int(metadata['volume_id'])
        self.volume = db.volume_get(context, self.volume_id)
        self.volume_mount_point = metadata.get('mount_point',
                                               "/mnt/" + str(self.volume_id))
        # Get the databases to create along with this instance.
        self.databases = json.loads(metadata['database_list'])


class ReddwarfInstanceInitializer(object):
    """Handles the provisioning of an instance.

    Also keeps "context" and "instance_id" and a few others (like volume_id,
    simply for error reporting) from appearing all over the place.
    Think of this as a child class of the ComputeManager below. It exists for
    a single call to run_instance and builds the instance.

    """

    def __init__(self, compute_manager, db, context, instance_id,
                 volume_id=None, volume=None, volume_mount_point=None,
                 databases=None):
        """Creates a new instance."""
        self.db = db
        self.context = context
        self.instance_id = instance_id
        self.volume_id = volume_id
        self.volume = volume
        self.volume_mount_point = volume_mount_point
        self.databases = databases
        self.compute_manager = compute_manager
        self.volume_api = volume_api.API()

    def _abort_guest_install(self):
        """Sets the guest state to FAIL continuously until an instance is known
         to have been suspended, or raises a PollTimeOut exception."""
        self._set_instance_status_to_fail()
        LOG.audit(_("Aborting db instance %d.") % self.instance_id,
                  context=self.context)
        self.compute_manager.suspend_instance(self.context, self.instance_id)

        # Wait for the state has become suspended so we know the guest won't
        # wake up and change its state. All the while until the end, set
        # the state to failed (in reality the suspension should occur quickly
        # and normally we will not be aborting because we didn't wait
        # long enough).

        def get_instance_state():
            return self.db.instance_get(self.context, self.instance_id).power_state

        def confirm_state_is_suspended(instance_state):
            # Make sure the guest state is set to FAILED after suspend, in
            # case it wakes up and tries anything here.
            self._set_instance_status_to_fail()
            return instance_state in VALID_ABORT_STATES

        utils.poll_until(get_instance_state,
                         confirm_state_is_suspended,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_instance_suspend_time_out)
        self._abort_volume()

    def _abort_volume(self):
        """Detach the volume that was created for an instance that is going to
        be aborted, due to errors. The volume will be detached and available.
        It will get reaped eventually."""
        self.compute_manager._detach_volume(self.context, self.instance_id,
                                            self.volume_id, False)

    def _ensure_volume_is_ready(self, volume_api, volume_client, host):
        self.wait_until_volume_is_ready(FLAGS.reddwarf_volume_time_out)
        #TODO(tim.simpson): This may not be able to be the self.host name.
        # Needs to be something that can identify the compute node.
        volume_client.initialize(self.context, self.volume_id, host)
        self.db.volume_attached(self.context, self.volume_id,
                                self.instance_id, self.volume_mount_point)
        volume_api.update(self.context, self.volume_id, {})

    def initialize_guest(self, guest_api):
        """Tell the guest to initialize itself and wait for it to happen.

        This method aborts the guest if there's a timeout.

        """
        try:
            guest_api.prepare(self.context, self.instance_id,
                                          self.databases)
            utils.poll_until(lambda : dbapi.guest_status_get(self.instance_id),
                             lambda status : status.state == power_state.RUNNING,
                             sleep_time=2,
                             time_out=FLAGS.reddwarf_guest_initialize_time_out)
            LOG.info("Guest is now running on instance %s" % self.instance_id)
            return True
        except utils.PollTimeOut as pto:
            self._notify_of_failure(
                exception=pto,
                event_type='reddwarf.instance.abort.guest',
                audit_msg=_("Aborting instance %(instance_id)d because the "
                            "guest did not initialize."))
            self._abort_guest_install()
            return False

    def initialize_compute_instance(self, **kwargs):
        """Runs underlying compute instance and aborts if any errors occur."""
        try:
            self.compute_manager.run_instance(self.context,
                                              self.instance_id, **kwargs)
            return True
        except Exception as exception:
            self._notify_of_failure(exception=exception,
                event_type='reddwarf.instance.abort.compute',
                audit_msg=_("Aborting instance %(instance_id)d because the "
                            "underlying compute instance failed to run."))
            self._abort_guest_install()
            return False

    def initialize_volume(self, volume_api, volume_client,
                          host):
        try:
            self._ensure_volume_is_ready(volume_api, volume_client, host)
            return True
        except Exception as exception:
            self._set_instance_status_to_fail()
            # If we call suspend, the compute driver throws an error because
            # it can't find the instance, since it does not yet exist...
            #self.compute_manager.suspend_instance(self.context,
            #                                      self.instance_id)
            # ... so we have to duplicate some code from the Compute manager.
            self.compute_manager._instance_update(self.context,
                                              self.instance_id,
                                              power_state=power_state.SHUTOFF,
                                              vm_state=vm_states.SUSPENDED,
                                              task_state=None)
            self._notify_of_failure(exception=exception,
                event_type='reddwarf.instance.abort.volume',
                audit_msg=_("Aborting instance %(instance_id)d because "
                            "volume %(volume_id)dfailed to provision."))
            return False

    def _notify_of_failure(self, event_type, exception, audit_msg):
        """Logs message / sends notification that an instance has failed."""
        LOG.error(exception)
        err_values = { 'instance_id':self.instance_id,
                       'volume_id':self.volume_id }
        LOG.audit(audit_msg % err_values, context=self.context)
        notifier.notify(publisher_id(), event_type, notifier.ERROR, err_values)

    def _set_instance_status_to_fail(self):
        """Sets the instance to FAIL."""
        dbapi.guest_status_update(self.instance_id, power_state.FAILED)

    def wait_until_volume_is_ready(self, time_out):
        """Sleeps until the given volume has finished provisioning."""
        def volume_is_available():
            volume = self.db.volume_get(self.context, self.volume_id)
            status = volume['status']
            if status == 'creating':
                return False
            elif status == 'available':
                return True
            elif status != 'available':
                LOG.error("STATUS: %s" % status)
                raise exception.VolumeProvisioningError(
                    volume_id=self.volume_id)
        utils.poll_until(volume_is_available, sleep_time=1, time_out=time_out)

class ReddwarfComputeManager(ComputeManager):
    """Manages the running Reddwarf instances."""

    def __init__(self, *args, **kwargs):
        super(ReddwarfComputeManager, self).__init__(*args, **kwargs)
        self.guest_api = guest.API()
        self.compute_manager = super(ReddwarfComputeManager, self)

    def run_instance(self, context, instance_id, **kwargs):
        """Launch a new instance with specified options.

        Reddwarf instances are a bit more complex than plain Nova compute
        instances. We're overriding ComputeManager for tactical reasons as
        this is the only way to make sure the extra provisioning actions
        occur when the REST API is called.

        """
        metadata = ReddwarfInstanceMetaData(self.db, context, instance_id)
        instance = ReddwarfInstanceInitializer(self.compute_manager, self.db,
            context, instance_id, metadata.volume_id, metadata.volume,
            metadata.volume_mount_point, metadata.databases)
        # If any steps return False, cancel subsequent steps.
        (instance.initialize_volume(self.volume_api,
                                    self.volume_client, self.host) and
         instance.initialize_compute_instance(**kwargs) and
         instance.initialize_guest(self.guest_api))

    def terminate_instance(self, context, instance_id):
        """Terminate the instance and also delete all the attached volumes"""
        volumes = None
        try:
            volumes = self.db.volume_get_all_by_instance(context, instance_id)
        except exception.VolumeNotFoundForInstance:
            LOG.info("Skipping as no volumes are associated with the instance")

        self.compute_manager.terminate_instance(context, instance_id)

        for volume in volumes:
            self.volume_api.delete_volume_when_available(context,
                                                         volume['id'],
                                                         time_out=60)
