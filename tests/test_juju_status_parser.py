import os
import yaml
from collections import defaultdict
from unittest import TestCase
import jujucrashdump.crashdump as crashdump

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")


class TestJujuStatusParser(TestCase):
    def __check_status(self, filename, dict_):
        mapping = defaultdict(set, dict_)
        with open(os.path.join(ASSETS_PATH, filename)) as fd:
            self.assertEqual(
                crashdump.service_unit_addresses(yaml.safe_load(fd)), mapping
            )

    def test_good_status(self):
        mapping = {
            "1": set(
                [
                    "ci-configurator/0",
                    "10.5.0.206",
                    "ci-oil-jenkins/0",
                    "ci-oil-config/0",
                ]
            ),
            "2": set(["ci-oil-jenkins-fe/0", "10.5.0.207"]),
            "0": set(["10.5.0.205", "ci-oil-apache2/0"]),
            "3": set(["ci-oil-postgresql/0", "10.5.0.208"]),
            "4": set(["ci-oil-qmaster/0", "10.5.0.209", "ci-oil-config/1"]),
            "5": set(["10.5.0.211", "ci-oil-test-catalog/0"]),
            "6": set(["10.5.0.210", "ci-oil-weebl/0"]),
        }
        self.__check_status("good_juju_status.yaml", mapping)

    def test_bad_status(self):
        mapping = {
            "0/lxd/4": set(["magpie/0", "10.245.214.27"]),
            "1": set(["magpie/1", "10.245.214.28"]),
            "0/lxd/1": set(["landscape-server/0", "10.245.214.3"]),
            "0/lxd/0": set(["haproxy/0", "10.245.214.2"]),
            "0": set(["10.245.214.1"]),
            "0/lxd/3": set(["rabbitmq-server/0", "10.245.214.5"]),
            "0/lxd/2": set(["postgresql/0", "10.245.214.4"]),
        }
        self.__check_status("bad_juju_status.yaml", mapping)
