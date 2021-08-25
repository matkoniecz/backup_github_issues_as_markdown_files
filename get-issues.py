#!/usr/bin/env python

# Copyright 2014, 2015 Mark Longair
# This script is distributed under the terms of the GNU General Public License.
# See the COPYING file in this repository for the complete text of the license.

import doctest
import errno
import hashlib
import json
from optparse import OptionParser
import os
from os.path import dirname, exists, isdir, join, realpath, relpath, splitext
import re
import requests

with open(join(os.environ['HOME'], '.oauth-private-repository-control-for-github-backup.json')) as f: # tokens can be generated at https://github.com/settings/tokens
    token = json.load(f)['token']

standard_headers = {'User-Agent': 'github-issues-printer/1.0',
                    'Authorization': 'bearer {0}'.format(token)}

cwd = os.getcwd()
repo_directory = realpath(join(dirname(__file__)))
images_directory = relpath(join(repo_directory, 'images'), cwd)
mds_directory = relpath(join(repo_directory, 'markdown_files'), cwd)


def mkdir_p(d):
    try:
        os.makedirs(d)
    except OSError as e:
        if e.errno == errno.EEXIST and isdir(d):
            pass
        else:
            raise


mkdir_p(images_directory)
mkdir_p(mds_directory)


def replace_image(match, download=True):
    """Rewrite an re match object that matched an image tag

    Download the image and return a version of the tag rewritten
    to refer to the local version.  The local version is named
    after the MD5sum of the URL.
    
    >>> m = re.search(r'\!\[(.*?)\]\((.*?)\)',
    ...               'an image coming up ![caption](http://blah/a/foo.png)')
    >>> replace_image(m, download=False)
    '![caption](github-print-issues/images/b62082dd8a02ea495f5e3c293eb6ee67.png)'
    """

    caption = match.group(1)
    url = match.group(2)
    hashed_url = hashlib.md5(url).hexdigest()
    extension = splitext(url)[1]
    if not extension:
        raise Exception("No extension at the end of {0}".format(url))
    image_filename = join(images_directory, hashed_url) + extension
    if download:
        if not exists(image_filename):
            r = requests.get(url)
            with open(image_filename, 'w') as f:
                f.write(r.content)
    return "![{0}]({1})".format(caption.encode('utf-8'), image_filename)


def replace_images(md):
    """Rewrite a Markdown string to replace any images with local versions

    'md' should be a GitHub Markdown string; the return value is a version
    of this where any references to images have been downloaded and replaced
    by a reference to a local copy.
    """

    return re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, md)


def download(repo):
    page = 1
    raw = open('raw_json.json', 'w')
    while True:
        issues_url = 'https://api.github.com/repos/{0}/issues'.format(repo)
        r = requests.get(issues_url,
                         params={'per_page': '100',
                                 'page': str(page),
                                 'state': 'all'},
                         headers=standard_headers)
        if r.status_code != 200:
            raise Exception("HTTP status {0} on fetching {1}".format(
                r.status_code,
                issues_url))

        issues_json = r.json()
        if len(issues_json) == 0:
            raw.close()
            break

        for issue in issues_json:
            number = issue['number']
            md_filename = 'markdown_files/' + str(number) + '.md'
            if exists(md_filename):
                continue

            raw.write(str(issue))
            raw.write("\n")

            print number

            title = issue['title'].encode('utf-8')
            body = issue['body'].encode('utf-8')
            labels = issue['labels']

            with open(md_filename, 'w') as f:
                f.write("# {0} {1}\n\n".format(number, title))
                nick = issue['user']['login'].encode('utf-8')
                f.write("### Reported by {0}\n\n".format(nick))
                f.write("### State: {0}\n\n".format(issue['state']))
                f.write("### Labels:\n")
                for label in labels:
                    name = label['name'].encode('utf-8')
                    color = label['color']
                    f.write("{0}\n{1}\n".format(name, color))
                f.write("\n")
                # Increase the indent level of any Markdown heading
                body = re.sub(r'^(#+)', r'#\1', body)
                body = replace_images(body)
                f.write(body)
                f.write("\n\n")
                if issue['comments'] > 0:
                    comments_request = requests.get(issue['comments_url'],
                                                    headers=standard_headers)
                    for comment in comments_request.json():
                        f.write("### Comment from {0}\n\n".format(comment['user']['login']))
                        comment_body = comment['body']
                        comment_body = re.sub(r'^(#+)', r'###\1', comment_body)
                        comment_body = replace_images(comment_body)
                        f.write(comment_body.encode('utf-8'))
                        f.write("\n\n")
        page += 1
        if 'Link' not in r.headers:
            break


import shutil


def move(repo):
    shutil.move(images_directory, join(mds_directory, 'images'))
    shutil.move('raw_json.json', join(mds_directory, 'raw_json.json'))
    shutil.move(mds_directory, repo.replace('/', '-'))


usage = """Usage: %prog [options] REPOSITORY

Repository should be username/repository from GitHub, e.g. mysociety/pombola"""
parser = OptionParser(usage=usage)
parser.add_option("-t", "--test",
                  action="store_true", dest="test", default=False,
                  help="Run doctests")

(options, args) = parser.parse_args()

if options.test:
    doctest.testmod()
else:
    if len(args) != 1:
        parser.print_help()
    else:
        download(args[0])
        move(args[0])
