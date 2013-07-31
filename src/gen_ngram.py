#!/usr/bin/env python
#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import collections
import os
import sys
import datetime

from _utilities import sort_uniq

import asm_manip as am
import ope_manip as om
import precomp_manip as pm

UNTRACKED_CLAZS = frozenset([
    "java/lang/StringBuilder", 
    "java/util/Iterator"
])

UNDIGGED_METHODS = frozenset([
    'getClass:()Ljava/lang/Class;',
    'equals:(Ljava/lang/Object;)Z',
    'hashCode:()I',
    'compareTo:(Ljava/lang/Object;)I',
    'toString:()Ljava/lang/String;',
    'get:(Ljava/lang/Object;)Ljava/lang/Object;',
    'put:(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;',
    'getProperty:(Ljava/lang/Object;)Ljava/lang/Object;',
])

def to_ngram_tuples_iter(found_ngrams):
    for head, tails in sorted(found_ngrams.iteritems(), key=lambda h_ts: h_ts[0]):
        ngram_tuples = []
        for tail in tails:
            ngram = (head,) + tail
            buf = []
            for c_m, frame in ngram:
                claz, method = frame.claz_method
                c, m = c_m
                s = m if c is None else "%s.%s" % c_m
                buf.append((s, "%s.%s,%d" % (claz, method, frame.index), frame.depth))
            ngram_tuple = tuple(buf)
            ngram_tuples.append(ngram_tuple)
        yield sort_uniq(ngram_tuples)
            # Drop intermediate paths data from each n-gram and merge the n-grams. 
            # Because printed n-grams do not have such intermediate path data, 
            # so two n-grams, which starts the same posision and the same depth but the distinct paths,
            # are not able to be distinguished in the output and look just duplication in the output.

def make_method2claz2code(sig2code):
    method2claz2code = {}
    for (claz, sig), code in sorted(sig2code.iteritems()):
        method2claz2code.setdefault(sig, {})[claz] = code
    return method2claz2code

def make_claz2methods(method2claz2code):
    claz2methods = {}
    for m, c2c in method2claz2code.iteritems():
        for c in c2c.iterkeys():
            claz2methods.setdefault(c, []).append(m)
    return claz2methods

class StackFrame(object):
    def __init__(self, claz_method, index, prev_frame):
        self.claz_method = claz_method
        self.index = index
        self.prev_frame = prev_frame
        self.depth = 0 if prev_frame is None else prev_frame.depth + 1
    
    def __eq__(self, other):
        return other is not None and \
            self.claz_method == other.claz_method and self.index == other.index and \
            self.depth == other.depth and self.prev_frame == other.prev_frame

    def __lt__(self, other):
        if other is None:
            return False
        if self.claz_method < other.claz_method:
            return True
        elif self.claz_method == other.claz_method:
            if self.index < other.index:
                return True
            elif self.index == other.index:
                if self.depth < other.depth:
                    return True
                elif self.depth == other.depth:
                    return self.prev_frame < other.prev_frame

    def __hash__(self):
        return hash(self.claz_method) + hash(self.index) + hash(self.depth)  # prev_frame is not used in hash computation

    def copy(self, index=None):
        return StackFrame(self.claz_method, index if index is not None else self.index, self.prev_frame)
    
    def __repr__(self):
        return "StackFrame(%s,%s,*,depth=%d)" % (repr(self.claz_method), repr(self.index), self.depth)  # prev_frame is not printed

