# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
""" Creates or updates profiles.

The profile creation works as following:

For each scenario:

- The latest indexed profile is picked on TC, if none we create a fresh profile
- The scenario is done against it
- The profile is uploaded on TC, replacing the previous one as the freshest

For each platform we keep a changelog file that keep track of each update
with the Task ID. That offers us the ability to get a profile from a specific
date in the past.

Artifacts are staying in TaskCluster for 3 months, and then they are removed,
so the oldest profile we can get is 3 months old. Profiles are being updated
continuously, so even after 3 months they are still getting "older".

When Firefox changes its version, profiles from the previous version
should work as expected. Each profile tarball comes with a metadata file
that keep track of the Firefox version that was used and the profile age.
"""
import os

from arsenic import get_session
from arsenic.browsers import Firefox

from condprof.util import fresh_profile, LOG, ERROR
from condprof.scenarii import scenarii
from condprof.client import get_profile, ProfileNotFoundError
from condprof.archiver import Archiver
from condprof.customization import get_customization
from condprof.metadata import Metadata


class ProfileCreator:
    def __init__(self, scenario, customization, archive, changelog, force_new, env):
        self.env = env
        self.scenario = scenario
        self.customization = customization
        self.archive = archive
        self.changelog = changelog
        self.force_new = force_new
        self.customization_data = get_customization(customization)

    def _log_filename(self, name):
        filename = "%s-%s-%s.log" % (
            name,
            self.scenario,
            self.customization_data["name"],
        )
        return os.path.join(self.archive, filename)

    async def run(self, headless=True):
        LOG("Building %s x %s" % (self.scenario, self.customization_data["name"]))
        with self.env.get_device(2828, verbose=True) as device:
            try:
                with self.env.get_browser():
                    metadata = await self.build_profile(device, headless)
            finally:
                self.env.dump_logs()

        if not self.archive:
            return

        LOG("Creating archive")
        archiver = Archiver(self.scenario, self.env.profile, self.archive)
        # the archive name is of the form
        # profile-<platform>-<scenario>-<customization>.tgz
        name = "profile-%(platform)s-%(name)s-%(customization)s.tgz"
        name = name % metadata
        archive_name = os.path.join(self.archive, name)
        dir = os.path.dirname(archive_name)
        if not os.path.exists(dir):
            os.makedirs(dir)
        archiver.create_archive(archive_name)
        LOG("Archive created at %s" % archive_name)
        statinfo = os.stat(archive_name)
        LOG("Current size is %d" % statinfo.st_size)
        if metadata.get("result", 0) != 0:
            LOG("The scenario returned a bad exit code")
            raise Exception("scenario error")
        self.changelog.append("update", **metadata)

    async def build_profile(self, device, headless):
        scenario = self.scenario
        profile = self.env.profile
        customization_data = self.customization_data

        scenario_func = scenarii[scenario]
        if scenario in customization_data.get("scenario", {}):
            options = customization_data["scenario"][scenario]
            LOG("Loaded options for that scenario %s" % str(options))
        else:
            options = {}

        # Adding general options
        options["platform"] = self.env.target_platform

        if not self.force_new:
            try:
                custom_name = customization_data["name"]
                get_profile(profile, self.env.target_platform, scenario, custom_name)
            except ProfileNotFoundError:
                # XXX we'll use a fresh profile for now
                fresh_profile(profile, customization_data)
        else:
            fresh_profile(profile, customization_data)

        LOG("Updating profile located at %r" % profile)
        metadata = Metadata(profile)

        LOG("Starting the Gecko app...")
        self.env.prepare(logfile=self._log_filename("adb"))
        geckodriver_logs = self._log_filename("geckodriver")
        LOG("Writing geckodriver logs in %s" % geckodriver_logs)
        try:
            firefox_instance = Firefox(**self.env.get_browser_args(headless))
            with open(geckodriver_logs, "w") as glog:
                async with get_session(
                    self.env.get_geckodriver(log_file=glog), firefox_instance
                ) as session:
                    self.env.check_session(session)
                    LOG("Running the %s scenario" % scenario)
                    metadata.update(await scenario_func(session, options))
                    LOG("%s scenario done." % scenario)

        except Exception:
            ERROR("%s scenario broke!" % scenario)

        self.env.stop_browser()
        self.env.collect_profile()

        # writing metadata
        metadata.write(
            name=self.scenario,
            customization=self.customization_data["name"],
            version=self.env.get_browser_version(),
            platform=self.env.target_platform,
        )

        LOG("Profile at %s" % profile)
        LOG("Done.")
        return metadata
