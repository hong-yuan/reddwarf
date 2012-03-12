#    Copyright 2011 OpenStack LLC
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
'''
Created on Feb 22, 2012

@author: vipul
'''
import os


from nova import log as logging
from nova.api.openstack import common as nova_common
from nova.compute import power_state
from nova.exception import InstanceNotFound

from reddwarf.api import common
from reddwarf.db.snapshot_state import SnapshotState
from reddwarf.util.enum import Enum

LOG = logging.getLogger('reddwarf.api.views.snapshot')
LOG.setLevel(logging.DEBUG)


def _project_id(req):
    return getattr(req.environ['nova.context'], 'project_id', '')


def _base_url(req):
    return req.application_url


class ViewBuilder(object):
    """Views for a Snapshot"""

    def _build_basic(self, db_snapshot, req):
        """Build the very basic information for an snapshot"""
        snapshot = {}
        snapshot['id'] = db_snapshot.uuid
        snapshot['name'] = db_snapshot.name
        snapshot['created'] = db_snapshot.created_at
        snapshot['instanceId'] = db_snapshot.instance_uuid
        snapshot['links'] = self._build_links(req, db_snapshot)
        return snapshot

    def _build_detail(self, db_snapshot, snapshot):
        snapshot['status'] = Enum.valueOf(SnapshotState, db_snapshot.state)
        return snapshot

    @staticmethod
    def _build_links(req, db_snapshot):
        """Build the links for the snapshot"""
        base_url = _base_url(req)
        href = os.path.join(base_url, _project_id(req),
                            "snapshots", str(db_snapshot.uuid))
        bookmark = os.path.join(nova_common.remove_version_from_href(base_url),
                                "snapshots", str(db_snapshot.uuid))
        links = [
            {
                'rel': 'self',
                'href': href
            },
            {
                'rel': 'bookmark',
                'href': bookmark
            }
        ]
        return links

    def build_index(self, db_snapshot, req):
        """Build the response for an snapshot index call"""
        return self._build_basic(db_snapshot, req)

    def build_single(self, db_snapshot, req):
        """Build the response for a snapshot detail call"""
        snapshot = self._build_basic(db_snapshot, req)
        snapshot = self._build_detail(db_snapshot, snapshot)
        return snapshot

    @staticmethod
    def get_instance_status(server, guest_states):
        """Figures out what the instance status should be.

        First looks at the server status, then to a dictionary mapping guest
        IDs to their states.

        """
        if server.status == 'ERROR':
            return 'ERROR'
        else:
            try:
                state = guest_states[server.id]
                #state = server.status
            except (KeyError, InstanceNotFound):
                # we set the state to shutdown if not found
                state = power_state.SHUTDOWN
            return common.dbaas_mapping.get(state, None)
