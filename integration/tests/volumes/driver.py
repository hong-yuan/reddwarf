
from numbers import Number
import os
import re
import shutil
import socket
import time
import unittest

import pexpect

from nova import context
from nova import exception
from nova import flags
from nova import volume
from nova import utils
from nova.utils import poll_until

from proboscis import test
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out
from reddwarf.tests.volume.driver import ISCSITestDriver
from tests import initialize
from tests import util
from tests.volumes import VOLUMES_DRIVER


FLAGS = flags.FLAGS
UUID_PATTERN = re.compile('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
                          '[0-9a-f]{4}-[0-9a-f]{12}$')


def is_uuid(text):
    return UUID_PATTERN.search(text) is not None


class StoryDetails(object):

    def __init__(self):
        self.api = volume.API()
        self.client = volume.Client()
        self.context = context.get_admin_context()
        self.device_path = None
        self.volume_desc = None
        self.volume_id = None
        self.volume_name = None
        self.volume = None
        self.host = socket.gethostname()
        self.original_uuid = None
        self.original_device_info = None

    def get_volume(self):
        return self.api.get(self.context, self.volume_id)

    @property
    def mount_point(self):
        return "%s/%s" % (LOCAL_MOUNT_PATH, self.volume_id)

    @property
    def test_mount_file_path(self):
        return "%s/test.txt" % self.mount_point


story = None
storyFail = None

LOCAL_MOUNT_PATH = "/testsmnt"


