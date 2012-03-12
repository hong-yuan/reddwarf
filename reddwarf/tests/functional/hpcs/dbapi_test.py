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

import logging
import unittest
import json
import httplib2
import time

API_URL = "http://15.185.163.25:8775/v1.0/dbaasapi/"
AUTH_TOKEN = "abc:123"
AUTH_HEADER = {'X-Auth-Token': AUTH_TOKEN, 'content-type': 'application/json', 'Accept': 'application/json'}
created_instance = False

logging.basicConfig()

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

class DBFunctionalTests(unittest.TestCase):

    def test_instance_api(self):
        """Comprehensive instance API test using an instance lifecycle."""

        # Test creating a db instance.
        LOG.debug("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "dbapi_test",
            "flavorRef": "102",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.1.2"
            },
            "databases": [
                {
                    "name": "testdb",
                    "character_set": "utf8",
                    "collate": "utf8_general_ci"
                },
                {
                    "name": "abcdefg"
                }
            ],
            "volume":
                {
                    "size": "2"
                }
            }
        }"""

        req = httplib2.Http(".cache")
        resp, content = req.request(API_URL + "instances", "POST", body, AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the expected format.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('instance'))


        # Test listing all db instances.
        LOG.debug("* Listing all db instances")
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the response is
        # in the expected format (e.g. a JSON object beginning with an
        # 'instances' key).
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('instances'))


        # Test getting a specific db instance.
        LOG.debug("* Getting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the returned
        # instance is the same as the accepted instance.
        self.assertEqual(200, resp.status)
        self.assertEqual(self.instance_id, content['instance']['id'])


#        # Test immediately resetting the password on a db instance.
#        LOG.debug("* Resetting password on instance %s" % self.instance_id)
#        req = httplib2.Http(".cache")
#        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/resetpassword", "POST", "", AUTH_HEADER)
#        LOG.debug(resp)
#        LOG.debug(content)
#
#        # Assert 1) that the request was accepted.
#        self.assertEqual(resp.status, 500)


        # Test immediately restarting a db instance.
        LOG.debug("* Restarting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/restart", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted but raised an exception
        # (because the server isn't ready to be rebooted yet).
        self.assertEqual(500, resp.status)

        # TODO: add a sleep and re-test reset password and reboot instance


        # Test deleting a db instance.
        LOG.debug("* Deleting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(202, resp.status)

        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        content = json.loads(content)

        for each in content['instances']:
            self.assertFalse(each['id'] == self.instance_id)

        time.sleep(10)

        # Test that trying to delete an already deleted instance returns
        # the proper error code.
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the right error
        # code is returned.
        self.assertEqual(404, resp.status)


    def test_snapshot_api(self):
        """Comprehensive snapshot API test using a snapshot lifecycle."""

        # Create an image for snapshot purposes.
        LOG.debug("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "dbapi_test",
            "flavorRef": "102",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.1.2"
            },
            "databases": [
                {
                    "name": "testdb",
                    "character_set": "utf8",
                    "collate": "utf8_general_ci"
                },
                {
                    "name": "abcdefg"
                }
            ],
            "volume":
                {
                    "size": "2"
                }
            }
        }"""

        req = httplib2.Http(".cache")
        resp, content = req.request(API_URL + "instances", "POST", body, AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)

        """Assert 1) that the request was accepted and 2) that the response
           is in the expected format."""
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('instance'))
#        self.instance_id = "568f69e2-9477-4f88-92c3-0313bf6e4f78"

        # Test creating a db snapshot.
        LOG.debug("* Creating snapshot for instance %s" % self.instance_id)
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self.instance_id + "\"" + r""", "name": "dbapi_test" } }"""
        resp, content = req.request(API_URL + "snapshots", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Create snapshot - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        self.snapshot_id = content['snapshot']['id']
        LOG.debug("Snapshot ID: %s" % self.snapshot_id)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshot'))
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])


        # Test listing all db snapshots.
        LOG.debug("* Listing all snapshots")
        resp, content = req.request(API_URL + "snapshots", "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("List all snapshots - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshots'))


        # Test listing all db snapshots for a specific instance.
        LOG.debug("* Listing all snapshots for %s" % self.instance_id)
        resp, content = req.request(API_URL + "snapshots?instanceId=" + self.instance_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("List all snapshots for an instance - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the list contains the created
        # snapshot.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshots'))
        found = False
        for each in content['snapshots']:
            if self.snapshot_id == each['id'] and \
               self.instance_id == each['instanceId']:
                found = True
        self.assertEqual(True, found)


        # Test getting details about a specific db snapshot.
        LOG.debug("* Listing snapshot %s" % self.snapshot_id)
        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Listing specific snapshot - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the response is the correct
        # snapshot.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshot'))
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        self.assertEqual(self.snapshot_id, content['snapshot']['id'])


        # Test deleting a db snapshot.
        LOG.debug("* Deleting snapshot %s" % self.snapshot_id)
        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the snapshot
        # has been deleted.
        self.assertEqual(204, resp.status)

        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

        time.sleep(10)

        # Finally, delete the instance.
        LOG.debug("* Deleting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(202, resp.status)

        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Deleting instance used for snapshots - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        for each in content['instances']:
            self.assertFalse(each['id'] == self.instance_id)

    def tearDown(self):
        """Run a clean-up check to catch orphaned instances/snapshots due to
           premature test failures."""

        LOG.debug("\n*** Starting cleanup...")
        req = httplib2.Http(".cache")

        # Delete all orphaned instances
        LOG.debug("- Deleting orphaned instances:")
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        content = json.loads(content)

        for each in content['instances']:
            if each['name'] == "dbapi_test":
                LOG.debug("Deleting instance: %s" % each['id'])
                resp, content = req.request(API_URL + "instances/" + each['id'], "DELETE", "", AUTH_HEADER)
                LOG.debug(resp)
                LOG.debug(content)

        # Delete all orphaned snapshots belonging to any orphaned instance
        LOG.debug("- Deleting orphaned snapshots:")
        resp, content = req.request(API_URL + "snapshots", "GET", "", AUTH_HEADER)        
        content = json.loads(content)

        for snapshot in content['snapshots']:
            if snapshot['name'] == "dbapi_test":
                LOG.debug("Deleting snapshot: %s" % snapshot['id'])
                resp, content = req.request(API_URL + "snapshots/" + snapshot['id'], "DELETE", "", AUTH_HEADER)
                LOG.debug(resp)
                LOG.debug(content)
