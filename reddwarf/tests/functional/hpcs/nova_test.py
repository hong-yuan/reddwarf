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
import mox
import unittest
from nova import test
from nova import log
from reddwarf.client.osclient import OSClient
from novaclient.v1_1 import servers
from novaclient.v1_1 import client
from novaclient.v1_1 import flavors
from novaclient import base
from novaclient.v1_1 import base as local_base
from webob import exc as exception


LOG = log.getLogger('reddwarf.tests.hpcs.nova_test')


class OSClientTests(unittest.TestCase):
    def setUp(self):
        self.mox = mox.Mox()

        self.novaClient = self.mox.CreateMock(client.Client)
        self.baseClient = self.mox.CreateMock(base.ManagerWithFind)

        self.localBase = self.mox.CreateMock(local_base.BootingManagerWithFind(self.baseClient))
        self.localBase2 = self.mox.CreateMock(local_base.BootingManagerWithFind)

        self.novaClient.servers = self.mox.CreateMock(servers.ServerManager(self.localBase2))
        self.novaClient.flavors = self.mox.CreateMock(flavors.FlavorManager(self.baseClient))

        self.mox.StubOutClassWithMocks(client, 'Client')

        self.mox.StubOutWithMock(self.novaClient.flavors, "findall")
        self.mox.StubOutWithMock(client, "flavors")

        self.mox.StubOutWithMock(self.novaClient.servers, "get")
        self.mox.StubOutWithMock(self.novaClient.servers, "delete")
        self.mox.StubOutWithMock(self.novaClient.servers, "reboot")
        self.mox.StubOutWithMock(client, "servers")

        self.nClient = client.Client("username", "password", "apikey", "url", region_name="return")


    def tearDown(self):
        self.mox.UnsetStubs()

    def test_listFlavors(self):
        print """Get list of flavors available test"""

        self.novaClient.flavors.findall().AndReturn("Flavors List")

        self.mox.ReplayAll()


        self.nClient.flavors = self.novaClient.flavors

        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.flavors()

        print result

        self.assertEqual(True, True)

        self.mox.VerifyAll()

    def test_getServer(self):
        print """Get server information test"""

        self.novaClient.servers.get(1).AndReturn("Server Detail")

        self.mox.ReplayAll()


        self.nClient.servers = self.novaClient.servers

        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.show(1)

        print result

        self.assertEqual(result, "Server Detail")

        self.mox.VerifyAll()

    def test_create_instance(self):
        """Test a successful create instance call"""

        self.novaClient.servers.create("hostname", "image", "flavor", files="files", key_name="key_name", security_groups="security_groups", userdata="userdata").AndReturn(202)
        self.mox.ReplayAll()

        self.nClient.servers = self.novaClient.servers
        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.create("hostname", "image", "flavor", "files", "key_name", "security_groups", "userdata")

        self.assertEqual(202, result)
        self.mox.VerifyAll()

    def test_delete_instance(self):
        """Test a successful delete instance call"""

        self.novaClient.servers.delete(1).AndReturn(202)
        self.mox.ReplayAll()

        self.nClient.servers = self.novaClient.servers
        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.delete(1)

        self.assertEqual(202, result)
        self.mox.VerifyAll()

    def test_restart_instance(self):
        """Test a successful restart instance call"""

        self.novaClient.servers.reboot(1).AndReturn(202)
        self.mox.ReplayAll()

        self.nClient.servers = self.novaClient.servers
        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.restart(1)

        self.assertEqual(202, result)
        self.mox.VerifyAll()

    def test_show_instance(self):
        """Test a successful show instance call"""

        self.novaClient.servers.get(1).AndReturn(202)
        self.mox.ReplayAll()

        self.nClient.servers = self.novaClient.servers
        self.osclient = OSClient("username", "password", "apikey", "url", region_name="return")
        result = self.osclient.show(1)

        self.assertEqual(202, result)
        self.mox.VerifyAll()
