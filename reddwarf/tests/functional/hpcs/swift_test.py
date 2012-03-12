#    Copyright 2011 OpenStack LLC
#    Copyright 2012 HP Software, LLC
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



import os
import unittest
import sys

"""This was added so you can run this from the command line, and it will be able to pick up the swiftapi.swift module"""
cwd = os.getcwd()
os.chdir("../../../")
sys.path.append(os.getcwd())

import swiftapi.swift as swifty


"""Read environment variables for testing credentials  If you're using a mac, set these in your ~/.MacOSX/environment.plist file"""

env = os.environ.copy()

AUTH_USERNAME = env.get("OPENSTACK_USERNAME","")
AUTH_PASSWORD = env.get("OPENSTACK_PASSWORD","")
AUTH_TENANTID = env.get("OPENSTACK_TENANTID","")

TEST_CONTAINER = "MyTestContainer"

AUTH_URL = "https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/tokens"

authenticated = False
auth_token = ""
object_url = ""

def setupAuthentication():
    result = swifty.get_auth(AUTH_URL, AUTH_USERNAME, AUTH_PASSWORD, False, "2.0")

    object_url = result[0]
    auth_token = result[1]
    authenticated = True

    return auth_token, object_url, authenticated

class HPCSTest(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        global auth_token, object_url, authenticated
        auth_token, object_url, authenticated = setupAuthentication()

        print "Setting up the authentication"


    def setUp(self):
        print ""


    def cleanUpContainer(self):
        swifty.delete_container(object_url, auth_token, TEST_CONTAINER)


    def test_authenticate(self):
        """Test to authenticate a user"""
        print("Testing authentication")

        result = swifty.get_auth(AUTH_URL, AUTH_USERNAME, AUTH_PASSWORD, False, "2.0")

        print result
        #print type(result)
        self.assertIsInstance(result, tuple)

    def test_authenticateFails(self):
        print("Testing authentication fail")

        AUTH_PASSWORD = "notmypassword"

        self.assertRaises(swifty.ClientException, swifty.get_auth, AUTH_URL, AUTH_USERNAME, AUTH_PASSWORD, False, "2.0")

    def test_accountGet(self):
        print("Testing get Account")

        result = swifty.get_account(object_url, auth_token)

        print result

        self.assertIsInstance(result, tuple)

    def test_accountGetStats(self):
        """Get account Stats"""
        print("Testing get account stats")

        result = swifty.head_account(object_url, auth_token)

        print result

        self.assertIsInstance(result, dict)

    def test_containerCreate(self):
        """Create a new container"""
        print("Testing create a new container")

        result = swifty.put_container(object_url, auth_token, TEST_CONTAINER)
        print swifty.get_account(object_url, auth_token)
        "Clean up the newly created container"
        self.cleanUpContainer()

        self.assertEquals(result, None)

    def test_containerGet(self):
        """Get a container"""
        print("Testing getting a container")

        swifty.put_container(object_url, auth_token, TEST_CONTAINER)
        result = swifty.get_container(object_url, auth_token, TEST_CONTAINER)

        "Clean up the newly created container"
        self.cleanUpContainer()

        print result

        self.assertIsInstance(result, tuple)

    def test_containerGetStats(self):
        """Get a container stats"""
        print("Testing getting a container stats")

        swifty.put_container(object_url, auth_token, TEST_CONTAINER)
        result = swifty.head_container(object_url, auth_token, TEST_CONTAINER)

        "Clean up the newly created container"
        self.cleanUpContainer()

        print result

        self.assertIsInstance(result, dict)

    @unittest.skip("Skipping, need to research implementation of more headers for meta data")
    def test_containerAddMetaData(self):
        """Add meta data to a container"""
        print("Testing add meta data to container")

        metaData = {'keyvalue': 'test'}

        swifty.put_container(object_url, auth_token, TEST_CONTAINER)
        result = swifty.post_container(object_url, auth_token, TEST_CONTAINER, metaData)
        print swifty.get_container(object_url, auth_token, TEST_CONTAINER)

        print result
        print type(result)

        self.cleanUpContainer()

        self.assertEquals(result, None)

    def test_containerDelete(self):
        """Delete a container"""
        print("Testing delete a container")

        print "Added container list"
        swifty.put_container(object_url, auth_token, TEST_CONTAINER)
        print swifty.get_account(object_url, auth_token)
        print "New list once container deleted"
        result = swifty.delete_container(object_url, auth_token, TEST_CONTAINER)
        print swifty.get_account(object_url, auth_token)

        self.assertEquals(result, None)

#    def test_makeContainer(self):
#        print("Making a container")
#        swifty.put_container(object_url, auth_token, "KevinContainer")
#        metaData = {'keyvalue': 'test'}
#        swifty.post_container(object_url, auth_token, "KevinContainer", metaData)
#        print swifty.get_container(object_url, auth_token, "KevinContainer")
#        self.assertEquals(True, True)



if __name__ == '__main__':
    unittest.main()







