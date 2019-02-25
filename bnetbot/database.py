
from datetime import datetime
import re


def get_default_groups():
    groups = {}
    g = DatabaseItem("Admin", True)
    g.permissions["commands.*"] = True
    groups["admin"] = g
    return groups


def load_item(data, name, is_group):
    item = DatabaseItem(name, is_group)
    item.permissions = data.get("permissions", {})
    item.added = data.get("added")
    item.modified = data.get("modified")
    item.modified_by = data.get("modified_by")
    return item


def load(config):
    db = UserDatabase()
    data = config.get("database")
    if data is None:
        return db   # No database found in config - return empty

    # Load group names and metadata
    group_list = data.get("groups", {})
    for name, group in group_list.items():
        db.groups[name.lower()] = load_item(group, name, True)

    # Link group names to objects
    for name, group in group_list.items():
        item = db.groups[name.lower()]

        for group_name in [gp.lower() for gp in group.get("groups", [])]:
            item.groups[group_name] = db.groups.get(group_name)

    # Load users
    for name, user in data.get("users", {}).items():
        item = load_item(user, name, False)
        db.users[name.lower()] = item

        # Link user groups
        for group_name in [gp.lower() for gp in user.get("groups", [])]:
            item.groups[group_name] = db.groups.get(group_name)

    return db


class UserDatabase:
    def __init__(self):
        self.groups = get_default_groups()
        self.users = {}

    def user(self, username):
        return self.users.get(username.lower())

    def group(self, group_name):
        return self.groups.get(group_name.lower())


class DatabaseItem:
    def __init__(self, name, is_group):
        self.name = name
        self.is_group = is_group
        self.permissions = {}
        self.groups = {}
        self.added = datetime.now()
        self.modified = None
        self.modified_by = None

    def check_permission(self, permission):
        permission = permission.lower()

        # Check for permission provided by a group assignment
        group_perm = False
        for group in filter(lambda x: x is not None, self.groups.values()):
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

