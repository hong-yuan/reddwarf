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
import os
import shutil

from nova.api import openstack
from nova import flags
from nova.db import migration as nova_migration
from sqlalchemy import MetaData
from reddwarf.db import models

from nova.db.sqlalchemy import session
import unittest
import urlparse

import mox
import inspect
from sqlalchemy.orm import mapper
database_file = "reddwarf_test.sqlite"
clean_db = "clean.sqlite"
reddwarf_db_version = 7

FLAGS = flags.FLAGS

def setup():
    FLAGS.Reset()
    FLAGS['sql_connection'].SetDefault("sqlite:///%s" % database_file)
    FLAGS['allow_admin_api'].SetDefault("True")
    FLAGS['state_path'].SetDefault(os.path.dirname(__file__))
    if os.path.exists(database_file):
        os.remove(database_file)
    if os.path.exists(clean_db):
        os.remove(clean_db)
    nova_migration.db_sync()
    shutil.copy(database_file, clean_db)

class TestCase(unittest.TestCase):
    def setUp(self):
        #maxDiff=None ensures diff output of assert methods are not truncated
        self.maxDiff = None
        self.mock = mox.Mox()
        super(TestCase, self).setUp()

    def tearDown(self):
        self.mock.UnsetStubs()
        self.mock.VerifyAll()
        super(TestCase, self).tearDown()

    def assertIn(self, expected, actual):
        """This is similar to assertIn in python 2.7"""
        self.assertTrue(expected in actual,
            "{0} does not contain {1}".format(repr(actual), repr(expected)))

    def assertNotIn(self, expected, actual):
        self.assertFalse(expected in actual,
            "{0} does contains {1}".format(repr(actual), repr(expected)))

    def assertIsNone(self, actual):
        """This is similar to assertIsNone in python 2.7"""
        self.assertEqual(actual, None)

    def assertIsNotNone(self, actual):
        """This is similar to assertIsNotNone in python 2.7"""
        self.assertNotEqual(actual, None)

    def assertItemsEqual(self, expected, actual):
        self.assertEqual(sorted(expected), sorted(actual))

    def assertModelsEqual(self, expected, actual):
        self.assertEqual(sorted(expected, key=lambda model: model.id),
                         sorted(actual, key=lambda model: model.id))

    def assertErrorResponse(self, response, error_type, expected_error):
        self.assertEqual(response.status_int, error_type().code)
        self.assertIn(expected_error, response.body)

    def assertDictKeysEqual(self, dict1, dict2):
        self._assertDictKeysEqual(dict1, dict2)
        self._assertDictKeysEqual(dict2, dict1)

    def _assertDictKeysEqual(self, dict1, dict2):
        for k, v in dict1.items():
            self.assertIn(k, dict2)
            if type(v) is dict:
                self._assertDictKeysEqual(v, dict2[k])

class DBTestCase(TestCase):
    def setUp(self):
        super(DBTestCase, self).setUp()

        if os.path.isfile("unittest.db"):
            os.remove("unittest.db")

        FLAGS.Reset()
        FLAGS['sql_connection'].SetDefault("sqlite:///unittest.db")

        metaModel = []
        for name, obj in inspect.getmembers(models):
            if inspect.isclass(obj):
                for c in inspect.getmro(obj):
                    if "nova.db.sqlalchemy.models" == c.__module__ and "NovaBase" == c.__name__ and obj.__name__ != "NovaBase":
                        metaModel.append(obj)

        engine = session.get_engine()
        for model in metaModel:
            model.metadata.bind = engine
            model.metadata.create_all()


