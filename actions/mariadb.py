from .action import ActiveAction

import subprocess
import os
# import json

from common import leapp_configs
from common import log


MARIADB_VERSION_ON_ALMA = "10.3.35"


def _is_version_larger(left, right):
    for pleft, pright in zip(left.split("."), right.split(".")):
        if int(pleft) > int(pright):
            return True
        elif int(pright) > int(pleft):
            return False

    return False


def _get_mariadb_utilname():
    for util in ["mariadb", "mysql"]:
        if subprocess.run(["which", util], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return util

    return None


def _is_mariadb_installed():
    util = _get_mariadb_utilname()
    if util is None:
        return False
    elif util == "mariadb":
        return True

    process = subprocess.Popen([util, "--version"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
    out, _ = process.communicate()
    if process.returncode != 0:
        return False

    return "MariaDB" in out


def _is_mysql_installed():
    util = _get_mariadb_utilname()
    if util is None or util == "mariadb":
        return False

    process = subprocess.Popen([util, "--version"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
    out, _ = process.communicate()
    if process.returncode != 0:
        return False

    return "MariaDB" not in out


def _get_mariadb_version():
    util = _get_mariadb_utilname()
    process = subprocess.Popen([util, "--version"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
    out, err = process.communicate()
    if process.returncode != 0:
        raise RuntimeError("Unable to get mariadb version: {}".format(err))

    log.debug("Detected mariadb version is: {version}".format(version=out.split("Distrib ")[1].split(",")[0].split("-")[0]))

    return out.split("Distrib ")[1].split(",")[0].split("-")[0]


class AvoidMariadbDowngrade(ActiveAction):
    def __init__(self):
        self.name = "avoid mariadb downgrade"
        self.mariadb_version_on_alma = "10.3.35"
        self.mariadb_repofile = "/etc/yum.repos.d/mariadb.repo"

    def _is_required(self):
        return _is_mariadb_installed() and not _is_version_larger(MARIADB_VERSION_ON_ALMA, _get_mariadb_version())

    def _prepare_action(self):
        if not os.path.exists(self.mariadb_repofile):
            raise Exception("Mariadb installed from unknown repository. Please check the '{}' file is present".format(self.mariadb_repofile))

        leapp_configs.add_repositories_mapping([self.mariadb_repofile])
        leapp_configs.set_package_repository("mariadb", "alma-maridb")

    def _post_action(self):
        pass

    def _revert_action(self):
        pass


class UpdateMariadbDatabase(ActiveAction):
    def __init__(self):
        self.name = "updating mariadb databases"

    def _is_required(self):
        return _is_mariadb_installed() and _is_version_larger(MARIADB_VERSION_ON_ALMA, _get_mariadb_version())

    def _prepare_action(self):
        pass

    def _post_action(self):
        # We should be sure mariadb is started, otherwise restore woulden't work
        subprocess.check_call(["systemctl", "start", "mariadb"])

        with open('/etc/psa/.psa.shadow', 'r') as shadowfile:
            shadowdata = shadowfile.readline().rstrip()
            subprocess.check_call(["mysql_upgrade", "-uadmin", "-p" + shadowdata])
        # Also find a way to drop cookies, because it will ruin your day
        # We have to delete it once again, because leapp going to install it in scope of conversation process,
        # but without right configs

    def _revert_action(self):
        pass


class AddMysqlConnector(ActiveAction):
    def __init__(self):
        self.name = "install mysql connector"

    def _is_required(self):
        return _is_mysql_installed()

    def _prepare_action(self):
        pass

    def _post_action(self):
        subprocess.check_call(["dnf", "install", "-y", "mariadb-connector-c"])

    def _revert_action(self):
        pass
