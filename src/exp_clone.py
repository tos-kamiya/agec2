#!/usr/bin/env python
#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import re
import sys

from _utilities import sort_uniq

import asm_manip as am
import ope_manip as om
import type_formatter as tf
import clonefile_manip as cm

import gen_ngram as ng
import precomp_manip as pm

def extract_class_from_loc_linenum(L):
    pat_loc_linenum = re.compile(r'^\s*([\w_$/.]+)[.]java\s*:\s*(\d+)\s+>\s*(\d+)\s*//\s*(.+)$')
    m = pat_loc_linenum.match(L)
    if m is None:
        return None

    claz_like, method_like = m.group(1), m.group(4)

    p = method_like.find("(")
    assert p >= 0
    q = method_like[:p].find('.')
    if q >= 0:
        inner_claz = method_like[:q]
        method_like = method_like[q+1:]
        claz_like += "$" + inner_claz

    claz, sig = tf.scan_in_javap_comment_style(claz_like + "." + method_like)
    return claz, sig

class ParseError(ValueError):
    pass

def extract_poeseq_and_ngrams(target_opeseq, locs, method2claz2precomp, 
        ngram_size, max_call_depth=-2, allow_repetitive_ngram=False,
        no_branch_ngram=False):
    target_opeseq_len = len(target_opeseq)
    if target_opeseq_len == 0:
        raise ParseError("empty ope sequence")
    if ngram_size == -1:
        ngram_size = target_opeseq_len
    else:
        if target_opeseq_len != ngram_size:
            raise ParseError("length of ope sequence doesn't match to --ngram-size agrgument")

    target_opeseq = tuple(target_opeseq)
    
    pat_loc_index = re.compile(r'\s*([^,]+),\s*(\d+)\s*>(\d+)')

    target_claz_methods = None
    target_claz_method_to_indices = {}
    if locs is not None:
        tcm_set = set()
        target_claz_methods = []
        for L in locs:
            cs = extract_class_from_loc_linenum(L)
            if cs:
                claz, sig = cs
                index = None
            else:
                m = pat_loc_index.match(L)
                if m:
                    claz_sig = m.group(1)
                    claz, sig = tf.scan_in_javap_comment_style(claz_sig)
                    index = int(m.group(2))
                    target_claz_method_to_indices.setdefault((claz, sig), []).append(index)
                else:
                    raise ParseError("invalid loc line: %s" % L)
            cm = (claz, sig)
            if cm not in tcm_set:
                tcm_set.add(cm)
                target_claz_methods.append(cm)
        del tcm_set

    if target_claz_methods is None:
        target_claz_methods = sorted((claz, method) for method, claz2pre in method2claz2precomp.iteritems() \
                for claz in claz2pre.iterkeys())

    ngrams_of_target_opeseq = []
    for claz, method in target_claz_methods:
        c2c = method2claz2precomp.get(method)
        assert c2c != None
        precomp = c2c.get(claz)
        assert precomp != None
        found_ngrams = ng.gen_code_ngrams(claz, method, method2claz2precomp,
                ngram_size, start_indices=target_claz_method_to_indices.get((claz, method)), 
                max_call_depth=max_call_depth, allow_repetitive_ngram=allow_repetitive_ngram,
                no_branch_ngram=no_branch_ngram)
        for ngrams in ng.to_ngram_tuples_iter(found_ngrams):  
            for ngram in ngrams:
                opeseq = tuple(cm for cm, _, _ in ngram)
                if opeseq == target_opeseq:
                    ngrams_of_target_opeseq.append(ngram)

    return ngrams_of_target_opeseq

def extract_clat(ngrams):
    # common location among traces
    if not ngrams:
        return []

    common_locs = set([loc for _, loc, _ in ngrams[0]])
    for ngram in ngrams[1:]:
        locs = set([loc for _, loc, _ in ngram])
        common_locs.intersection_update(locs)

    return common_locs

def extract_max_depth(ngrams):
    if not ngrams:
        return 0

    max_depth = max(depth for ngram in ngrams for _, _, depth in ngram)
    return max_depth

def extract_max_depth_from_locs(locs):
    depths = [0]
    for L in locs:
        p = L.find('>')
        assert p >= 0
        depth = int(L[p + 1])
        depths.append(depth)
    return max(depths)

def extract_unique_method_count_from_opeseq(opeseq):
    return len(set(opeseq))

def extract_unique_method_count(ngrams):
    return extract_unique_method_count_from_opeseq([ope for ope, _, _ in ngrams[0]])

def gen_argpsr():
    from argparse import ArgumentParser
    from _version_data import VERSION
    psr = ArgumentParser(description="Expand clone's each location to a trace")
    psr.add_argument('-a', '--asm-directory', action='store')
    psr.add_argument('clone_file', action='store',
            help="options and clones to be expanded. part of clone-index (generated by det_clone.py) or clone-linenum file (generated by tosl_clone.py). specify '-' to read from stdin")
    psr.add_argument('-t', '--loc-to-trace', action='store_true',
            help='expand each clone location to trace')
    psr.add_argument('-c', '--add-metric-clat', action='store_true',
            help='add common-location-among-traces metric to each clone')
    psr.add_argument('-d', '--add-metric-max-depth', action='store_true',
            help='add max-depth metric to each clone')
    psr.add_argument('-u', '--add-metric-unique-method', action='store_true',
            help='add unique-method count to each clone')
    psr.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
    return psr

