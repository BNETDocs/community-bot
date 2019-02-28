
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
        self.users = get_default_users()

    def add(self, item):
        if not isinstance(item, DatabaseItem):
            raise TypeError("Can't add type %s to user database." % type(item).__name__)

        if item.is_group:
            self.groups[item.name.lower()] = item
        else:
            self.users[item.name.lower()] = item
        return item

    def remove(self, item):
        if not isinstance(item, DatabaseItem):
            raise TypeError("Can't remove type %s from the user database." % type(item).__name__)

        if item.is_group:
            del self.groups[item.name.lower()]
        else:
            del self.users[item.name.lower()]
        return None

    def user(self, username):
        return self.users.get(username.lower())

    def group(self, group_name):
        return self.groups.get(group_name.lower())


class DatabaseItem:
    def __init__(self, name, is_group, permissions=None):
        self.name = name
        self.is_group = is_group
        self.permissions = {p: True for p in permissions} if permissions else {}
        self.groups = {}
        self.added = datetime.now()
        self.modified = None
        self.modified_by = None

    def check_permission(self, permission):
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
        return [g.name for g in self.groups.values()]
