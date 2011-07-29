# Copyright 2010-2011 OpenStack LLC.
# All Rights Reserved.
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


from nova import log as logging
from nova.api.openstack.views import flavors as os_flavors


LOG = logging.getLogger('nova.api.platform.dbaas.flavors')
LOG.setLevel(logging.DEBUG)


class ViewBuilder(os_flavors.ViewBuilderV11):
    """Simpler view of flavors which removes local_gb."""

    def _build_detail(self, flavor_obj):
        """Build a more complete representation of a flavor."""
        LOG.debug("_build_detail of a flavor")
        detail = super(ViewBuilder, self)._build_detail(flavor_obj)
        del detail['disk']
        return detail