class CodeNgramGenerator:
    def __init__(self, method2claz2precomp):
        self.method2claz2precomp = method2claz2precomp
        self.ngram_size = 6
        self.max_call_depth = -1
        self.allow_repetitive_ngram = False
        self.no_branch_ngram = False
        self.no_returning_execution_path = False
        self.use_undigg_method_list = False
        self.count_branch_in_surface_level = False
        self.clear_temp()
    
    def clear_temp(self):
        self._claz_method0 = None
        self._max_call_depth = None
        self._stack_already_printed_on_raise = False
    
    def _remove_repetition(self, cur_gram):
        if self.allow_repetitive_ngram:
            return 0
          
        for replen in range(1, min(len(cur_gram), self.ngram_size) // 2 + 1):
            for j in range(-1, -1 - replen, -1):
                c, r = cur_gram[j], cur_gram[j - replen]
                if c[0] != r[0]:
                    break  # for j
            else:
                del cur_gram[-replen:]
                return replen
          
        return 0

    def _setup_temp(self, claz, method):
        self._claz_method0 = claz, method
        self._max_call_depth = self.max_call_depth if self.max_call_depth >= 0 else \
                self.ngram_size * (-self.max_call_depth)
        self._stack_already_printed_on_raise = False
        self._found_grams = {}  # head item -> set if tuple of tail items
            # here, head is the first item of ngram tail is the other items
        
    def gen_ngrams(self, claz, method):
        self._setup_temp(claz, method)
        self._dig_method(self._max_call_depth , [], (claz, method), None, None)
        self.clear_temp()
        return self._found_grams

    def _dig_method(self, dig_count, cur_gram, claz_method, prev_frame, prev_footmarks_frame, 
            start_cell=None, is_return_dig=False):
        if not is_return_dig:
            p = self.method2claz2precomp[claz_method[1]][claz_method[0]]
            if start_cell is None:
                start_cell = p.start_cell
            cur_frame = StackFrame(claz_method, start_cell[0], prev_frame)
            cur_footmarks_frame = [], prev_footmarks_frame
        else:
            assert claz_method is None
            assert start_cell is None
            cur_frame = prev_frame
            claz_method = cur_frame.claz_method
            p = self.method2claz2precomp[claz_method[1]][claz_method[0]]
            start_cell = p.cells[cur_frame.index][1]
            cur_footmarks_frame = prev_footmarks_frame[0][:], prev_footmarks_frame[1]
        cur_block_entrance_cells = p.bent_cells
        depth = cur_frame.depth
        
        try:
            branches = []
            def dig_branch(dig_count, cur_gram, cur_cell, cur_footmarks_frame):
                footmarks = cur_footmarks_frame[0]
                while True:
                    index, next_cell, precomp_cmd, precomp_arg = cur_cell
                    if index in cur_block_entrance_cells:
                        if index in footmarks:
                            break  # while True
                        footmarks.append(index)

                        # in deeper levels than the surface, branchs are counted 
                        # in order to avoid interprting too complex control dependencies
                        if self.count_branch_in_surface_level or depth > 0:
                            if dig_count <= 0:
                                break  # while True
                            dig_count -= 1

                    if precomp_cmd == pm.INVOKE:
                        stk = cur_frame.copy(index)

                        c_m = c, m = precomp_arg
                        if cur_gram and dig_count > 0 and self._is_method_digg_target(c, m, cur_gram):
                            c2p = self.method2claz2precomp.get(m)
                            if c2p:
                                cs = sorted(c2p.iterkeys()) if c is None else \
                                        [c] if c in c2p else \
                                        []
                                for c2 in cs:
                                    c2_m = (c2, m)
                                    if not CodeNgramGenerator.is_recursion(c2_m, cur_frame):
                                        self._dig_method(dig_count - 1, cur_gram[-self.ngram_size:], c2_m, stk, cur_footmarks_frame)

                        cur_gram.append((c_m, stk))
                        if self._remove_repetition(cur_gram) == 0 and  len(cur_gram) >= self.ngram_size:
                            if self._is_escaping(cur_gram[-self.ngram_size][1]):
                                break  # while True
                            cand_gram = tuple(cur_gram[-self.ngram_size:])
                            if not self._store_if_new_ngram(cand_gram):
                                break  # while True
                    elif precomp_cmd == pm.RETURN:
                        if self.no_returning_execution_path:
                            break  # while True
                        if cur_frame.prev_frame is not None:
                            self._dig_method(dig_count, cur_gram, None, 
                                    cur_frame.prev_frame, cur_footmarks_frame[1], is_return_dig=True)
                        break  # while True
                    elif precomp_cmd == pm.GOTO:
                        if not self.no_branch_ngram:
                            next_cell = precomp_arg
                    elif precomp_cmd == pm.BRANCHS:
                        if not self.no_branch_ngram:
                            branches.extend((dig_count, cur_gram[-self.ngram_size:], dc, (footmarks[:], prev_footmarks_frame)) \
                                    for dc in precomp_arg)
                    elif precomp_cmd == pm.THROW:
                        break  # while True
                    else:
                        assert False
                    cur_cell = next_cell
            dig_branch(dig_count, cur_gram, start_cell, cur_footmarks_frame)
            while branches:
                b = branches.pop()
                dig_branch(*b)
        except:
            self._print_stack(cur_frame)
            raise

    @staticmethod
    def is_recursion(claz_method, frame):
        method = claz_method[1]
        while frame:
            if method == frame.claz_method[1]:
                return True
            frame = frame.prev_frame
        return False
    
    def _store_if_new_ngram(self, cand_gram):
        assert len(cand_gram) >= 1
        tails = self._found_grams.setdefault(cand_gram[0], set())
        tail = tuple(cand_gram[1:])
        if tail in tails:
            return False
        tails.add(tail)
        return True

    def _is_method_digg_target(self, c, method, cur_gram):
        assert method
        if self.use_undigg_method_list and method in UNDIGGED_METHODS:
            return False
        if c is None and method.endswith(":()V"):
            return False
        for i in xrange(0, min(len(cur_gram), self.ngram_size - 1)):
            if cur_gram[-i-1][0][1] == method:
                return False
        return True
    
    def _is_escaping(self, head_frame):
        return head_frame.depth != 0  # escaped from the original method?
        # a head item of a n-gram always comes from the original method.
        # if not (that is, a head item is comes from some called method by the original method),
        # such code fragment is not a part of the orignal method, but a part of the called method.
    
    def _print_stack(self, frame):
        if self._stack_already_printed_on_raise:
            return
        buf = []
        while frame:
            buf.append((frame.claz_method[0], frame.claz_method[1], frame.index))
            frame = frame.prev_frame
        sys.stderr.write("debug info> cur_call_stack = [%s]\n" % ", ".join("%s.%s:%d" % f for f in buf))
        self._stack_already_printed_on_raise = True

class CodeNgramGeneratorWStartIndices(CodeNgramGenerator):
    def clear_temp(self):
        CodeNgramGenerator.clear_temp(self)
        self._start_index = None
        
    def gen_ngrams(self, claz, method, start_indices):
        self._setup_temp(claz, method)
        for start_index in start_indices:
            self._start_index = start_index
            claz2precomp = self.method2claz2precomp[method]
            precomp_cells = claz2precomp[claz].cells
            head_cell = precomp_cells[start_index]
            self._dig_method(self._max_call_depth, [], (claz, method), None, None, head_cell)
        self.clear_temp()
        return self._found_grams

    def _is_escaping(self, head_frame):
        if self._start_index is not None:
            if head_frame.claz_method == self._claz_method0 and head_frame.index != self._start_index:
                return True
        return CodeNgramGenerator._is_escaping(self, head_frame)

def gen_code_ngrams(claz, method, method2claz2precomp, ngram_size, start_indices=None,
        max_call_depth=-1, allow_repetitive_ngram=False, no_branch_ngram=False,
        no_returning_execution_path=False, use_undigg_method_list=False,
        count_branch_in_surface_level=False):
    if start_indices:
        cng = CodeNgramGeneratorWStartIndices(method2claz2precomp)
    else:
        cng = CodeNgramGenerator(method2claz2precomp)
    cng.ngram_size = ngram_size
    cng.max_call_depth = max_call_depth
    cng.allow_repetitive_ngram = allow_repetitive_ngram
    cng.no_branch_ngram = no_branch_ngram
    cng.no_returning_execution_path = no_returning_execution_path
    cng.use_undigg_method_list = use_undigg_method_list
    cng.count_branch_in_surface_level = count_branch_in_surface_level
    if start_indices:
        return cng.gen_ngrams(claz, method, start_indices)
    else:
        return cng.gen_ngrams(claz, method)

def identify_claz(method2claz2code, class_patterns):    
    exclude_clazs = frozenset([e for e in class_patterns if not e.endswith('/*')])
    exclude_packages = frozenset([e[:-1] for e in class_patterns if e.endswith('/*')])
    clazs = set()
    for method, claz2code in method2claz2code.iteritems():
        clazs.update(claz2code.iterkeys())
    clazs_tobe_excluded = set()
    for claz in sorted(clazs):
        if claz in exclude_clazs:
            clazs_tobe_excluded.add(claz)
        else:
            p = claz.rfind('/')
            if p >= 0:
                package = claz[:p + 1]  # include trailing '/'
                if package in exclude_packages:
                    clazs_tobe_excluded.add(claz)
    return clazs_tobe_excluded

def identify_target_claz_method(method2claz2code,entry_class_patterns):
    if entry_class_patterns:
        claz_set = frozenset(identify_claz(method2claz2code, entry_class_patterns))
        claz_method_list = sorted((claz, method) for method, claz2pre in method2claz2code.iteritems() \
                for claz in claz2pre.iterkeys() if claz in claz_set)
    else:
        claz_method_list = sorted((claz, method) for method, claz2pre in method2claz2code.iteritems() \
                for claz in claz2pre.iterkeys())
    claz_method_count = collections.Counter()
    for claz, method in claz_method_list:
        claz_method_count[claz] += 1
    return claz_method_list, claz_method_count

def exclude_clazs(method2claz2code, excludeded_class_patterns):
    removed_clazs = identify_claz(method2claz2code, excludeded_class_patterns)
    for method, claz2code in method2claz2code.items():
        for c in removed_clazs.intersection(claz2code.iterkeys()):
            del claz2code[c]
        if len(claz2code) == 0:
            del method2claz2code[method]
    return removed_clazs

def exclude_ctors(method2claz2code):
    ctors = [m for m in method2claz2code.iterkeys() \
            if m.startswith('"<init>"') or m.startswith("access$")]
    for m in ctors:
        del method2claz2code[m]
    return ctors

def remove_too_many_definition_methods(method2claz2code, max_method_definition):
    assert max_method_definition > 0
    too_many_definition_methods = [method \
            for method, claz2code in method2claz2code.iteritems() \
            if len(claz2code) > max_method_definition]
    for m in too_many_definition_methods:
        del method2claz2code[m]
    return too_many_definition_methods

def do_filtering_clazs(write, method2claz2code, excluded_class_patterns):
    if excluded_class_patterns:
        removed_clazs = exclude_clazs(method2claz2code, excluded_class_patterns)
        write("removed classes by --exclude option(s): %d\n" % \
                len(removed_clazs))

def do_filtering_methods(write, method2claz2code, include_ctors, max_method_definition):
    if not include_ctors:
        ctors = exclude_ctors(method2claz2code)
        write("removed ctors: %d\n" % len(ctors))

    if max_method_definition > 0:
        too_many_definition_methods = remove_too_many_definition_methods(
                method2claz2code, max_method_definition)
        write("removed methods by option --max-definition=%d: %d\n" % \
                (max_method_definition, len(too_many_definition_methods)))

def gen_argpsr():
    from argparse import ArgumentParser
    from _version_data import VERSION
    psr = ArgumentParser(description='Generate n-grams of method calls')
    psr.add_argument('-a', '--asm-directory', action='store', required=True)

    psr.add_argument('-n', '--ngram-size', action='store', type=int, default=6)
    psr.add_argument('-v', '--verbose', action='store_true')
    psr.add_argument('--max-call-depth', action='store', type=int, default=-2,
            help='max depth in expanding method calls. negative number means scale factor to n-gram size. (default is -2, that is. 2 * n-gram size.)')
    psr.add_argument('--max-method-definition', action='store', type=int, default=-1,
            help='max method defintions for a signiture. =-1 means unlimited')
    psr.add_argument('--allow-repetitive-ngram', action='store_true')
    psr.add_argument('--no-branch-ngram', action='store_true')

    psr.add_argument('-e', '--exclude', action='append',
            help="specify class in fully-qualified name, e.g. org/myapp/MyClass$AInnerClass. a wildcard '*' can be used as class name, e.g. org/myapp/*")
    psr.add_argument('--entry', action='append',
            help="class to be a entry point of abstract interpretation. specify class in fully-qualified name. wildcard can be used.")

    psr.add_argument('--include-ctors', action='store_true',
            help='include "<init>" and access$... methods as targets')

    grp = psr.add_mutually_exclusive_group(required=False)
    grp.add_argument('--mode-diagnostic', action='store_true',
            help='show bytecode info and the filtering results')
    grp.add_argument('--mode-method-signature', action='store_true',
            help='show method signatures')
    grp.add_argument('--mode-method-body', action='store_true',
            help='show method bodies (byte code)')
    
    psr.add_argument('--debug-wo-leaf-class-dispatch-optimization', action='store_true')
    psr.add_argument('--debug-no-returning-execution-path', action='store_true')
    psr.add_argument('--debug-count-branch-in-surface-level', action='store_true')
    psr.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
    return psr

def is_untracked_method_call(c, m):
    return c in UNTRACKED_CLAZS or m.find("access$") >= 0

def main(argv):
    psr = gen_argpsr()
    args = psr.parse_args(argv[1:])

    max_method_definition = max(-1, args.max_method_definition)
    excluded_class_patterns = frozenset(args.exclude if args.exclude else [])
    entry_class_patterns = frozenset(args.entry if args.entry else [])

    verbose = args.verbose
    debug_wo_leaf_class_dispatch_optimization = args.debug_wo_leaf_class_dispatch_optimization
    debug_no_returning_execution_path = args.debug_no_returning_execution_path

    if verbose:
        def verbose_write(mes): sys.stderr.write("> %s" % mes)
    else:
        def verbose_write(mes): pass

    if not os.path.isdir(args.asm_directory):
        sys.exit("error: fail to access asm_directory: %s" % args.asm_directory)

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

    if args.mode_method_signature:
        for claz_sig in sorted(sig2code.iterkeys()):
            sys.stdout.write('%s.%s\n' % claz_sig.encode('utf-8'))
    elif args.mode_method_body:
        for claz_sig, method_body in sorted(sig2code.iteritems()):
            ol = om.body_text_to_ope_list(method_body, claz_sig)
            try:
                om.verify_branch_ope(ol)
            except om.InvalidOpe as e:
                raise om.InvalidOpe("%s.%s: %s" % (claz_sig[0], claz_sig[1], str(e)))
            sys.stdout.write('%s.%s\n' % claz_sig)
            for L in om.format_ope_list(ol): #, fields=om.FORMAT_FIELD.OPE):
                sys.stdout.write('%s\n' % L)
    else:
        sig2oplist = {}
        for claz_sig, method_body in sorted(sig2code.iteritems()):
            ol = om.body_text_to_ope_list(method_body, claz_sig)
            sig2oplist[claz_sig] = ol
        del sig2code

        method2claz2code = make_method2claz2code(sig2oplist)
        del sig2oplist
        claz2methods = make_claz2methods(method2claz2code)

        do_filtering_clazs(verbose_write, method2claz2code, excluded_class_patterns)
        do_filtering_methods(verbose_write, method2claz2code, args.include_ctors, max_method_definition)
        claz_method_list, claz_method_count = identify_target_claz_method(method2claz2code,entry_class_patterns)
            
        if args.mode_diagnostic:
            sys.stdout.write("classes: %d\n" % len(claz_method_count))
            sys.stdout.write("method bodies: %d\n" % sum(claz_method_count.itervalues()))
            m2ccount = collections.Counter()
            for m, c2c in method2claz2code.iteritems():
                m2ccount[m] += len(c2c)
            mccounts = sorted(((m, c) for m, c in m2ccount.iteritems()), key=lambda m_c: m_c[1], reverse=True)
            sys.stdout.write("method having many definitions:\n")
            for m, c in mccounts:
                if c < 50: break  # for m, c
                sys.stdout.write("  %4d %s\n" % (c, m))
            return

        if debug_wo_leaf_class_dispatch_optimization:
            claz2methods = claz2deriving = None
        method2claz2precomp = {}
        claz_method_tables = pm.ClazMethodTables(claz2methods, claz2deriving, is_untracked_method_call)
        for method, c2c in method2claz2code.iteritems():
            for claz, ope_list in c2c.iteritems():
#                 if claz == "org/gjt/sp/jedit/bufferio/BufferSaveRequest" and method == "run:()V":
#                     assert True
                precomp = pm.precompile_code(claz, ope_list, 
                        claz_method_tables=claz_method_tables, 
                        remove_repetition=not args.allow_repetitive_ngram)
                method2claz2precomp.setdefault(method, {})[claz] = precomp
        del claz_method_tables
        del method2claz2code

        sys.stdout.write("# --ngram-size=%d\n" % args.ngram_size)
        sys.stdout.write("# --max-call-depth=%d\n" % args.max_call_depth)
        sys.stdout.write("# --max-method-definition=%d\n" % max_method_definition)
        if args.allow_repetitive_ngram:
            sys.stdout.write("# --allow-repetitive-ngram\n")
        if args.no_branch_ngram:
            sys.stdout.write("# --no-branch-ngram\n")
        if args.include_ctors:
            sys.stdout.write("# --include-ctors\n")
        for e in excluded_class_patterns:
            sys.stdout.write("# --exclude=%s\n" % e)
        for e in entry_class_patterns:
            sys.stdout.write("# --entry=%s\n" % e)
        sys.stdout.write('\n')
        
        prev_claz = None
        for i, (claz, method) in enumerate(claz_method_list):
            code = method2claz2precomp[method][claz]
            if verbose and claz != prev_claz:
                t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                s = '%s (%d-%d of %d) %s\n' % (t, i+1, i+1 + claz_method_count[claz] - 1, len(claz_method_list), claz)
                verbose_write(s.encode('utf-8'))
            prev_claz = claz
            found_ngrams = gen_code_ngrams(claz, method, method2claz2precomp, args.ngram_size, 
                    max_call_depth=args.max_call_depth, allow_repetitive_ngram=args.allow_repetitive_ngram,
                    no_branch_ngram=args.no_branch_ngram, no_returning_execution_path=debug_no_returning_execution_path,
                    use_undigg_method_list=debug_wo_leaf_class_dispatch_optimization,
                    count_branch_in_surface_level=args.debug_count_branch_in_surface_level)

            for ngrams in to_ngram_tuples_iter(found_ngrams):  
                for ngram in ngrams:
                    sys.stdout.write(''.join("%s\t%s\t%d\n" % op_loc_dep for op_loc_dep in ngram))
                    sys.stdout.write('\n')

if __name__ == '__main__':
    main(sys.argv)

