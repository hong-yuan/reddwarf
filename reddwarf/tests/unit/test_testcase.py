#    Copyright 2012 OpenStack LLC
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

from reddwarf.tests import TestCase

class TestTestCase(TestCase):
    def test_assertDictKeysEqual(self):
        d1 = {"1":"1", "2":"2", "3":{"a":"a", "b":"b", "c":{"a1":"x", "a2":"y"}}}
        d2 = {"1":"1", "2":"h", "3":{"a":"5", "b":"b", "c":{"a1":"4", "a2":"x"}}}
        self.assertDictKeysEqual(d1, d2)

    def test_assertDictKeysEqual_fails_on_unequal_dicts(self):
        d1 = {"1":"1", "2":"2", "3":{"a":"a", "b":"b", "c":{"a1":"x", "a2":"y"}}}
        d2 = {"1":"1", "2":"2", "3":{"a":"a", "b":"b", "c":{"a1":"x", "a4":"y"}}}
        with self.assertRaises(AssertionError):
            self.assertDictKeysEqual(d1, d2)
        with self.assertRaises(AssertionError):
            self.assertDictKeysEqual(d2, d1)

    def test_assertDictKeysEqual_fails_on_superfluous_keys(self):
        d1 = {"1":"1", "2":"2", "3":{"a":"a", "b":"b", "c":{"a1":"x", "a2":"y"}}}
        d2 = {"1":"1", "2":"h", "3":{"a":"5", "b":"b", "c":{"a1":"4", "a2":"x", "a4":"d"}}}
        with self.assertRaises(AssertionError):
            self.assertDictKeysEqual(d1, d2)
        with self.assertRaises(AssertionError):
            self.assertDictKeysEqual(d2, d1)
