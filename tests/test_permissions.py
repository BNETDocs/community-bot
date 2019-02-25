
from bnetbot.database import *
import unittest


def check_permission(permission, match_to):
    user = DatabaseItem("TestUser", False)
    user.permissions[permission] = True
    return user.check_permission(match_to)


class TestPermissionMatching(unittest.TestCase):
    def test_exact_match(self):
        user = DatabaseItem("TestUser", False)
        user.permissions["exact.perm.node"] = True

        self.assertTrue(user.check_permission("exact.perm.node"))
        self.assertFalse(user.check_permission("some.other.node"))
        self.assertFalse(user.check_permission("exact.perm.node.with.more"))

    def test_wildcard_match(self):
        user = DatabaseItem("TestUser", False)
        user.permissions["wildcard.node.*"] = True
        user.permissions["wildcard.*.node"] = True

        self.assertTrue(user.check_permission("wildcard.node.end"))
        self.assertTrue(user.check_permission("wildcard.node.end.extended"))
        self.assertFalse(user.check_permission("wildcard.different.end"))

        self.assertTrue(user.check_permission("wildcard.middle.node"))
        self.assertTrue(user.check_permission("wildcard.middle.extended.node"))
        self.assertFalse(user.check_permission("wildcard.different.end"))


class TestPermissionAssignment(unittest.TestCase):
    def test_user_override_group(self):
        user = DatabaseItem("TestUser", False)
        user.groups["test"] = DatabaseItem("Test", True)
        user.groups["test"].permissions["exact.perm.node"] = True

        # Check user has permission from group
        self.assertTrue(user.check_permission("exact.perm.node"))

        # Override the group's permission
        user.permissions["exact.perm.node"] = False
        self.assertFalse(user.check_permission("exact.perm.node"))


if __name__ == "__main__":
    unittest.main()
