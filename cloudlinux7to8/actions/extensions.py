# Copyright 2025. WebPros International GmbH. All rights reserved.

import typing

from pleskdistup import actions as common_actions
from pleskdistup.common import action, util, leapp_configs, files


class FixupImunify(action.ActiveAction):
    def __init__(self):
        self.name = "fixing up imunify360"

    def _find_imunify_repo_files(self) -> typing.List[str]:
        return files.find_files_case_insensitive("/etc/yum.repos.d", ["imunify*.repo"])

    def _is_required(self) -> bool:
        return len(self._find_imunify_repo_files()) > 0

    def _prepare_action(self) -> action.ActionResult:
        repofiles = self._find_imunify_repo_files()

        leapp_configs.add_repositories_mapping(repofiles)

        # For some reason leapp replaces the libssh2 package on installation. It's fine in most cases,
        # but imunify packages require libssh2. So we should use PRESENT action to keep it.
        leapp_configs.set_package_action("libssh2", leapp_configs.LeappActionType.PRESENT)
        return action.ActionResult()

    def _post_action(self) -> action.ActionResult:
        return action.ActionResult()

    def _revert_action(self) -> action.ActionResult:
        return action.ActionResult()


class AdoptKolabRepositories(action.ActiveAction):
    def __init__(self):
        self.name = "adopting kolab repositories"

    def _find_kolab_repo_files(self) -> typing.List[str]:
        return files.find_files_case_insensitive("/etc/yum.repos.d", ["kolab*.repo"])

    def _is_required(self) -> bool:
        return len(self._find_kolab_repo_files()) > 0

    def _prepare_action(self) -> action.ActionResult:
        repofiles = self._find_kolab_repo_files()

        leapp_configs.add_repositories_mapping(
            repofiles,
            ignore=[
                "kolab-16-source",
                "kolab-16-testing-source",
                "kolab-16-testing-candidate-source",
            ]
        )
        return action.ActionResult()

    def _post_action(self) -> action.ActionResult:
        for file in self._find_kolab_repo_files():
            leapp_configs.adopt_repositories(file)

        util.logged_check_call(["/usr/bin/dnf", "-y", "update"])
        return action.ActionResult()

    def _revert_action(self) -> action.ActionResult:
        return action.ActionResult()

    def estimate_prepare_time(self) -> int:
        return 30

    def estimate_post_time(self) -> int:
        return 2 * 60


class FetchKernelCareGPGKey(common_actions.FetchGPGKeyForLeapp):
    def __init__(self):
        self.name = "fetching KernelCare GPG key"
        self.target_repository_files_regex = ["kernelcare*.repo"]
        super().__init__()


class FetchPleskGPGKey(common_actions.FetchGPGKeyForLeapp):
    def __init__(self):
        self.name = "fetching Plesk GPG key"
        self.target_repository_files_regex = ["plesk*.repo"]
        super().__init__()
