#!/usr/bin/env python
#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import os
import sys
import subprocess

JAVAP_COMMAND = "/usr/bin/javap"

def classname_iter(classlist):
    with open(classlist, "rb") as f:
        for L in f:
            classname = L.rstrip().decode("utf-8")
            classname = classname.replace('/', '.')
            yield classname

def disassemble(classname, classpath=None):
    cmd = [JAVAP_COMMAND]
    if classpath:
        cmd.extend(["-classpath", classpath])
    cmd.extend(["-c", "-p", "-l", "-constants", classname])
    text = subprocess.check_output(cmd)
    text = text.decode("utf-8")
    return text

def main(argv):
    from argparse import ArgumentParser
    psr = ArgumentParser(description="Disassemble java class(s)")
    psr.add_argument('class_list', nargs='*', action='store')
    psr.add_argument('-o', '--output-dir', action='store', required=True)
    grp = psr.add_mutually_exclusive_group(required=False)
    grp.add_argument('--classpath', action='store')
    grp.add_argument('--jar', action='store')
    args = psr.parse_args(argv[1:])
    
    outputdir = args.output_dir
    classlist = args.class_list
    classpath = args.classpath
    classnames = []

    if not os.path.isdir(outputdir):
        if os.path.exists(outputdir):
            sys.exit("output directory already exists: %s" % outputdir)
        os.mkdir(outputdir)
    
    if args.jar:
        sys.stderr.write('> extracting files form jar file\n')
        import unzip_jar
        dest_dir = unzip_jar.gen_dest_dir_name(args.jar)
        classlist.append(os.path.join(dest_dir, "class_list"))
        classpath = dest_dir
        unzip_jar.main(["unzip_jar.py", args.jar])
    elif classpath:
        if not classlist:
            class_ext = u".class"
            class_ext_len = len(class_ext)
            for root, dirs, files in os.walk(classpath.decode("utf-8")):
                relpath = os.path.relpath(root, start=classpath)
                if relpath == u".":
                    relpath = ""
                assert not relpath.startswith(u".")
                package = relpath.replace(os.sep, u".")
                if package:
                    package = package + u"."
                for f in files:
                    if f.endswith(class_ext):
                        class_name = f[:-class_ext_len]
                        classnames.append(package + class_name)

    def classname_it():
        if classlist:
            for clfile in classlist:
                for cn in classname_iter(clfile):
                    yield cn
        if classnames:
            for cn in classnames:
                yield cn

    sys.stderr.write('> disassembling class files\n')
    for classname in classname_it():
        text = disassemble(classname, classpath=classpath)
        outputfile = os.path.join(outputdir, classname + ".asm")
        with open(outputfile, "wb") as outp:
            outp.write(text.encode("utf-8"))

if __name__ == '__main__':
    main(sys.argv)