class VolumeTest(unittest.TestCase):
    """This test tells the story of a volume, from cradle to grave."""

    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)

    def setUp(self):
        global story, storyFail
        self.story = story
        self.storyFail = storyFail

    def assert_volume_as_expected(self, volume):
        self.assertTrue(isinstance(volume["id"], Number))
        self.assertEqual(self.story.volume_name, volume["display_name"])
        self.assertEqual(self.story.volume_desc, volume["display_description"])
        self.assertEqual(1, volume["size"])
        self.assertEqual(self.story.context.user_id, volume["user_id"])
        self.assertEqual(self.story.context.project_id, volume["project_id"])


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[initialize.Volume])
class SetUp(VolumeTest):

    def test_05_create_story(self):
        """Creating 'story' vars used by the rest of these tests."""
        global story, storyFail
        story = StoryDetails()
        storyFail = StoryDetails()

    @time_out(60)
    def test_10_wait_for_topics(self):
        """Wait until the volume topic is up before proceeding."""
        topics = ["volume"]
        from tests.util.topics import hosts_up
        while not all(hosts_up(topic) for topic in topics):
            pass

    def test_20_refresh_local_folders(self):
        """Delete the local folders used as mount locations if they exist."""
        if os.path.exists(LOCAL_MOUNT_PATH):
            #TODO(rnirmal): Also need to remove any existing mounts.
            shutil.rmtree(LOCAL_MOUNT_PATH)
        os.mkdir(LOCAL_MOUNT_PATH)
        # Give some time for the services to startup
        time.sleep(10)

    @time_out(60)
    def test_30_mgmt_volume_check(self):
        """Get the volume information from the mgmt API"""
        device_info = self.story.api.get_storage_device_info(self.story.context)
        print("device_info : %r" % device_info)
        self.assertNotEqual(device_info, None, "the storage device information should exist")
        self.story.original_device_info = device_info

    @time_out(60)
    def test_31_mgmt_volume_info(self):
        """Check the available space against the mgmt API info."""
        device_info = self.story.api.get_storage_device_info(self.story.context)
        print("device_info : %r" % device_info)
        info = {'spaceTotal': device_info['raw_total'],
                'spaceAvail': device_info['raw_avail']}
        self._assert_avilable_space(info)

    def _assert_avilable_space(self, device_info, fail=False):
        """Give the SAN device_info(fake or not) and get the asserts for free"""
        print("DEVICE_INFO on SAN : %r" % device_info)
        # Calculate the gbs and divide by 2 for the FLAGS.san_network_raid_factor
        gbs = 1.0/1024/1024/1024/2
        total = int(device_info['spaceTotal'])*gbs
        free = int(device_info['spaceAvail'])*gbs
        used = total - free
        usable = round(total * (FLAGS.san_max_provision_percent * 0.01))
        real_free = round((usable - used))

        print("total : %r" % total)
        print("free : %r" % free)
        print("used : %r" % used)
        print("usable : %r" % usable)
        print("real_free : %r" % real_free)

        self.assertFalse(self.story.api.check_for_available_space(self.story.context, 500))
        self.assertFalse(self.story.api.check_for_available_space(self.story.context, real_free+1))

        if fail:
            self.assertFalse(self.story.api.check_for_available_space(self.story.context, real_free))
            self.assertFalse(self.story.api.check_for_available_space(self.story.context, real_free-1))
            self.assertFalse(self.story.api.check_for_available_space(self.story.context, 1))
        else:
            self.assertTrue(self.story.api.check_for_available_space(self.story.context, real_free))
            self.assertTrue(self.story.api.check_for_available_space(self.story.context, real_free-1))
            self.assertTrue(self.story.api.check_for_available_space(self.story.context, 1))


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[SetUp])
class AddVolumeFailure(VolumeTest):

    @time_out(60)
    def test_add(self):
        """Make call to FAIL a prov. volume and assert the return value is a FAILURE."""
        self.assertEqual(None, self.storyFail.volume_id)
        name = "TestVolume"
        desc = "A volume that was created for testing."
        self.storyFail.volume_name = name
        self.storyFail.volume_desc = desc
        volume = self.storyFail.api.create(self.storyFail.context, size=500,
                                           snapshot_id=None, name=name,
                                           description=desc)
        self.assertEqual(500, volume["size"])
        self.assertTrue("creating", volume["status"])
        self.assertTrue("detached", volume["attach_status"])
        self.storyFail.volume = volume
        self.storyFail.volume_id = volume["id"]


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[AddVolumeFailure])
class AfterVolumeFailureIsAdded(VolumeTest):
    """Check that the volume can be retrieved via the API, and setup.

    All we want to see returned is a list-like with an initial string.

    """

    @time_out(120)
    def test_api_get(self):
        """Wait until the volume is a FAILURE."""
        volume = poll_until(lambda : self.storyFail.get_volume(),
                            lambda volume : volume["status"] != "creating")
        self.assertEqual(volume["status"], "error")
        self.assertTrue(volume["attach_status"], "detached")

    @time_out(60)
    def test_mgmt_volume_check(self):
        """Get the volume information from the mgmt API"""
        info = self.story.api.get_storage_device_info(self.story.context)
        print("device_info : %r" % info)
        self.assertNotEqual(info, None, "the storage device information should exist")
        self.assertEqual(self.story.original_device_info['raw_total'], info['raw_total'])
        self.assertEqual(self.story.original_device_info['raw_avail'], info['raw_avail'])


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[SetUp])
class AddVolume(VolumeTest):

    @time_out(60)
    def test_add(self):
        """Make call to prov. a volume and assert the return value is OK."""
        self.assertEqual(None, self.story.volume_id)
        name = "TestVolume"
        desc = "A volume that was created for testing."
        self.story.volume_name = name
        self.story.volume_desc = desc
        volume = self.story.api.create(self.story.context, size=1,
                                       snapshot_id=None, name=name,
                                       description=desc)
        self.assert_volume_as_expected(volume)
        self.assertTrue("creating", volume["status"])
        self.assertTrue("detached", volume["attach_status"])
        self.story.volume = volume
        self.story.volume_id = volume["id"]


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[AddVolume])
class AfterVolumeIsAdded(VolumeTest):
    """Check that the volume can be retrieved via the API, and setup.

    All we want to see returned is a list-like with an initial string.

    """

    @time_out(120)
    def test_api_get(self):
        """Wait until the volume is finished provisioning."""
        volume = poll_until(lambda : self.story.get_volume(),
                            lambda volume : volume["status"] != "creating")
        self.assertEqual(volume["status"], "available")
        self.assert_volume_as_expected(volume)
        self.assertTrue(volume["attach_status"], "detached")

    @time_out(60)
    def test_mgmt_volume_check(self):
        """Get the volume information from the mgmt API"""
        print("self.story.original_device_info : %r" % self.story.original_device_info)
        info = self.story.api.get_storage_device_info(self.story.context)
        print("device_info : %r" % info)
        self.assertNotEqual(info, None, "the storage device information should exist")
        self.assertEqual(self.story.original_device_info['raw_total'], info['raw_total'])
        volume_size = int(self.story.volume['size']) * (1024**3) * 2
        print("volume_size: %r" % volume_size)
        print("self.story.volume['size']: %r" % self.story.volume['size'])
        avail = int(self.story.original_device_info['raw_avail']) - volume_size
        print("avail space: %r" % avail)
        self.assertEqual(int(info['raw_avail']), avail)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[AfterVolumeIsAdded])
