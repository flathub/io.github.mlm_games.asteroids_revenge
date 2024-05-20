#!/usr/bin/env python3
import argparse
import collections
import json
import os
import subprocess
import xml.etree.ElementTree as ET

HERE = os.path.abspath(os.path.dirname(__file__))
ASTEROIDS_CLONE = os.path.join(HERE, 'asteroids_revenge')
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


def update_appdata(tag, date):
    """Update the appdata XML file with the new version and date using an XML parser."""
    tree = ET.parse(APPDATA)
    root = tree.getroot()

    # Find the release element and update the version and date
    release = root.find(".//release")
    if release is not None:
        release.set("version", tag)
        release.set("date", date)

    # Write the updated XML back to the file
    tree.write(APPDATA, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with open(MANIFEST, 'r') as f:
        manifest = json.load(f, object_pairs_hook=collections.OrderedDict)

    asteroids_source = manifest['modules'][-1]['sources'][0]

    if not os.path.isdir(ASTEROIDS_CLONE):
        run(('git', 'clone', asteroids_source['url'], ASTEROIDS_CLONE))

    os.chdir(ASTEROIDS_CLONE)
    run(('git', 'pull'))
    sha = run_and_read(('git', 'rev-parse', 'HEAD'))
    tag = run_and_read(('git', 'describe', '--tags', 'HEAD'))
    date = run_and_read(('git', 'log', '-1', '--date=short',
                         '--pretty=format:%cd'))
    os.chdir(HERE)

    # Patch manifest
    old_tag = asteroids_source.get('tag', '')
    asteroids_source['tag'] = tag
    asteroids_source['commit'] = sha
    manifest['modules'][-1]['sources'][0] = asteroids_source

    with open(MANIFEST, 'w') as f:
        json.dump(fp=f, obj=manifest, indent=2)

    # Patch appdata using an XML parser
    update_appdata(tag, date)

    try:
        run(('git', 'diff-index', '--quiet', 'HEAD', '--'))
    except subprocess.CalledProcessError:
        pass
    else:
        print("Manifest is up-to-date")
        return

    branch = 'update-to-{}'.format(tag)
    title = f"Update to {tag}"
    body = f"Upstream changes: {asteroids_source['url']}/compare/{old_tag}...{tag}"
    f = dry_run if args.dry_run else run
    f(('git', 'checkout', '-b', branch))
    f(('git', 'commit', '-am', title + "\n\n" + body))
    f(("git", "push", "-u", args.remote, branch))
    f(("gh", "pr", "create", "--title", title, "--body", body))


if __name__ == '__main__':
    main()