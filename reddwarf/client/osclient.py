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

'''
Created on Feb 1, 2012

@author: vipul
'''
from novaclient.v1_1 import client
from novaclient.v1_1 import servers
from reddwarf import exception
from nova import flags
from nova import log as logging
import eventlet

FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)

class OSClient(object):
    '''
    classdocs
    '''


    def __init__(self, username, api_key, project_id, auth_url, region_name):
        '''
        Constructor
        '''
        password = api_key

        self.client = client.Client(username,password,project_id, auth_url, region_name=region_name)

    def create(self, hostname, image, flavor, files, key_name, security_groups, userdata):
        LOG.debug("OSClient - create()")
        return self.client.servers.create(hostname, image, flavor, files=files, key_name=key_name, security_groups=security_groups, userdata=userdata)

    def delete (self, id):
        LOG.debug("OSClient - delete()")
        return self.client.servers.delete(id)

    def restart(self, id):
        LOG.debug("OSClient - restart() using id %s", id)
        return self.client.servers.reboot(id)

    def show(self, id):
        LOG.debug("OSClient - show() using id %s", id)
        #server = servers.Server()
        #server.id = id
        return self.client.servers.get(id)

    def flavors(self):
        return self.client.flavors.findall()

    def assign_public_ip(self,id):
        LOG.debug("Assigning public IP to instance %s" % id)

        ip = None
        fl = self.client.floating_ips.list()
        for flip in fl:
            if flip.instance_id is None:
                # Choose one of the unassigned IPs
                ip = flip.ip
                #self.client.servers.add_floating_ip(id, flip.ip)
                break

        if ip is None:
            floating_ip = self.client.floating_ips.create(None)
            ip = floating_ip.ip

        LOG.debug("Found IP to Assign: %s" + str(ip) )

        # Fail after 30 attempts
        success = False
        for i in range(30):
            try:
                LOG.debug('Assign public IP, Attempt %d', i)
                self.client.servers.add_floating_ip(id, ip)
                success = True
                break
            except Exception:
                sucess = False
                eventlet.sleep(1)

        if success is False:
            raise exception.InstanceFault()

        return ip

    def ensure_security_group(self, name, port):
        LOG.debug("Checking SecurityGroup %s" % name % " exists")

