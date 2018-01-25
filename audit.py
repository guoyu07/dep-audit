#!/usr/bin/env python

""" This script will extract the exact Git SHA version for all third party dependencies
    in a standard Golang project that uses Dep for package management """

import toml
import urllib2
import sys
import os


ALIASES = {
    'gopkg.in/ini.v1': 'github.com/go-ini/ini',
}

NORMALIZATIONS = {
    'k8s.io': 'github.com/kubernetes',
    'gopkg.in/yaml.v2': 'github.com/go-yaml/yaml'
}


class GithubRawFileFetcher(object):

    """ GithubRawFileFetcher will fetch raw file information from a remote Git project file"""

    def __init__(self, org):
        self.org = org

    def fetch(self, project, filename):
        url = 'https://raw.githubusercontent.com/%s/%s/master/%s'
        conn = urllib2.urlopen(url % (self.org, project, filename))
        return conn.read()

    def fetch_toml(self, project, filename):
        content = self.fetch(project, filename)
        return toml.loads(content)


class Auditor(object):

    """ Auditor will extract a dict in the form {'k8s.io/kubernetes': 'fff5156092b56e6bd60fff75aad4dc9de6b6ef37'}
        with the key as a third party dependency and a value as the exact Git SHA used currently """

    def __init__(self, org, project):
        self.org = org
        self.project = project
        self.fetcher = GithubRawFileFetcher(self.org)

    def __third_party_constraints(self, pkg, lock):
        """ Generates a map of dep : SHA for third party dependencies """
        locked = {project['name']: project['revision'] for project in lock['projects']}
        result = {}
        for constraint in pkg['constraint']:
            dep = constraint['name']
            if dep in ALIASES:
                dep = ALIASES[dep]
            if dep in locked:
                result[dep] = locked[dep]
            else:
                print('Warning: Could not find revision for %s' % dep)
        return result

    def audit(self):
        pkg = self.fetcher.fetch_toml(self.project, "Gopkg.toml")
        lock = self.fetcher.fetch_toml(self.project, "Gopkg.lock")

        return self.__third_party_constraints(pkg, lock)


class Normalizer(object):
    """ Used to normalize the names of dependencies. For instance renaming k8s.io to
        something more accurate for auditing i.e github.com/kubernetes """

    def __init__(self, aliases, normalizations):
        self.aliases = aliases
        self.normalizations = normalizations

    def normalize_dep(self, dep):
        """ Normalise a dependency name so that we use the Github project name rather than
        something like k8s.io """
        for key, value in self.normalizations.iteritems():
            if dep.startswith(key):
                return dep.replace(key, value)
        return dep

    def short_name(self, dep):
        """ Returns the short name of a dependency i.e github.com/go-yaml/yaml => yaml """
        return dep.split('/')[-1]

    def short_sha(self, sha):
        return sha[:7]


def generate_csv_file(project_name, auditor, normalizer):
    deps = auditor.audit()
    csv_file = project_name + '-audit.csv'
    with open(csv_file, 'wb') as io:
        io.write('Dependency,Short Name,SHA\n')
        for dep, sha in deps.iteritems():
            dep_name = normalizer.normalize_dep(dep)
            dep_short_name = normalizer.short_name(dep_name)
            dep_sha = normalizer.short_sha(sha)
            io.write('%s,%s,%s\n' % (dep_name, dep_short_name, dep_sha))


def main(args):
    if len(args) != 2:
        print("Use: python audit.py org project_name i.e. python audit.py oracle oci-flexvolume-driver")
        return sys.exit(1)

    org = args[0]
    project = args[1]
    auditor = Auditor(org, project)
    normalizer = Normalizer(ALIASES, NORMALIZATIONS)
    generate_csv_file(project, auditor, normalizer)


if __name__ == '__main__':
    main(sys.argv[1:])