class SetupVolume(VolumeTest):

    @time_out(60)
    def test_assign_volume(self):
        """Tell the volume it belongs to this host node."""
        #TODO(tim.simpson) If this is important, could we add a test to
        #                  make sure some kind of exception is thrown if it
        #                  isn't added to certain drivers?
        self.assertNotEqual(None, self.story.volume_id)
        self.story.api.assign_to_compute(self.story.context, self.story.volume_id,
                                         self.story.host)

    @time_out(60)
    def test_setup_volume(self):
        """Set up the volume on this host. AKA discovery."""
        self.assertNotEqual(None, self.story.volume_id)
        device = self.story.client._setup_volume(self.story.context,
                                                self.story.volume_id,
                                                self.story.host)
        if not isinstance(device, basestring):
            self.fail("Expected device to be a string, but instead it was " +
                      str(type(device)) + ".")
        self.story.device_path = device


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[SetupVolume])
class FormatVolume(VolumeTest):

    @expect_exception(IOError)
    @time_out(60)
    def test_10_should_raise_IOError_if_format_fails(self):
        """

        Tests that if the driver's _format method fails, its
        public format method will perform an assertion properly, discover
        it failed, and raise an exception.

        """

        volume_driver_cls = utils.import_class(FLAGS.volume_driver)
        class BadFormatter(volume_driver_cls):

            def _format(self, device_path):
                pass

        bad_client = volume.Client(volume_driver=BadFormatter())
        bad_client._format(self.story.device_path)

    @time_out(60)
    def test_20_format(self):
        self.assertNotEqual(None, self.story.device_path)
        self.story.client._format(self.story.device_path)

    def test_30_check_options(self):
        cmd = "sudo dumpe2fs -h %s 2> /dev/null | " \
              "awk -F ':' '{ if($1 == \"Reserved block count\") { rescnt=$2 } }" \
              " { if($1 == \"Block count\") { blkcnt=$2 } } END " \
              "{ print (rescnt/blkcnt)*100 }'" % self.story.device_path
        out, err = util.process(cmd)
        self.assertEqual(float(5), round(float(out)), msg=out)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[FormatVolume])
class MountVolume(VolumeTest):

    @time_out(60)
    def test_mount(self):
        self.story.client._mount(self.story.device_path, self.story.mount_point)
        with open(self.story.test_mount_file_path, 'w') as file:
            file.write("Yep, it's mounted alright.")
        self.assertTrue(os.path.exists(self.story.test_mount_file_path))

    def test_mount_options(self):
        cmd = "mount -l | awk '/noatime/ { print $1 }'"
        out, err = util.process(cmd)
        self.assertEqual(os.path.realpath(self.story.device_path), out.strip(),
                         msg=out)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[MountVolume])
