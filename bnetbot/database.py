
from datetime import datetime
import re


def get_default_groups():
    groups = {
        "admin": DatabaseItem("Admin", True, ["commands.*"]),
        "moderator": DatabaseItem("Moderator", True, ["commands.moderation.*"]),
        "user": DatabaseItem("User", True, ["commands.internal.*"])
    }
    groups["moderator"].groups["user"] = groups["user"]
    return groups


def get_default_users():
    return {
        "%root%": DatabaseItem("%root%", False, ["*"])
    }


def parse_isoformat(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f") if s else None


class UserDatabase:
    def __init__(self):
        self.groups = get_default_groups()
        self.users = get_default_users()

    def __dict__(self):
        return {
            "groups": self.groups.items(),
            "users": self.users.items()
        }

    def add(self, item):
        """Adds a user object to the database."""
        if not isinstance(item, DatabaseItem):
            raise TypeError("Can't add type %s to user database." % type(item).__name__)

        if item.is_group:
            self.groups[item.name.lower()] = item
        else:
            self.users[item.name.lower()] = item
        return item

    def remove(self, item):
        """Removes a user object from the database."""
        if not isinstance(item, DatabaseItem):
            raise TypeError("Can't remove type %s from the user database." % type(item).__name__)

        if item.is_group:
            del self.groups[item.name.lower()]
        else:
            del self.users[item.name.lower()]
        return None

    def user(self, username):
        """Returns a user object matching a given name."""
        return self.users.get(username.lower())

    def group(self, group_name):
        """Returns a group object matching a given name."""
        return self.groups.get(group_name.lower())

    @classmethod
    def load(cls, config):
        """Loads a user database from the 'database' element of an instance's configuration."""
        db = UserDatabase()
        if config is None:
            return db  # No database found in config - return empty

        # Load group names and metadata
        group_list = config.get("groups", {})
        for name, group in group_list.items():
            db.groups[name.lower()] = DatabaseItem.load(group, name, True)

        # Link group names to objects
        for name, group in group_list.items():
            item = db.groups[name.lower()]

            for group_name in [gp.lower() for gp in group.get("groups", [])]:
                item.groups[group_name] = db.groups.get(group_name)

        # Load users
        for name, user in config.get("users", {}).items():
            item = DatabaseItem.load(user, name, False)
            db.users[name.lower()] = item

            # Link user groups
            for group_name in [gp.lower() for gp in user.get("groups", [])]:
                item.groups[group_name] = db.groups.get(group_name)

        return db


class DatabaseItem:
    def __init__(self, name, is_group, permissions=None):
        self.name = name
        self.is_group = is_group
        self.permissions = {p: True for p in permissions} if permissions else {}
        self.groups = {}
        self.added = datetime.now()
        self.modified = None
        self.modified_by = None

    def __dict__(self):
        d = {
            "permissions": self.permissions or {},
            "added": self.added.isoformat() if self.added else None,
            "modified": self.modified.isoformat() if self.modified else None,
            "modified_by": self.modified_by
        }
        return {k: v for k, v in d.items() if v}

    def check_permission(self, permission):
        """Checks that the item has a permission."""
        permission = permission.lower()

        # Check for permission provided by a group assignment
        group_perm = False
        for group in filter(None, self.groups.values()):
            if group.check_permission(permission):
                # Permission allowed by a group
                group_perm = True
                break

        # Check for permission defined directly
        direct_perm = False
        for perm, value in self.permissions.items():
            if re.fullmatch(perm.replace(".", "\\.").replace("*", ".*"), permission):
                direct_perm = value
                if not value:
                    # Permission explicitly denied
                    return False

        return group_perm or direct_perm

    def get_permissions(self):
        """Returns the effective permission of this item, including permissions of parent groups."""
        perms = []
        for group in filter(None, self.groups.values()):
            perms.extend(group.get_permissions())
        for perm, value in self.permissions.items():
            if value:
                perms.append(perm)
            elif perm in perms:
                perms.remove(perm)
        return list(set(perms))

    def group_list(self):
        """Returns a list of groups this item is member to."""
        return [g.name for g in self.groups.values()]

    @classmethod
    def load(cls, data, name, is_group):
        """Creates an item from a database entry."""
        item = DatabaseItem(name, is_group)
        item.permissions = data.get("permissions", {})
        item.added = parse_isoformat(data.get("added")) or datetime.now()
        item.modified = parse_isoformat(data.get("modified"))
        item.modified_by = data.get("modified_by")
        return item
