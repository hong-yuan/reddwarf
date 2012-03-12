# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Hewlett-Packard Development Company, L.P.
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

# Copyright 2010 OpenStack LLC.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import logging
import json
import os
from webob import exc

from nova import compute
from nova import db
from nova import exception as nova_exception
from nova import flags
#from nova import log as logging
from nova import volume
from nova import utils
from nova.api.openstack import common as nova_common
from nova.api.openstack import faults
from nova.api.openstack import servers
from nova.api.openstack import wsgi
from nova.compute import power_state
from smartagent import result_state
from nova.notifier import api as notifier

from novaclient.v1_1 import servers as novaclientservers
from novaclient import exceptions as novaclient_exceptions
import novaclient

from reddwarf import exception
from reddwarf.api import common
from reddwarf.api import deserializer
from reddwarf.api.views import instances
from reddwarf.db import api as dbapi
from reddwarf.guest import api as guest_api
from reddwarf.client import osclient

logging.basicConfig()

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS
#flags.DEFINE_string('reddwarf_mysql_data_dir', '/var/lib/mysql',
# 'Mount point within the instance for MySQL data.')
#flags.DEFINE_string('reddwarf_volume_description',
# 'Volume ID: %s assigned to Instance: %s',
# 'Default description populated for volumes')
#flags.DEFINE_integer('reddwarf_max_accepted_volume_size', 128,
# 'Maximum accepted volume size (in gigabytes) when creating'
# ' an instance.')


def publisher_id(host=None):
    return notifier.publisher_id("reddwarf-api", host)


