#coding: utf-8

"""
javap's disassembled file manipulation.
"""

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import os
import re

from _utilities import readline_iter

import type_formatter as tf

def indent_width(L):
    for i, c in enumerate(L):
        if c != ' ':
            return i
    return 0

def asm_file_iter(asmdir):
    for root, dirs, files in os.walk(asmdir, topdown=True):
        dirs.sort()
        files.sort()
        for f in files:
            if f.endswith(".asm"):
                yield os.path.join(root, f)

def asm_filetext_iter(asmdir):
    for asmfile in asm_file_iter(asmdir):
        yield asmfile, list(readline_iter(asmfile))

def remove_generics_args(s):
    if re.match(r"^\s+((public|private|static|final)\s+)*(java.lang.String|char) .*$", s) and \
            s.find(" = ") >= 0:
        return s

    c = ''
    p = s.find('//')
    if p >= 0:
        s, c = s[:p], s[p:]

    p = s.rfind('<')
    while p >= 0:
        q = s.find('>', p)
        assert q >= 0
        if re.match(r'^\s*$', s[:p]) and len(s) >= q + 3 and s[q+1] == ' ' and re.match(r'\w', s[q+2]):
            s = s[:p] + s[q+2:]  # such as "    <T extends Hoge> T fuga(T a);"
        else:
            s = s[:p] + s[q+1:]
        p = s.rfind('<')

    return s + c

COMPILED_FROM = 'COMPILED_FROM'
METHOD_CODE = 'METHOD_CODE'
INHERITANCE = 'INHERITANCE'

def split_into_method_iter(asmfile, lines):
    method_attribute = frozenset("public|private|protected|final|abstract|synchronized|static".split('|'))
    pat_compiled_from = re.compile(r'^Compiled from\s+"(?P<file>[^"]+)"')
    typ = r'(\w|[.$\[\]])+'
    pat_class = re.compile(r'^((public|private|final|abstract|strictfp) +)*class +(?P<id>TYP) +({|extends|implements)'.replace('TYP', typ))
    pat_interface = re.compile(r'^((public|private|abstract|strictfp) +)*interface +(?P<id>TYP) +({|extends)'.replace('TYP', typ))
    pat_static = re.compile(r'^  static +{};$')
    pat_method = re.compile(r'^  ((public|private|protected|final|abstract|synchronized|static) +)*(?P<retv>TYP) +(?P<name>[\w$]+)[(](?P<args>((TYP, )*TYP)?)[)](;| +throws)'.replace('TYP', typ))
    pat_ctor = re.compile(r'^  ((public|private|protected) +)*(?P<name>TYP)[(](?P<args>((TYP, )*TYP)?)[)](;| +throws)'.replace('TYP', typ))

    def pack(class_name, method_sig, method_body):
        if class_name == None:
            assert False
        p = class_name.find('<')
        if p >= 0:
            class_name = class_name[:p]
        return ((class_name, method_sig), method_body)

    class_name, method_sig, method_body = None, None, None

    def scan_extends_and_implements(L):
        fields = re.split('{| extends | implements ', L)
        fields = filter(None, [f.strip() for f in fields])
        lf = len(fields)
        if lf == 1:
            return (), ()
        elif lf == 2:
            return (fields[1].strip(), ), ()
        elif lf == 3:
            return (fields[1].strip(), ), tuple(filter(None, [i.strip() for i in fields[2].split(',')]))
        else:
            assert False
    
    for ln, L in enumerate(lines):
        if not L: continue # skip empty lines
        L = remove_generics_args(L)

        iw = indent_width(L)
        if iw == 0:
            m = pat_compiled_from.match(L)
            if m:
                yield COMPILED_FROM, m.group('file')
            else:
                m = pat_class.match(L)
                if m:
                    if class_name and method_sig:
                        yield METHOD_CODE, pack(class_name, method_sig, method_body)
                        method_sig, method_body = None, None
                    class_name = m.group('id')
                    class_name = tf.format_sig_in_javap_comment_style(class_name, None, None, None)
                    imps, exts = scan_extends_and_implements(L)
                    yield INHERITANCE, (class_name, imps, exts)
                else:
                    m = pat_interface.match(L)
                    if m:
                        if class_name and method_sig:
                            yield METHOD_CODE, pack(class_name, method_sig, method_body)
                            method_sig, method_body = None, None
                        class_name = None
                    else:
                        if L.startswith("Compiled from ") or L == "}":
                            pass
                        else:
                            raise AssertionError("unexpected line: %s: %d: %s" % (asmfile, ln + 1, L))
        elif iw == 2:
            m = pat_method.match(L)
            if m and m.group('retv') not in method_attribute:
                if class_name and method_sig:
                    yield METHOD_CODE, pack(class_name, method_sig, method_body)
                    method_sig, method_body = None, None
                args = m.group('args') or ''
                args = tuple(filter(None, args.split(', ')))
                method_sig = tf.format_sig_in_javap_comment_style(None, m.group('name'), args, m.group('retv'))
                method_body = []
            else:
                m = pat_ctor.match(L)
                if m:
                    if class_name and method_sig:
                        yield METHOD_CODE, pack(class_name, method_sig, method_body)
                        method_sig, method_body = None, None
                    args = m.group('args') or ''
                    args = tuple(filter(None, args.split(', ')))
                    method_sig = tf.format_sig_in_javap_comment_style(None, '"<init>"', args, 'void')
                    method_body = []
                else:
                    m = pat_static.match(L)
                    if m:
                        if class_name and method_sig:
                            yield METHOD_CODE, pack(class_name, method_sig, method_body)
                            method_sig, method_body = None, None
                        method_sig = tf.format_sig_in_javap_comment_style(None, '"static{}"', (), 'void')
                        method_body = []
        else:
            method_body.append(L)

    if class_name and method_sig:
        yield METHOD_CODE, pack(class_name, method_sig, method_body)
        method_sig, method_body = None, None

