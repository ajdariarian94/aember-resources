"""The kas container's CPU cap."""

import os
import unittest
from unittest import mock

from aember.utils import kas_container


class CpuLimitTest(unittest.TestCase):
    # Regression: Yocto builds on every core crashed the WSL host; the kas
    # container gets 66% of the CPUs.
    def test_regression_never_every_core(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            kas_container.os, "cpu_count", return_value=16
        ):
            self.assertEqual(kas_container.cpu_limit(), "10.56")

    def test_at_least_one_cpu(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            kas_container.os, "cpu_count", return_value=1
        ):
            self.assertEqual(kas_container.cpu_limit(), "1.00")

    def test_override(self):
        with mock.patch.dict(os.environ, {"AEMBER_KAS_CPUS": "4"}):
            self.assertEqual(kas_container.cpu_limit(), "4")


if __name__ == "__main__":
    unittest.main()