class UnmountVolume(VolumeTest):

    @time_out(60)
    def test_unmount(self):
        self.story.client._unmount(self.story.mount_point)
        child = pexpect.spawn("sudo mount %s" % self.story.mount_point)
        child.expect("mount: can't find %s in" % self.story.mount_point)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[UnmountVolume])
class GrabUuid(VolumeTest):

    @time_out(60)
    def test_uuid_must_match_pattern(self):
        """UUID must be hex chars in the form 8-4-4-4-12."""
        client = self.story.client # volume.Client()
        device_path = self.story.device_path # '/dev/sda5'
        uuid = client.get_uuid(device_path)
        self.story.original_uuid = uuid
        self.assertTrue(is_uuid(uuid), "uuid must match regex")

    @time_out(60)
    def test_get_invalid_uuid(self):
        """DevicePathInvalidForUuid is raised if device_path is wrong."""
        client = self.story.client
        device_path = "gdfjghsfjkhggrsyiyerreygghdsghsdfjhf"
        self.assertRaises(exception.DevicePathInvalidForUuid, client.get_uuid,
                          device_path)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[GrabUuid])
class RemoveVolume(VolumeTest):

    @time_out(60)
    def test_remove(self):
        self.story.client.remove_volume(self.story.context,
                                 self.story.volume_id,
                                 self.story.host)
        self.assertRaises(Exception,
                          self.story.client._format, self.story.device_path)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[GrabUuid])
class Initialize(VolumeTest):

    @time_out(60)
    def test_10_initialize_will_format(self):
        """initialize will setup, format, and store the UUID of a volume"""
        self.assertTrue(self.story.get_volume()['uuid'] is None)
        self.story.client.initialize(self.story.context, self.story.volume_id,
                                     self.story.host)
        volume = self.story.get_volume()
        self.assertTrue(is_uuid(volume['uuid']), "uuid must match regex")
        self.assertNotEqual(self.story.original_uuid, volume['uuid'],
                            "Validate our assumption that the volume UUID "
                            "will change when the volume is formatted.")
        self.story.client.remove_volume(self.story.context,
                                        self.story.volume_id,
                                        self.story.host)

    @time_out(60)
    def test_20_initialize_the_second_time_will_not_format(self):
        """If initialize is called but a UUID exists, it should not format."""
        old_uuid = self.story.get_volume()['uuid']
        self.assertTrue(old_uuid is not None)

        class VolumeClientNoFmt(volume.Client):

            def _format(self, device_path):
                raise RuntimeError("_format should not be called!")

        no_fmt_client = VolumeClientNoFmt()
        no_fmt_client.initialize(self.story.context, self.story.volume_id,
                                 self.story.host)
        self.assertEqual(old_uuid, self.story.get_volume()['uuid'],
                         "UUID should be the same as no formatting occurred.")
        self.story.client.remove_volume(self.story.context,
                                        self.story.volume_id,
                                        self.story.host)

    @expect_exception(exception.InvalidDevicePath)
    def test_30_check_device_exists(self):
        self.story.client._format(self.story.device_path)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[Initialize])
class DeleteVolume(VolumeTest):

    @time_out(60)
    def test_delete(self):
        self.story.api.delete(self.story.context, self.story.volume_id)


@test(groups=[VOLUMES_DRIVER], depends_on_classes=[DeleteVolume])
class ConfirmMissing(VolumeTest):

    @expect_exception(exception.Error)
    @time_out(60)
    def test_discover_should_fail(self):
        self.story.client.driver.discover_volume(self.story.context,
                                                 self.story.volume)

    @time_out(60)
    def test_get_missing_volume(self):
        try:
            volume = poll_until(lambda : self.story.api.get(self.story.context,
                                                        self.story.volume_id),
                                lambda volume : volume["status"] != "deleted")
            self.assertEqual(volume["deleted"], False)
        except exception.VolumeNotFound:
            pass
