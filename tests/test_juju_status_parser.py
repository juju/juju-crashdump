import os
import yaml
from collections import defaultdict
from unittest import TestCase
import jujucrashdump.crashdump as crashdump

ASSETS_PATH = os.path.join(os.path.dirname(__file__), 'assets')


class TestJujuStatusParser(TestCase):
    def test_good_status(self):
        mapping = defaultdict(set, {
            '10.5.0.206': set([
                'ci-configurator/0',
                'machine_1',
                'ci-oil-jenkins/0',
                'ci-oil-config/0'
            ]), '10.5.0.207': set([
                'ci-oil-jenkins-fe/0',
                'machine_2'
            ]), '10.5.0.205': set([
                'machine_0',
                'ci-oil-apache2/0'
            ]), '10.5.0.208': set([
                'ci-oil-postgresql/0',
                'machine_3'
            ]), '10.5.0.209': set([
                'ci-oil-qmaster/0',
                'machine_4',
                'ci-oil-config/1'
            ]), '10.5.0.211': set([
                'machine_5',
                'ci-oil-test-catalog/0'
            ]), '10.5.0.210': set([
                'machine_6', 'ci-oil-weebl/0'
            ])
        })
        units = set([
           'ci-oil-test-catalog/0',
           'ci-oil-postgresql/0',
           'ci-oil-apache2/0',
           'ci-oil-qmaster/0',
           'ci-oil-weebl/0',
           'ci-oil-jenkins-fe/0',
           'ci-oil-jenkins/0'
        ])
        result = (mapping, units)
        with open(os.path.join(ASSETS_PATH, 'good_juju_status.yaml')) as fd:
            self.assertEquals(crashdump.service_unit_addresses(yaml.load(fd)),
                              result)
