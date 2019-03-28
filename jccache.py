#!/usr/bin/env python

from __future__ import absolute_import, print_function
import argparse
import hashlib
import os
import shutil
import subprocess
import sys


def build_argument_parser():
    parser = argparse.ArgumentParser('Java compile cache')
    parser.add_argument('-c', '--cleanup', dest='cleanup', action='store_true', help='delete old files and recalculate size counters'
                          '(normally not needed as this is done automatically)')
    parser.add_argument('-C', '--clear', dest='clear', action='store_true', help='clear the cache completely (except configuration)')
    parser.add_argument('-F', '--max-entries', dest='max_entries', type=int, help='set maximum number of files in cache to N (use 0 for no limit)')
    parser.add_argument('-M', '--max-size', dest='max_size', type=int, help='set maximum size of cache to SIZE (use 0 for no'
                          'limit); available suffixes: k, M, G, T (decimal) and'
                          'Ki, Mi, Gi, Ti (binary); default suffix: G')
    # parser.add_argument('-o', '--set-config'=K=V  set configuration key K to value V
    parser.add_argument('-p', '--print-config', dest='print_config', action='store_true', help='print current configuration options')
    parser.add_argument('-s', '--show-stats', dest='show_stats', action='store_true', help='show statistics summary')
    parser.add_argument('-z', '--zero-stats', dest='zero_stats', action='store_true', help='zero statistics counters')

    parser.add_argument('-V', '--version', action='version', version='%(prog)s 1.0')
    return parser


class Cache(object):
    def __init__(self, options):
        self.__basedir = os.path.expanduser('~/.jccache')

    def obtain_dir(self, hashcode):
        """Put files in path into cache"""
        path = os.path.join(self.__basedir, hashcode)
        hit = True
        if not os.path.exists(path):
            hit = False
            os.makedirs(path)
        return hit, path

    def release(self, hashcode):
        pass

# All known javac options with a space seperated arg, from the 'java -help'
_FLAGS_HAS_ARGS = frozenset([
    '-classpath', '-cp', '-bootstrap', '-extdirs', '-endorseddirs',
    '-processorpath', '-d', '-s', '-h', '-encoding', '-source', '-target', '-profile'
])


def run_javac(javac, options, classes_dir, source):
    args = [javac] + options + ['-d', classes_dir] + source
    p = subprocess.Popen(args)
    p.wait()
    return p.returncode


def parse_java_command_line(args):
    options = []
    classes_dir = None
    sources = []
    need_classes_dir = False
    need_value = False
    for arg in args:
        if arg.startswith('-'):
            if arg == '-d':
                need_classes_dir = True
            else:
                options.append(arg)
                if arg in _FLAGS_HAS_ARGS:
                    need_value = True
        elif need_classes_dir:
            classes_dir = arg
            need_classes_dir = False
        elif need_value:
            options.append(arg)
            need_value = False
        else:
            sources.append(arg)

    return options, classes_dir, sources


def find_javac(args):
    for i, arg in enumerate(args):
        if arg.endswith('javac'):
            return i
    return -1


def get_command_hash(javac, options, sources):
    m = hashlib.md5()
    m.update(javac)
    for o in options:
        m.update(o)
    for s in sources:
        m.update(s)
    return m.hexdigest()


def parse_command_line():
    parser = build_argument_parser()
    javac_pos = find_javac(sys.argv)
    if javac_pos < 0:
        options = parser.parse_args()
        return None, None, None
    options = sys.argv[1:javac_pos]
    options = parser.parse_args(options)
    javac = sys.argv[javac_pos]
    javac_args = sys.argv[javac_pos+1:]
    return options, javac, javac_args


def copy_out_of_cache(cache_dir, classes_dir):
    root_src_dir = cache_dir
    root_dst_dir = classes_dir
    for src_dir, dirs, files in os.walk(root_src_dir):
        dst_dir = src_dir.replace(root_src_dir, root_dst_dir, 1)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.copy(src_file, dst_dir)


def main():
    options, javac, javac_args = parse_command_line()
    if not javac:
        return
    cache = Cache(options)
    javac_options, classes_dir, sources = parse_java_command_line(javac_args)
    if not sources or '-help' in javac_options or '-version' in javac_options:
        return subprocess.call([javac] + javac_options + sources)
    if sources and not classes_dir:
        print("-d is required for use jccache")
        return

    if not os.path.exists(classes_dir):
        # Let javac report error
        return run_javac(javac, javac_options, classes_dir, sources)

    cmdhash = get_command_hash(javac, javac_options, sources)
    hit, cache_dir = cache.obtain_dir(cmdhash)
    cache_classes_dir = os.path.join(cache_dir, 'classes')
    if not hit:
        os.mkdir(cache_classes_dir)
        ret = run_javac(javac, javac_options, cache_classes_dir, sources)
        if ret != 0:
            os.rmdir(cache_classes_dir)
            return ret
    copy_out_of_cache(cache_classes_dir, classes_dir)


if __name__ == '__main__':
    main()