def split_method_body_to_code_and_tables(method_body_lines):
    code_lines = []
    exceptiontable_lines = []
    linenumbertable_lines = []
    target = dummy = []
    for L in method_body_lines:
        if L == "    Code:":
            target = code_lines
        elif L == "    Exception table:":
            target = exceptiontable_lines
        elif L == "    LineNumberTable:":
            target = linenumbertable_lines
        elif L == "    LocalVariableTable:":
            target = dummy
        else:
            target.append(L)
    return code_lines, exceptiontable_lines, linenumbertable_lines

ASM_FILE = 'ASM_FILE'

def get_asm_info_iter(asm_dir):
    """
    Iterate each method definition of each disassembled file in 'asm_dir' directory.
    Yielded values
       typ: ASM_FILE, COMPILED_FROM, METHOD_CODE, or INHERITANCE
       values: string or tuple
       
       when typ == ASM_FILE, values is a string, name of a disassembled file.

       when COMPILED_FROM == 'COMPILED_FROM', values is a string,
         name of source file recorded in bytecode.

       when typ == METHOD_CODE, values is a tuple, which contains:
         sig: signature of the method (str)
         code: definition of the method (list of str)
         exception table: exception table of the method (list of str)
         linenum_table: line number table (list of str)

       when typ == INHERITANCE, values is a tuple, which contains:
         claz: (str)
         extends: its exntending classes (list of str, length is 0 or 1)
         implements: its implementing interfaces (list of str)
    """

    def search_asmdir(asmdir):
        for asmfile, lines in asm_filetext_iter(asmdir):
            yield ASM_FILE, asmfile
            for v in split_into_method_iter(asmfile, lines):
                yield v

    for typ, values in search_asmdir(asm_dir):
        if typ in (ASM_FILE, COMPILED_FROM, INHERITANCE):
            yield typ, values
        elif typ == METHOD_CODE:
            claz_sig, body = values
            code, exception_table, linenum_table = split_method_body_to_code_and_tables(body)
            yield typ, (claz_sig, code, exception_table, linenum_table)
        else:
            assert False