class Controller(object):
    """ The Instance API controller for the Platform API """

    def __init__(self):
        self.compute_api = compute.API()
        self.guest_api = guest_api.API()
        self.server_controller = servers.ControllerV11()
        self.volume_api = volume.API()
        self.view = instances.ViewBuilder()
        self.client = osclient.OSClient(FLAGS.novaclient_account_id,
            FLAGS.novaclient_access_key,
            FLAGS.novaclient_project_id,
            FLAGS.novaclient_auth_url,
            FLAGS.novaclient_region_name)
        super(Controller, self).__init__()

    def index(self, req):
        """ Returns a list of instance names and ids for a given user """
        LOG.info("Call to Instances index")

        context = req.environ['nova.context']

        instance_list = db.api.instance_get_all_by_user(context, context.user_id)

        #servers_respose = self.server_controller.index(req)
        #server_list = servers_response['servers']
        #context = req.environ['nova.context']
        # Instances need the status for each instance in all circumstances,
        # unlike servers.
        server_states = db.instance_state_get_all_filtered(context)
        for instance in instance_list:
            state = server_states[instance['id']]
            instance['status'] = nova_common.status_from_state(state)

        id_list = [instance['internal_id'] for instance in instance_list]
        guest_state_mapping = self.get_guest_state_mapping(id_list)
        instances = [self.view.build_index(instance, req, guest_state_mapping)
                     for instance in instance_list]
        return {'instances': instances}

    def detail(self, req):
        """ Returns a list of instance details for a given user """
        LOG.debug("%s - %s", req.environ, req.body)
        server_list = self.server_controller.detail(req)['servers']
        id_list = [server['id'] for server in server_list]
        guest_state_mapping = self.get_guest_state_mapping(id_list)
        instances = [self.view.build_detail(server, req, guest_state_mapping)
                     for server in server_list]
        return {'instances': instances}

    def show(self, req, id):
        """ Returns instance details by instance id """
        LOG.info("Get Instance by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)

        db_instance = dbapi.instance_from_uuid(id)
        if not db_instance:
            return exc.HTTPNotFound()

        remote_id = db_instance.internal_id
        guest_state = self.get_guest_state_mapping([remote_id])

        instance = self.view.build_single(db_instance, req, guest_state)

        LOG.debug("instance - %s" % instance)
        return {'instance': instance}

    def delete(self, req, id):
        """ Destroys an instance """
        LOG.info("Delete Instance by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)

        internal_id = dbapi.internalid_from_uuid(id)
        LOG.debug("Remote ID: " + str(internal_id))
        if not internal_id:
            return exc.HTTPNotFound()

        LOG.debug("Deleting instance %d" % int(internal_id))
        try:
            self.client.delete(internal_id)
        except novaclient_exceptions.NotFound as e:
            LOG.debug("Delete: instance not found")
            #print str(e)
            return exc.HTTPNotFound(e)
        except Exception, e:
            LOG.debug("Delete: internal server error")
            LOG.debug(e)
            return exc.HTTPInternalServerError()

        dbapi.instance_delete(id)
        return exc.HTTPAccepted()


    def create(self, req, body):
        """ Creates a new Instance for a given user """
        self._validate(body)

        LOG.info("Create Instance")
        LOG.debug("%s - %s", req.environ, body)

        context = req.environ['nova.context']
        LOG.debug(" BODY Instance Name: " + body['instance']['name'])

        instance_name = body['instance']['name']

        # Generate a UUID and set as the hostname, to guarantee unique
        # routing key for Agent
        host_name = str(utils.gen_uuid());

        # This should be fetched from Flags, image should contain mysqld and agent
        image_id = FLAGS.default_image
        flavor_ref = FLAGS.default_instance_type

        storage_uri = None
        if 'snapshotId' in body['instance']:
            snapshot_id = body['instance']['snapshotId']
            if snapshot_id and len(snapshot_id) > 0:
                db_snapshot = dbapi.db_snapshot_get(snapshot_id)
                storage_uri = db_snapshot.storage_uri
                LOG.debug("Found Storage URI for snapshot: %s" % storage_uri)

        # Create the Server remotely
        server_resp = self._try_create_server(req, host_name, image_id, flavor_ref, storage_uri)

        # Capture response values
        instance_id = server_resp.uuid
        remote_id = str(server_resp.id)

        LOG.info("Created server with uuid: " + instance_id + " and remote id: " + remote_id)

        # Create DB Entry
        db_instance = dbapi.instance_create(context.user_id, context.project_id, instance_name, server_resp)

        # Need to assign public IP, but also need to wait for Networking
        ip = self.client.assign_public_ip(remote_id)

        dbapi.instance_set_public_ip(instance_id, ip)
        dbapi.guest_status_create(remote_id)

        # Nova doesn't populate the public IP in the server Response
        #server_resp.accessIPv4 = ip
        #print server_resp.accessIPv4
        #server_resp.name = instance_name

        db_instance.access_ip_v4 = ip

        guest_state = self.get_guest_state_mapping([remote_id])
        instance = self.view.build_single(db_instance, req, guest_state, create=True)

        return { 'instance': instance }

    def restart_compute_instance(self, req, instance_id):
        """Restarts a compute instance by ID"""
        LOG.info("Restart Compute Instance by ID - %s", instance_id)
        LOG.debug("%s - %s", req.environ, req.body)

        context = req.environ['nova.context']
        remote_id = dbapi.internalid_from_uuid(instance_id)
        LOG.debug("Remote ID: " + str(remote_id))

        server_response = self.client.restart(remote_id)
        print server_response

        server_response = self.client.show(instance_id)
        LOG.info("Called OSClient.restart().  Response: %s", server_response)

        if 'rebooting' not in server_response.status:
            raise exception.InstanceFault("There was a problem restarting" +\
                " this instance.  If this problem persists, please" +\
                " contact Customer Support.")

        return exc.HTTPAccepted()

    def reset_db_password(self, req, instance_id):
        """Resets DB password on remote instance"""
        LOG.info("Resets DB password on Instance %s", instance_id)
        password = utils.generate_password()
        context = req.environ['nova.context']
        result = self.guest_api.reset_password(context, instance_id, password)
        if result == result_state.ResultState.SUCCESS:
            return {'password': password}
        else:
            LOG.debug("Smart Agent failed to reset password (RPC response: '%s').",
                result_state.ResultState.name(result))
            return exc.HTTPInternalServerError("Smart Agent failed to reset password.")

    @staticmethod
    def get_guest_state_mapping(id_list):
        """Returns a dictionary of guest statuses keyed by guest ids."""
        results = dbapi.guest_status_get_list(id_list)
        return dict([(r.instance_id, r.state) for r in results])

    def create_volume(self, context, body):
        """Creates the volume for the instance and returns its ID."""
        volume_size = body['instance']['volume']['size']
        name = body['instance'].get('name', None)
        description = FLAGS.reddwarf_volume_description % (None, None)

        return self.volume_api.create(context, size=volume_size,
            snapshot_id=None,
            name=name,
            description=description)

    def _try_create_server(self, req, instance_name, image_id, flavor_ref, snapshot_uri=None):
        """Handle the call to create a server through novaclient.

Separating this so we could do retries in the future and other
processing of the result etc.
"""
        try:
            # Default SecurityGroup to use for instances
            sec_group = FLAGS.default_firewall_rule_name

            conf_file = '[messaging]\n'\
                        'rabbit_host: ' + FLAGS.rabbit_host + '\n'\
                        '\n'\
                        '[database]\n'\
                        'initial_password: ' + utils.generate_password(length=8)

            if snapshot_uri and len(snapshot_uri) > 0:
                conf_file = conf_file + '\n'\
                               '[snapshot]\n'\
                               'snapshot_uri: ' + snapshot_uri + '\n'\
                               'swift_auth_url: ' + FLAGS.swiftclient_auth_url + '\n'\
                               'swift_auth_user: ' + FLAGS.swiftclient_user + '\n'\
                               'swift_auth_key: ' + FLAGS.swiftclient_key + '\n'

            LOG.debug('%s',conf_file)

            files = { '/home/nova/agent.config': conf_file }
            #files = None
            userdata = None
            init_script = FLAGS.instance_initscript
            if init_script and len(init_script) > 0:
                #cwd = os.getcwd()
                #print ( cwd )
                #init_script_fqn = os.path.join(cwd, init_script)
                userdata = open(init_script)

            keypair = FLAGS.instance_keypair_default

            server = self.client.create(instance_name, image_id, flavor_ref, files, keypair, [sec_group], userdata)

            #server = self.server_controller.create(req, body)
            if not server or isinstance(server, faults.Fault)\
            or isinstance(server, exc.HTTPClientError):
                if isinstance(server, faults.Fault):
                    LOG.error("%s: %s", server.wrapped_exc,
                        server.wrapped_exc.detail)
                if isinstance(server, exc.HTTPClientError):
                    LOG.error("a 400 error occurred %s" % server)
                raise exception.InstanceFault("Could not complete the request."
                                              " Please try again later or contact Customer Support")
            return server
        except (TypeError, AttributeError, KeyError) as e:
            LOG.error(e)
            raise exception.UnprocessableEntity()

    @staticmethod
    def _create_server_dict(instance, volume_id, mount_point):
        """Creates a server dict from the request instance dict."""
        server = copy.copy(instance)
        # Append additional stuff to create.
        # Add image_ref
        try:
            server['imageRef'] = dbapi.config_get("reddwarf_imageref").value
        except nova_exception.ConfigNotFound:
            msg = "Cannot find the reddwarf_imageref config value, "\
                  "using default of 1"
            LOG.warn(msg)
            notifier.notify(publisher_id(), "reddwarf.image", notifier.WARN,
                msg)
            server['imageRef'] = 1
            # Add security groups
        security_groups = [{'name': FLAGS.default_firewall_rule_name}]
        server['security_groups'] = security_groups
        # Add volume id
        if not 'metadata' in instance:
            server['metadata'] = {}
        server['metadata']['volume_id'] = str(volume_id)
        # Add mount point
        server['metadata']['mount_point'] = str(mount_point)
        # Add databases
        # We create these once and throw away the result to take advantage
        # of the validators.
        db_list = common.populate_databases(instance.get('databases', []))
        server['metadata']['database_list'] = json.dumps(db_list)
        return server

    def _setup_security_groups(self, context, group_name, port):
        """ Setup a default firewall rule for reddwarf.

We are using the existing infrastructure of security groups in nova
used by the ec2 api and piggy back on it. Reddwarf by default will have
one rule which will allow access to the specified tcp port, the default
being 3306 from anywhere. For this the group_id and parent_id are the
same, we are not doing any hierarchical rules yet.
Here's how it would look in iptables.

-A nova-compute-inst-<id> -p tcp -m tcp --dport 3306 -j ACCEPT
"""
        self.compute_api.ensure_default_security_group(context)

        if not db.security_group_exists(context, context.project_id,
            group_name):
            LOG.debug('Creating a new firewall rule %s for project %s'
            % (group_name, context.project_id))
            values = {'name': group_name,
                      'description': group_name,
                      'user_id': context.user_id,
                      'project_id': context.project_id}
            security_group = db.security_group_create(context, values)
            rules = {'group_id': security_group['id'],
                     'parent_group_id': security_group['id'],
                     'cidr': '0.0.0.0/0',
                     'protocol': 'tcp',
                     'from_port': port,
                     'to_port': port}
            db.security_group_rule_create(context, rules)
            self.compute_api.trigger_security_group_rules_refresh(context,
                security_group['id'])

    def _get_guest_info(self, context, id, state):
        """Get the list of databases on a instance"""
        running = common.dbaas_mapping[power_state.RUNNING]
        if common.dbaas_mapping.get(state, None) == running:
            try:
                result = self.guest_api.list_databases(context, id)
                LOG.debug("LIST DATABASES RESULT - %s", str(result))
                databases = [{'name': db['_name'],
                              'collate': db['_collate'],
                              'character_set': db['_character_set']}
                for db in result]
                root_enabled = self.guest_api.is_root_enabled(context, id)
                return databases, root_enabled
            except Exception as err:
                LOG.error(err)
                LOG.error("guest not responding on instance %s" % id)
                #TODO(cp16net) we have hidden the actual exception by returning [],None
        return [], None

    @staticmethod
    def _validate(body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exception.BadRequest("The request contains an empty body")

        try:
            body['instance']
            body['instance']['flavorRef']
#            try:
#                volume_size = float(body['instance']['volume']['size'])
#            except (ValueError, TypeError) as e:
#                LOG.error("Create Instance Required field(s) - "
#                          "['instance']['volume']['size']")
#                raise exception.BadRequest("Required element/key - instance "
#                                           "volume 'size' was not specified as a number")
#            if int(volume_size) != volume_size or int(volume_size) < 1:
#                raise exception.BadRequest("Volume 'size' needs to be a "
#                                           "positive integer value, %s cannot be accepted."
#                % volume_size)
#            max_size = FLAGS.reddwarf_max_accepted_volume_size
#            if int(volume_size) > max_size:
#                raise exception.BadRequest("Volume 'size' cannot exceed maximum "
#                                           "of %d Gb, %s cannot be accepted."
#                % (max_size, volume_size))
        except KeyError as e:
            LOG.error("Create Instance Required field(s) - %s" % e)
            raise exception.BadRequest("Required element/key - %s was not "
                                       "specified" % e)


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
        }[version]()

    metadata = {
        'attributes': {
            'instance': ['created', 'hostname', 'id', 'name', 'rootEnabled',
                         'status', 'updated'],
            'dbtype': ['name', 'version'],
            'flavor': ['id'],
            'link': ['rel', 'href'],
            'volume': ['size'],
            'database': ['name', 'collate', 'character_set'],
            },
        }

    xmlns = {
        '1.0': common.XML_NS_V10,
        }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata,
            xmlns=xmlns),
        }

    deserializers = {
        'application/xml': deserializer.InstanceXMLDeserializer(),
        }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(deserializers)
    return wsgi.Resource(controller, deserializer=request_deserializer,
        serializer=response_serializer)
