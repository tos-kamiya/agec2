#!/usr/bin/env python
#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import os.path
import re
import sys
import subprocess

UNIZP_COMMAND = "/usr/bin/unzip"

def get_class_names_from_jar(jar_file):
    class_names = []
    pat = re.compile(r"^\s*testing:\s*(.+)[.]class\s+OK\s*$")
    text = subprocess.check_output([UNIZP_COMMAND, "-t", jar_file])
    for L in text.split('\n'):
        L = L.rstrip()
        m = pat.match(L)
        if m:
            class_names.append(m.group(1))
    return class_names

def gen_dest_dir_name(jar_file):
    return jar_file + ".files"

def main(argv):
    from argparse import ArgumentParser
    psr = ArgumentParser(description="Expand a jar file to extract class files and class list")
    psr.add_argument('jar_file', action='store')
    args = psr.parse_args(argv[1:])
    
    dest_dir = gen_dest_dir_name(args.jar_file)
    if os.path.exists(dest_dir):
        sys.exit("output directory already exists: %s" % dest_dir)
    
    os.mkdir(dest_dir)
    
    class_names = get_class_names_from_jar(args.jar_file)
    with open(os.path.join(dest_dir, "class_list"), "wb") as f:
        for cn in class_names:
            f.write("%s\n" % cn)

    subprocess.check_call([UNIZP_COMMAND, args.jar_file, "-d", dest_dir])
    
if __name__ == '__main__':
    main(sys.argv)