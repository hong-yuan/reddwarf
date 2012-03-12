# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

import gettext
import glob
import os
import subprocess
import sys

from setuptools import find_packages
from setuptools.command.sdist import sdist
from setuptools import setup

from nova import version

from reddwarf.openstack.common.setup import parse_requirements
from reddwarf.openstack.common.setup import parse_dependency_links
from reddwarf.openstack.common.setup import write_requirements
from reddwarf.openstack.common.setup import write_git_changelog


class local_sdist(sdist):
    """Customized sdist hook - builds the ChangeLog file from VC first"""
    def run(self):
        write_git_changelog()
        sdist.run(self)
cmdclass = {'sdist': local_sdist}

try:
    from sphinx.setup_command import BuildDoc

    class local_BuildDoc(BuildDoc):
        def run(self):
            for builder in ['html', 'man']:
                self.builder = builder
                self.finalize_options()
                BuildDoc.run(self)
    nova_cmdclass['build_sphinx'] = local_BuildDoc

except:
    pass

requires = parse_requirements()
depend_links = parse_dependency_links()

write_requirements()


def find_data_files(destdir, srcdir):
    package_data = []
    files = []
    for d in glob.glob('%s/*' % (srcdir, )):
        if os.path.isdir(d):
            package_data += find_data_files(
                                 os.path.join(destdir, os.path.basename(d)), d)
        else:
            files += [d]
    package_data += [(destdir, files)]
    return package_data

setup(name='nova',
      version=version.canonical_version_string(),
      description='cloud computing fabric controller',
      author='OpenStack',
      author_email='nova@lists.launchpad.net',
      url='http://www.openstack.org/',
      cmdclass=cmdclass,
      packages=find_packages(exclude=['bin', 'smoketests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      dependency_links=depend_links,
      test_suite='nose.collector',
      data_files=find_data_files('share/nova', 'tools'),
      scripts=['bin/nova-ajax-console-proxy',
               'bin/nova-api',
               'bin/nova-compute',
               'bin/nova-console',
               'bin/nova-dhcpbridge',
               'bin/nova-direct-api',
               'bin/nova-logspool',
               'bin/nova-manage',
               'bin/nova-network',
               'bin/nova-objectstore',
               'bin/nova-scheduler',
               'bin/nova-spoolsentry',
               'bin/stack',
               'bin/nova-volume',
               'bin/nova-vncproxy',
               'tools/nova-debug'],
        py_modules=[])
