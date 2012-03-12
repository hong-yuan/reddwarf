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
"""
Tests for Instances API calls
"""

import mox
import json
import stubout
import webob
from paste import urlmap

import nova
from nova import context
from nova import test
from nova.compute import vm_states
from nova.compute import power_state
import nova.exception as nova_exception


import reddwarf
import reddwarf.exception as exception
from reddwarf.api import instances
from reddwarf.db import models
from reddwarf.tests import util

#instances_url = util.v1_instances_prefix
instances_url = r"/v1.0/dbaas/instances"

def localid_from_uuid(id):
    return id

def internalid_from_uuid(id):
    return id

def instance_delete(id):
    return

def compute_get_osclient_not_found(osclient, id):
    return webob.exc.HTTPNotFound()

def compute_get_osclient_unprocessable(osclient, id):
    raise exception.UnprocessableEntity()

def compute_get_osclient_accepted(osclient, id):
    return

def request_obj(url, method, body=None):
    req = webob.Request.blank(url)
    req.method = method
    if method in ['POST', 'PUT'] and body:
        req.body = json.dumps(body)
    print req
    req.headers["content-type"] = "application/json"
    return req

def get_osclient_show_deleting(osclient, id):
    response = DummyServer()
    response.status += "(deleting)"
    return response

def get_osclient_show_restarting(osclient, id):
    response = DummyServer()
    response.status += "(rebooting)"
    return response

class DummyServer(object):

    def __init__(self):
        self.id = 11111
        self.status = "ACTIVE "

class InstanceApiTest(test.TestCase):
    """Test various Database API calls"""

#    def setUp(self):
#        super(InstanceApiTest, self).setUp()
#        self.context = context.get_admin_context()
#        self.controller = instances.Controller()
#        self.stubs.Set(reddwarf.db.api, "localid_from_uuid", localid_from_uuid)
#
#    def tearDown(self):
#        self.stubs.UnsetAll()
#        super(InstanceApiTest, self).tearDown()
#
#    def test_instances_delete_not_found(self):
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "delete", compute_get_osclient_not_found)
#        self.stubs.Set(reddwarf.db.api, "instance_delete", instance_delete)
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "show", get_osclient_show_deleting)
#        self.stubs.Set(reddwarf.db.api, "internalid_from_uuid", internalid_from_uuid)
#        req = request_obj('%s/1' % instances_url, 'DELETE')
#        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
#        self.assertEqual(res.status_int, 404)

#    def test_instances_delete_unprocessable(self):
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "delete", compute_get_osclient_unprocessable)
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "show", get_osclient_show_deleting)
#        self.stubs.Set(reddwarf.db.api, "internalid_from_uuid", internalid_from_uuid)
#        req = request_obj('%s/1' % instances_url, 'DELETE')
#        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
#        self.assertEqual(res.status_int, 422)
#
#    def test_instances_delete_failed(self):
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "delete", compute_get_osclient_accepted)
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "show", get_osclient_show_deleting)
#        self.stubs.Set(reddwarf.db.api, "internalid_from_uuid", internalid_from_uuid)
#        req = request_obj('%s/1' % instances_url, 'DELETE')
#        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
#        self.assertEqual(res.status_int, 202)
#
#    def test_instances_restart(self):
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "restart", compute_get_osclient_accepted)
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "show", get_osclient_show_restarting)
#        self.stubs.Set(reddwarf.db.api, "internalid_from_uuid", internalid_from_uuid)
#        req = request_obj('%s/1/restart' % instances_url, 'POST')
#        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
#        self.assertEqual(res.status_int, 202)
#
#    def test_instances_restart_failed(self):
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "restart", compute_get_osclient_accepted)
#        self.stubs.Set(reddwarf.client.osclient.OSClient, "show", get_osclient_show_deleting)
#        self.stubs.Set(reddwarf.db.api, "internalid_from_uuid", internalid_from_uuid)
#        req = request_obj('%s/1/restart' % instances_url, 'POST')
#        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
#        self.assertEqual(res.status_int, 500)
