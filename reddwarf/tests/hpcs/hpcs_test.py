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
import json #@UnresolvedImport
import httplib2
import os

from nova import log as logging
from nova import test


#LOG = logging.getLogger('reddwarf.tests.hpcs.hpcs_test')
#LOG.setLevel(logging.DEBUG)

"""Read environment variables for testing credentials  If you're using a mac, set these in your ~/.MacOSX/environment.plist file"""
authenticated = False

env = os.environ.copy()
auth_username = env.get("OPENSTACK_USERNAME","")
auth_password = env.get("OPENSTACK_PASSWORD","")
auth_tenantID = env.get("OPENSTACK_TENANTID","")

auth_token = ""
auth_url = "region-a.geo-1.identity.hpcloudsvc.com"
auth_port = 35357
auth_path = "/v2.0/tokens"
auth_headers = {"Content-type": "application/json",
                "Accept": "application/json"}

object_url = ""
object_path = ""

image_url = ""
image_path = ""

blockstorage_url = ""
blockstorage_path = ""

compute_url = "az-2.region-a.geo-1.compute.hpcloudsvc.com"
compute_path = "/v1.1/%s/" % auth_tenantID
    

class HPCSTest(test.TestCase):
    """Test various API calls"""    
    
    def get_authtoken(self):
        """Get authentication token"""
        jsonRequest = """{"auth":{"passwordCredentials":{"username":"%s", "password":"%s"}, "tenantName":"%s"}}""" % (auth_username, auth_password, auth_username)
        
        req = httplib2.HTTPSConnectionWithTimeout(auth_url, auth_port)
        req.request("POST", auth_path, jsonRequest, auth_headers)
        response = req.getresponse()
        responseContent = response.read()
        
        if(response.status == 200) : 
            jsonResponse = json.loads(responseContent)
            global auth_token, authenticated
            auth_token = jsonResponse['access']['token']['id']
            authenticated = True
            
        
    def tokenHeader(self):
        h = {"X-Auth-Token" : auth_token}
        return h

    def setUp(self):
        super(HPCSTest, self).setUp()
        
        global authenticated
        
        if(authenticated != True) :
            self.get_authtoken()
        else : 
            print "Authentication Token : " + auth_token
    
#    def tearDown(self):
#        super(HPCSTest, self).tearDown()


    def test_authenticate(self):
        """Test to authenticate a user"""
        print("Testing authentication")
        
        jsonRequest = """{"auth":{"passwordCredentials":{"username":"%s", "password":"%s"}, "tenantName":"%s"}}""" % (auth_username, auth_password, auth_username)
        
        req = httplib2.HTTPSConnectionWithTimeout(auth_url, auth_port)
        req.request("POST", auth_path, jsonRequest, auth_headers)
        response = req.getresponse()
        responseContent = response.read()
        
        #print(responseContent)
        
        self.assertEqual(response.status, 200)        
        
        
    def test_instances_list(self):
        """Test to get list of instances from nova"""
        print("Testing instances call")
        
        req = httplib2.HTTPSConnectionWithTimeout(compute_url)
        req.request("GET", compute_path + "servers", "", self.tokenHeader())
        response = req.getresponse()
        responseContent = response.read()
        
        #print(responseContent)

        self.assertEqual(response.status, 200)
        
        
    def test_instances_list_details(self):
        """Test to get list of instances with details from nova"""
        print("Testing instances details call")
        
        req = httplib2.HTTPSConnectionWithTimeout(compute_url)
        req.request("GET", compute_path + "servers/detail", "", self.tokenHeader())
        response = req.getresponse()
        responseContent = response.read()
        
        #print(responseContent)

        self.assertEqual(response.status, 200)
        
    
#    def test_instances_create(self):
#        """Test to create an instance on nova"""
#        
#    
#    def test_instances_update(self):
#        """Test to update information on an instance"""
#        
#    
#    def test_instances_delete(self):
#        """Test to delete an instance on nova"""
#        
#    
#    def test_instances_detail(self):
#        """Test to get specific instance details"""
#            
#    
#    def test_versions_list(self):
#        """Test to list out version information for the nova api"""
#        
#    
    def test_flavors_list(self):
        """Test to list out a list of flavors available"""
        print("Testing flavors call")
        req = httplib2.HTTPSConnectionWithTimeout(compute_url)
        req.request("GET", compute_path + "flavors", "", self.tokenHeader())
        response = req.getresponse()
        responseContent = response.read()
        
        #print(responseContent)

        self.assertEqual(response.status, 200)
        
    def test_flavors_list_details(self):
        """Test to list out a list of flavors with details"""
        print("Testing flavor details call")
        
        req = httplib2.HTTPSConnectionWithTimeout(compute_url)
        req.request("GET", compute_path + "flavors/detail", "", self.tokenHeader())
        response = req.getresponse()
        responseContent = response.read()
        
        #print(responseContent)

        self.assertEqual(response.status, 200)
#    
#    def test_images_list(self):
#        """Test to list out a list of images available"""
#        
#    
#    def test_databases_list(self):
#        """Test to list out database instances from nova"""
#        
#    
#    def test_databases_list_detail(self): 
#        """Test to list out database instances with details from nova"""   
#    
#    
#    def test_databases_create(self):
#        """Test to create a database instance on nova"""
#        
#    
#    def test_databases_update(self):
#        """Test to update information on a database instance"""
#        
#    
#    def test_databases_delete(self):
#        """Test to delete a database instance on nova"""
#        
#    def test_databases_detail(self):
#        """Test to list out database details"""
#        x
#    def test_databases_user_create(self):
#        """Test to create a database user"""
#        
#    def test_databases_user_enableroot(self):
#        """Test to update a database user to enable root for that user"""
#        
#    def test_databases_user_update(self):
#        """Test to update a database user information"""
#        
#    def test_databases_user_delete(self):
#        """Test to delete a database user"""
