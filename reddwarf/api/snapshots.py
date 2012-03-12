#    Copyright 2012 OpenStack LLC
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

from webob import exc

from nova import log as logging
from nova.api.openstack import wsgi
from nova.notifier import api as notifier
from nova import utils
from nova import flags

from reddwarf import exception
from reddwarf.api import common
from reddwarf.api import deserializer
from reddwarf.api.views import snapshots
from reddwarf.guest import api as guest_api
from reddwarf.db import api as dbapi
from reddwarf.db import snapshot_state
from reddwarf.client import credential
from swiftapi import swift
import urlparse

LOG = logging.getLogger('reddwarf.api.snapshots')
LOG.setLevel(logging.DEBUG)

FLAGS = flags.FLAGS

def publisher_id(host=None):
    return notifier.publisher_id("reddwarf-api", host)

class Controller(object):
    def __init__(self):
        self.guestapi = guest_api.API()
        self.view = snapshots.ViewBuilder()
        super(Controller, self).__init__()

    def show(self, req, id):
        """ Returns a requested snapshot """
        LOG.info("Get snapshot %s" % id)
        LOG.debug("%s - %s", req.environ, req.body)
        db_snapshot = dbapi.db_snapshot_get(id)
        if not db_snapshot:
            return exc.HTTPNotFound()

        snapshot = self.view.build_single(db_snapshot, req)
        return { 'snapshot' : snapshot }

    def index(self, req):
        """ Returns a list of Snapshots for the Instance """
        LOG.info("List snapshots")
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']
        user_id = context.user_id

        instance_id = ''
        if req.query_string is not '':
            # returns list of tuples
            name_value_pairs = urlparse.parse_qsl(req.query_string,
                                         keep_blank_values=True,
                                         strict_parsing=False)
            for name_value in name_value_pairs:
                if name_value[0] == 'instanceId':
                    instance_id = name_value[1]
                    break

        if instance_id and len(instance_id) > 0:
            LOG.debug("Listing snapshots by instance_id %s", instance_id)
            snapshot_list = dbapi.db_snapshot_list_by_user_and_instance(context, user_id, instance_id)
        else:
            LOG.debug("Listing snapshots by user_id %s", user_id)
            snapshot_list = dbapi.db_snapshot_list_by_user(context, user_id)

        snapshots = [self.view.build_index(db_snapshot, req)
                    for db_snapshot in snapshot_list]

        return dict(snapshots=snapshots)

    def delete(self, req, id):
        """ Deletes a Snapshot """
        LOG.info("Delete snapshot with id %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']
        db_snapshot = dbapi.db_snapshot_get(id)

        if not db_snapshot:
            return exc.HTTPNotFound()

        uri = db_snapshot.storage_uri

        #Only delete from swift if we have a URI
        if uri and len(uri) > 0:
            container, file = uri.split('/',2)

            LOG.debug("Deleting from Container: %s - File: %s", container, file)

            ## TODO Move these to database!
            ST_AUTH=FLAGS.swiftclient_auth_url
            ST_USER=FLAGS.swiftclient_user
            ST_KEY=FLAGS.swiftclient_key

            opts = {'auth' : ST_AUTH,
                'user' : ST_USER,
                'key' : ST_KEY,
                'snet' : False,
                'prefix' : '',
                'auth_version' : '1.0'}
            try:
                swift.st_delete(opts, container, file)
            except Exception as e:
                exc.HTTPInternalServerError(e)

        # Mark snapshot deleted in DB
        dbapi.db_snapshot_delete(context, id)

        return exc.HTTPNoContent()

    def create(self, req, body):
        """ Creates a Snapshot """
        self._validate(body)
        instance_id = body['snapshot']['instanceId']
        name = body['snapshot']['name']
        LOG.info("Create Snapshot for instance %s", instance_id)
        LOG.debug("%s - %s", req.environ, req.body)

        context = req.environ['nova.context']

        # Generate UUID for Snapshot
        uuid = str(utils.gen_uuid())

        values = {
            'uuid' : uuid,
            'instance_uuid' : instance_id,
            'name' : name,
            'state' : snapshot_state.SnapshotState.INPROGRESS,
            'user_id' : context.user_id,
            'project_id' : context.project_id
            }

        ## TODO Move these to database!
        ST_AUTH=FLAGS.swiftclient_auth_url
        ST_USER=FLAGS.swiftclient_user
        ST_KEY=FLAGS.swiftclient_key

        # Add record to database
        db_snapshot = dbapi.db_snapshot_create(context, values)
        cred = credential.SwiftCredential(ST_USER, ST_KEY, ST_AUTH)
        self.guestapi.create_snapshot(context, instance_id, uuid, cred)
        snapshot = self.view.build_single(db_snapshot, req)
        return { 'snapshot' : snapshot }

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exception.BadRequest("The request contains an empty body")
        try:
            body['snapshot']
            body['snapshot']['instanceId']
            body['snapshot']['name']
        except KeyError as e:
            LOG.error("Create Snapshot Required field(s) - %s" % e)
            raise exception.BadRequest("Required element/key - %s was not specified" % e)

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            "snapshot": ["id", "state", "availabilityZone", "createdTime", "instanceId",
                      "engine", "engineVersion"],
            "link": ["rel", "href"],
            },
    }

    xmlns = {
        '1.0': common.XML_NS_V10,
    }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata, xmlns=xmlns),
    }

    deserializers = {
        'application/xml': deserializer.InstanceXMLDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(deserializers)
    return wsgi.Resource(controller, deserializer=request_deserializer, serializer=response_serializer)
