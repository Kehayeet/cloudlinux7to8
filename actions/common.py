from .action import ActiveAction, CheckAction

import os
import platform
import subprocess
import sys

import common
from common import util


class FixNamedConfig(ActiveAction):
    def __init__(self):
        self.name = "fix named configuration"
        self.user_options_path = "/etc/named-user-options.conf"

    def _prepare_action(self):
        if not os.path.exists(self.user_options_path):
            os.symlink("/var/named/chroot/etc/named-user-options.conf", self.user_options_path)

    def _post_action(self):
        if os.path.exists(self.user_options_path):
            os.unlink(self.user_options_path)

    def _revert_action(self):
        if os.path.exists(self.user_options_path):
            os.unlink(self.user_options_path)


class FixSpamassassinConfig(ActiveAction):
    # Make sure the trick is preformed before any call of 'systemctl daemon-reload'
    # because we change spamassassin.service configuration in scope of this action.
    def __init__(self):
        self.name = "fix spamassassin configuration"

    def _is_required(self):
        return common.is_package_installed("psa-spamassassin")

    def _prepare_action(self):
        util.logged_check_call(["systemctl", "stop", "spamassassin.service"])
        util.logged_check_call(["systemctl", "disable", "spamassassin.service"])

    def _post_action(self):
        util.logged_check_call(["plesk", "sbin", "spammng", "--enable"])
        util.logged_check_call(["plesk", "sbin", "spammng", "--update", "--enable-server-configs", "--enable-user-configs"])

        util.logged_check_call(["systemctl", "daemon-reload"])
        util.logged_check_call(["systemctl", "enable", "spamassassin.service"])

    def _revert_action(self):
        util.logged_check_call(["systemctl", "enable", "spamassassin.service"])
        util.logged_check_call(["systemctl", "start", "spamassassin.service"])


class DisableSuspiciousKernelModules(ActiveAction):
    def __init__(self):
        self.name = "rule suspicious kernel modules"
        self.suspicious_modules = ["pata_acpi", "btrfs", "floppy"]
        self.modules_konfig_path = "/etc/modprobe.d/pataacpibl.conf"

    def _get_enabled_modules(self, lookup_modules):
        modules = []
        process = subprocess.run(["lsmod"], stdout=subprocess.PIPE, universal_newlines=True)
        for line in process.stdout.splitlines():
            module_name = line[:line.find(' ')]
            if module_name in lookup_modules:
                modules.append(module_name)
        return modules

    def _prepare_action(self):
        with open(self.modules_konfig_path, "a") as kern_mods_config:
            for suspicious_module in self.suspicious_modules:
                kern_mods_config.write("blacklist {module}\n".format(module=suspicious_module))

        for enabled_modules in self._get_enabled_modules(self.suspicious_modules):
            util.logged_check_call(["rmmod", enabled_modules])

    def _post_action(self):
        for module in self.suspicious_modules:
            common.replace_string(self.modules_konfig_path, "blacklist " + module, "")

    def _revert_action(self):
        for module in self.suspicious_modules:
            common.replace_string(self.modules_konfig_path, "blacklist " + module, "")


class RuleSelinux(ActiveAction):
    def __init__(self):
        self.name = "rule selinux status"
        self.selinux_config = "/etc/selinux/config"

    def _prepare_action(self):
        common.replace_string(self.selinux_config, "SELINUX=enforcing", "SELINUX=permissive")

    def _post_action(self):
        common.replace_string(self.selinux_config, "SELINUX=permissive", "SELINUX=enforcing")

    def _revert_action(self):
        common.replace_string(self.selinux_config, "SELINUX=permissive", "SELINUX=enforcing")


class AddFinishSshLoginMessage(ActiveAction):
    def __init__(self):
        self.name = "add finish ssh login message"
        self.motd_path = "/etc/motd"
        self.finish_message = """
===============================================================================
Message from Plesk distupgrade tool:
The server has been converted to AlmaLinux 8.
You can remove this message from the /etc/motd file.
===============================================================================
"""

    def _prepare_action(self):
        pass

    def _post_action(self):
        common.restore_file_from_backup(self.motd_path)

        with open(self.motd_path, "a") as motd:
            motd.write(self.finish_message)

    def _revert_action(self):
        pass


class AddInProgressSshLoginMessage(ActiveAction):
    def __init__(self):
        self.name = "add in progress ssh login message"
        self.motd_path = "/etc/motd"
        path_to_script = os.path.abspath(sys.argv[0])
        self.in_progress_message = f"""
===============================================================================
Message from Plesk distupgrade tool:
The server is being converted to AlmaLinux 8. Please wait.
To see the current conversion status, run the '{path_to_script} --status' command.
To monitor the conversion progress in real time, run the '{path_to_script} --monitor' command.
===============================================================================
"""

    def _prepare_action(self):
        common.backup_file(self.motd_path)

        with open(self.motd_path, "a") as motd:
            motd.write(self.in_progress_message)

    def _post_action(self):
        pass

    def _revert_action(self):
        common.restore_file_from_backup(self.motd_path)


class PleskInstallerNotInProgress(CheckAction):
    def __init__(self):
        self.name = "checking if Plesk installer is in progress"
        self.description = "Plesk installer is in progress. Please wait until it is finished. Or use 'plesk installer stop' to abort it."

    def _do_check(self):
        installer_check = subprocess.run(["plesk", "installer", "--query-status", "--enable-xml-output"], stdout=subprocess.PIPE, universal_newlines=True)
        if "query_ok" in installer_check.stdout:
            return True
        return False


class DistroIsCentos79(CheckAction):
    def __init__(self):
        self.name = "checking if distro is CentOS7"
        self.description = """Your distributive is not CentOS 7.9. Unfortunately we are not supporting non CentOS 7.9 distributives yet.
\tIf you use any other version of Centos 7 please update it to Centos 7.9.
"""

    def _do_check(self):
        distro = platform.linux_distribution()
        major_version, minor_version = distro[1].split(".")[:2]
        if distro[0] == "CentOS Linux" and int(major_version) == 7 and int(minor_version) == 9:
            return True
        return False


class DistroIsAlmalinux8(CheckAction):
    def __init__(self):
        self.name = "checking if distro is AlmaLinux8"
        self.description = "Your distributive is not AlmaLinux8. Finish stage can be started only on AlmaLinux8."

    def _do_check(self):
        distro = platform.linux_distribution()
        major_version = distro[1].split(".")[0]
        if distro[0] == "AlmaLinux" and int(major_version) == 8:
            return True
        return False


class PleskVersionIsActual(CheckAction):
    def __init__(self):
        self.name = "checking if Plesk version is actual"
        self.description = "Plesk version should be 18.0.43 or later. Please update Plesk to solve the problem."

    def _do_check(self):
        version_process = subprocess.run(["plesk", "version"], stdout=subprocess.PIPE, universal_newlines=True)
        for line in version_process.stdout.splitlines():
            if line.startswith("Product version"):
                version = line.split()[-1]
                major, _, iter, _ = version.split(".")
                if int(major) >= 18 and int(iter) >= 43:
                    return True
                break

        return False
