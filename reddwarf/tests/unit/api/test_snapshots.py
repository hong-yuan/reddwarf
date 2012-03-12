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
Tests Snapshots API calls
"""

import json
import webob
from nova import context
from nova import test

from reddwarf.db import api as dbapi
from reddwarf.guest import api as guestapi
from reddwarf.api import snapshots
from reddwarf.tests import util
from reddwarf.db import models

import logging
logging.basicConfig()

snapshots_url = "%ssnapshots" % util.v1_prefix

def request_obj(url, method, body={}):
    req = webob.Request.blank(url)
    req.method = method
    if method in ['POST', 'PUT']:
        req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req

def db_snapshot_create(context, values):
    return dummy_snapshot

def create_snapshot(self, context, instance_id, snapshot_id, credential):
    return dummy_snapshot

dummy_snapshot = models.DbSnapShots()
dummy_snapshot.uuid = "123"
dummy_snapshot.name = "test-snapshot"
dummy_snapshot.state = 0
dummy_snapshot.created_at = "5555"
dummy_snapshot.instance_uuid = "234"

class SnapshotApiTest(test.TestCase):
    """Tests the Snapshot API"""

    def setUp(self):
        super(SnapshotApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = snapshots.Controller()

    def tearDown(self):
        self.stubs.UnsetAll()
        super(SnapshotApiTest, self).tearDown()

    def test_snapshots_create(self):
        self.stubs.Set(dbapi, "db_snapshot_create", db_snapshot_create)
        self.stubs.Set(guestapi.API, "create_snapshot", create_snapshot)
        req = request_obj(snapshots_url, 'POST', {"snapshot":{"instanceId": "123", "name":"test-snapsot"}})
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)

    def test_invalid_create_snapshot_request(self):
        req = request_obj(snapshots_url, 'POST')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)
