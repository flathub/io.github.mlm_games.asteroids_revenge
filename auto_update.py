#!/usr/bin/env python3

# Adapted from https://github.com/flathub/org.vim.Vim/blob/master/auto-update.py


import argparse
import os
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET

import ruamel.yaml

HERE = os.path.abspath(os.path.dirname(__file__))
CLONE = os.path.join(HERE, 'asteroids-revenge')
MANIFEST = os.path.join(HERE, 'io.github.mlm_games.asteroids_revenge.yml')
APPDATA = os.path.join(HERE, 'io.github.mlm_games.asteroids_revenge.metainfo.xml')


def run(args, **kwargs):
    print('$', ' '.join(args))
    return subprocess.run(args, check=True, **kwargs)


def dry_run(args, **kwargs):
    print('would run $', ' '.join(args))


def run_and_read(args):
    result = run(args, stdout=subprocess.PIPE)
    return result.stdout.decode('ascii').strip()


def update_manifest(manifest, tag, sha):
    for module in manifest['modules']:
        if isinstance(module, dict) and module['name'] == 'asteroids-revenge':
            source = module['sources'][0]
            old_tag = source['tag']
            source['tag'] = tag
            source['commit'] = sha
            module['sources'][0] = source
            return old_tag
    return None


def update_appdata(appdata_file, tag, date):
    tree = ET.parse(appdata_file)
    root = tree.getroot()
    release = root.find('releases/release')
    if release is not None:
        release.set('version', tag)
        release.set('date', date)
    tree.write(appdata_file, encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    yaml = ruamel.yaml.YAML()
    with open(MANIFEST, 'r') as f:
        manifest = yaml.load(f)

    if not os.path.exists(CLONE):
        run(('git', 'clone', 'https://github.com/mlm-games/asteroids-revenge.git', CLONE))

    os.chdir(CLONE)
    run(('git', 'pull'))
    sorted_tags = run_and_read(('git', 'tag', '-l', '--sort=-creatordate'))
    tag = sorted_tags.split('\n')[0]
    sha = run_and_read(('git', 'show-ref', '--hash', tag))
    date = run_and_read(('git', 'log', '-1', '--date=short',
                         '--pretty=format:%cd', tag))
    os.chdir(HERE)

    old_tag = update_manifest(manifest, tag, sha)

    with open(MANIFEST, 'w') as f:
        yaml.dump(manifest, f)

    update_appdata(APPDATA, tag, date)

    try:
        run(('git', 'diff-index', '--quiet', 'HEAD', '--'))
    except subprocess.CalledProcessError:
        pass
    else:
        print("Manifest is up-to-date")
        return

    branch = 'update-to-{}'.format(tag)
    f = dry_run if args.dry_run else run

    try:
        f(('git', 'rev-parse', '--verify', '--quiet', branch))
    except subprocess.CalledProcessError:
        # Branch doesn't exist, proceed
        pass
    else:
        # Branch exists, delete it
        f(('git', 'branch', '-D', branch))

    f(('git', 'checkout', '-b', branch))
    f(('git', 'commit', '-am', 'Update to {}'.format(tag)))
    f(('git', 'push', '-u', args.remote, branch))
    f(('hub', 'pull-request', '--no-edit', '-m', textwrap.dedent('''
       Update to {tag}

       Upstream changes: https://github.com/mlm-games/asteroids-revenge/compare/{old_tag}...{tag}

       <i>(This pull request was automatically generated.)</i>
       ''').strip().format(
        tag=tag,
        old_tag=old_tag
    )))


if __name__ == '__main__':
    main()