def main(argv):
    psr = gen_argpsr()
    args = psr.parse_args(argv[1:])

    if not any([args.add_metric_clat, args.add_metric_max_depth, args.add_metric_unique_method, args.loc_to_trace]):
        sys.exit("no action specfield. specify one or more of options, -t, -c, -d and -u")

    code_ngram_needed = args.add_metric_clat or args.loc_to_trace
    if code_ngram_needed and args.asm_directory is None:
        sys.exit("such as option -t or -c requires option -a")

    def itfunc():
        for sec, data in cm.read_clone_file_iter(args.clone_file):
            yield sec, data
    clonefile_iter = itfunc()

    for sec, data in clonefile_iter:
        if sec == cm.OPTIONS:
            clone_data_args = data
            break  # for sec
        else:
            sys.exit('clone file missing option section')

    ngram_size = clone_data_args.ngram_size
    max_call_depth = clone_data_args.max_call_depth
    max_method_definition = clone_data_args.max_method_definition
    exclude = clone_data_args.exclude
    allow_repetitive_ngram = clone_data_args.get("allow-repetitive-ngram")
    no_branch_ngram = clone_data_args.get("no-branch-ngram")

    sig2code = {}
    #sig2exceptiontable = {}
    #sig2linenumbertable = {}

    claz2deriving = {}  # claz -> list of the clazs that inherit it
    for typ, values in am.get_asm_info_iter(args.asm_directory):
        if typ == am.METHOD_CODE:
            claz_sig, code, etbl, ltbl = values
            sig2code[claz_sig] = tuple(code)
            #sig2exceptiontable[sig] = etbl
            #sig2linenumbertable[sig] = ltbl
        elif typ == am.INHERITANCE:
            claz, imps, exts = values
            for e in exts:
                claz2deriving.setdefault(e, []).append(claz)

    sig2oplist = {}
    for claz_sig, method_body in sorted(sig2code.iteritems()):
        ol = om.body_text_to_ope_list(method_body, claz_sig)
        sig2oplist[claz_sig] = ol
    del sig2code

    method2claz2code = ng.make_method2claz2code(sig2oplist)
    del sig2oplist
    claz2methods = ng.make_claz2methods(method2claz2code)

    if exclude:
        ng.exclude_clazs(method2claz2code, exclude)

    if max_method_definition > 0:
        ng.remove_too_many_definition_methods(method2claz2code, max_method_definition)

    method2claz2precomp = {}
    claz_method_tables = pm.ClazMethodTables(claz2methods, claz2deriving, ng.is_untracked_method_call)
    for method, c2c in method2claz2code.iteritems():
        for claz, ope_list in c2c.iteritems():
            precomp = pm.precompile_code(claz, ope_list, 
                    claz_method_tables=claz_method_tables,
                    remove_repetition=not allow_repetitive_ngram)
            method2claz2precomp.setdefault(method, {})[claz] = precomp
    del claz_method_tables
    del method2claz2code

    if ngram_size < 0:
        clone_data_args.delete("ngram-size")
    for L in clone_data_args.format():
        sys.stdout.write("%s\n" % L)
    sys.stdout.write('\n')  # separator
    
    try:
        for sec, data in clonefile_iter:
            if sec == cm.OPESEQ_LOCS:
                opeseq, locs = data
            elif sec == cm.OPESEQ_TRACES:
                opeseq, traces = data
                locs = [l[0] for l in traces]
            elif sec == cm.OPESEQ_SINGLE:
                opeseq, _ = data
                locs = None
            else:
                continue  # for sec

            if code_ngram_needed:
                ngrams = extract_poeseq_and_ngrams(opeseq, locs, method2claz2precomp, 
                        ngram_size, max_call_depth=max_call_depth, allow_repetitive_ngram=allow_repetitive_ngram,
                        no_branch_ngram=no_branch_ngram)
            else:
                ngrams = None

            if args.add_metric_clat:
                assert ngrams is not None
                clat = extract_clat(ngrams)
                sys.stdout.write(('metric-clat=%d\n' % len(clat)).encode('utf-8'))

            if args.add_metric_max_depth:
                if ngrams:
                    max_depth = extract_max_depth(ngrams)
                else:
                    max_depth = extract_max_depth_from_locs(locs)
                sys.stdout.write(('metric-max-depth=%d\n' % max_depth).encode('utf-8'))
            
            if args.add_metric_unique_method:
                if ngrams:
                    unique_method = extract_unique_method_count(ngrams)
                else:
                    unique_method = extract_unique_method_count_from_opeseq(opeseq)
                sys.stdout.write(('metric-unique-method=%d\n' % unique_method).encode('utf-8'))

            sys.stdout.write('ope:\n')
            for L in opeseq:
                sys.stdout.write(('  %s\n' % L).encode('utf-8'))

            if args.loc_to_trace:
                assert ngrams is not None
                for ngram in ngrams:
                    sys.stdout.write('trace:\n')
                    for _, loc, depth in ngram:
                        sys.stdout.write(('  %s >%d\n' % (loc, depth)).encode('utf-8'))
            else:
                sys.stdout.write('loc:\n')
                for loc in locs:
                    sys.stdout.write(('  %s\n' % loc).encode('utf-8'))
            sys.stdout.write('\n')
    except cm.CloneFileSyntaxError as e:
        sys.exit(unicode(e).encode('utf-8'))
    except ParseError as e:
        sys.exit(unicode(e).encode('utf-8'))

if __name__ == '__main__':
    main(sys.argv)

