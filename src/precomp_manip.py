#coding: utf-8

__author__ = 'Toshihiro Kamiya <kamiya@mbj.nifty.com>'
__status__ = 'experimental'

import re
import sys
import collections

from _utilities import sort_uniq

_BRANCH_OPES = frozenset([
    "ifeq", "ifnull", "iflt", "ifle", "ifne", "ifnonnull", "ifgt", "ifge",
    "if_icmpeq", "if_icmpne", "if_icmplt", "if_icmpgt", "if_icmple", "if_icmpg",
    "if_acmpeq", "if_acmpne",
    ])
_RETURN_OPS = ("return", "ireturn", "lreturn", "dreturn", "areturn")
_THROW_OPS = ("athrow",)
_INVOKE_STATIC_OPS = ("invokespecial", "invokestatic")
_INVOKE_DYNAMIC_OPS = ("invokevirtual", "invokeinterface")
_GOTO_OPS = ("goto", "goto_w")
_SWITCH_OPS = ("lookupswitch", "tableswitch")

VALID_OPS = set()
VALID_OPS.update(_BRANCH_OPES)
VALID_OPS.update(_RETURN_OPS)
VALID_OPS.update(_THROW_OPS)
VALID_OPS.update(_INVOKE_STATIC_OPS)
VALID_OPS.update(_INVOKE_DYNAMIC_OPS)
VALID_OPS.update(_GOTO_OPS)
VALID_OPS.update(_SWITCH_OPS)
VALID_OPS = frozenset(VALID_OPS)

_PUSH_OPS = frozenset([
    "bipush", "sipush", 
    "ldc", "ldc_w", "ldc2_w", 
    "iconst_m1", "iconst_0", "iconst_1", "iconst_2", "iconst_2", "iconst_3", "iconst_4", "iconst_5",
    "lconst_0", "lconst_1", "fconst_0", "fconst_1", "dconst_0", "dconst_1", "aconst_null",
    "iload", "lload", "fload", "dload", "aload",
    "iload_0", "iload_1", "iload_2", "iload_3",
    "lload_0", "lload_1", "lload_2", "lload_3",
    "fload_0", "fload_1", "fload_2", "fload_3",
    "dload_0", "dload_1", "dload_2", "dload_3",
    "aload_0", "aload_1", "aload_2", "aload_3",
])

def sig_to_claz_method(sig):
    p = sig.find('.')
    assert p >= 0
    claz = sig[:p]
    method = sig[p+1:]
    return claz, method

_pat_sig = re.compile(r'^//\s+(Interface)?Method\s+(?P<name>.+)$')

def get_claz_method_from_comment(comment, context_claz=None):
    m = _pat_sig.match(comment)
    if m:
        siglike = m.group('name')
        if siglike.find('.') < 0:
            if siglike.startswith('"<init>"'):
                return (context_claz, siglike)
            else:
                return (None, siglike)
        else:
            return sig_to_claz_method(siglike)
    return (None, None)

THROW, RETURN, BRANCHS, GOTO, INVOKE = range(1, 5 + 1)
#THROW, RETURN, BRANCHS, GOTO, INVOKE = "THROW", "RETURN", "BRANCHS", "GOTO", "INVOKE"

def claz2indirect_deriving(claz2deriving):
    claz2indd = {}  # claz -> set of claz
    def add(c, cindd, d):
        if d == c:
            return
        cindd.add(d)
        dds = claz2deriving.get(d)
        if dds:
            for dd in dds:
                add(c, cindd, dd)
    for c, ds in claz2deriving.iteritems():
        for d in ds:
            add(c, claz2indd.setdefault(c, set()), d)
    return claz2indd

def claz2methods_defined_in_the_class_but_not_in_its_derivings(claz2methods, claz2indd):
    claz2mdoins = {}  # claz -> set of methods (which are only defined in claz)
    for c, ms in claz2methods.iteritems():
        mdoin = set(ms)
        ds = claz2indd.get(c)
        if ds:
            for d in ds:
                if len(mdoin) == 0:
                    break  # for d
                dms = claz2methods.get(d)
                if dms:
                    mdoin.difference_update(dms)
        claz2mdoins[c] = frozenset(mdoin)
    return claz2mdoins

class ClazMethodTables(object):
    def __init__(self, claz2methods, claz2deriving, is_untracked_method_call):
        self.claz2methods = claz2methods
        self.claz2deriving = claz2deriving
        claz2indd = claz2indirect_deriving(claz2deriving)
        self.claz2ms_doiid = claz2methods_defined_in_the_class_but_not_in_its_derivings(claz2methods, claz2indd)
        self.is_untracked_method_call = is_untracked_method_call

def count_method_args(m):
    p = m.index(":(")
    q = m.index(")", p+2)
    argstr = m[p+2:q]
    argstr = argstr.replace('[', '')
    count = 0
    while argstr:
        a0 = argstr[0]
        if a0 in "VZBCSIJFD":
            count += 1
            argstr = argstr[1:]
        elif a0 == "L":
            count += 1
            p = argstr.index(";")
            argstr = argstr[p+1:]
        else:
            assert False
    return count

def is_receiver_this(ope_list, index, m):
    args = count_method_args(m)
    p = args
    i = index - 1
    while p:
        if i < 0:
            return False
        oi = ope_list[i]
        if not oi:
            return False
        if not oi[0] in _PUSH_OPS:
            return False
        p -= 1
        i -= 1
    if i >= 0 and ope_list[i] == ('aload_0', (), None):
        return True

def precompile_ope_list_to_cell_array(claz, ope_list, claz_method_tables=None):
    do_dynamic_dispatch_optimization = claz_method_tables is not None
    claz2methods = claz_method_tables.claz2methods
    claz2ms_doiid = claz_method_tables.claz2ms_doiid
    has_deriving_clazs = claz_method_tables.claz2deriving.get
    is_untracked_method_call = claz_method_tables.is_untracked_method_call
        
    ope_list_len = len(ope_list)
    cells = [[index, None, None, None] for index in range(ope_list_len + 1)]
    entrance_cell = [-1, None, None, None]
    prev_cell = entrance_cell
    for index in range(ope_list_len):
        cells_i = cells[index]
        ope = ope_list[index]
        if not(ope is not None and ope[0] in VALID_OPS):
            continue

        opecode, operands, comment = ope
        if opecode in _RETURN_OPS:
            cells_i[2:4] = [RETURN, None]
            prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _THROW_OPS:
            cells_i[2:4] = [THROW, None]
            prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _GOTO_OPS:
            assert len(operands) == 1
            dest_index = int(operands[0])
            if dest_index != index + 1:
                cells_i[2:4] = [GOTO, dest_index]
                prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _BRANCH_OPES:
            assert len(operands) == 1
            dest_index = int(operands[0])
            if dest_index != index + 1:
                cells_i[2:4] = [BRANCHS, [dest_index]]
                prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _SWITCH_OPS:
            dest_indices = sorted(set([int(d) for v, d in operands]))
            dest_indices = [d for d in dest_indices if d != index + 1]
            if dest_indices:
                cells_i[2:4] = [BRANCHS, dest_indices]
                prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _INVOKE_DYNAMIC_OPS:
            c, m = get_claz_method_from_comment(comment, context_claz=claz)
            receiver_this = is_receiver_this(ope_list, index, m)
            if do_dynamic_dispatch_optimization:
                if c not in claz2methods:
                    tc = c  # c is PERHAPS a library class
                elif receiver_this and m in claz2ms_doiid.get(c, ()):
                    tc = c  # receiver is this object and deriving classes don't have defintion of method m
                elif not has_deriving_clazs(c) and m in claz2methods[c]:
                    tc = c  # receiver is PERHAPS this object
                else:
                    tc = None  # unknown receiver
            else:
                tc = None
            if do_dynamic_dispatch_optimization and is_untracked_method_call(tc, m):
                pass
            else:
                cells_i[2:4] = [INVOKE, (tc, m)]
                prev_cell[1] = index; prev_cell = cells_i
        elif opecode in _INVOKE_STATIC_OPS:
            c, m = get_claz_method_from_comment(comment, context_claz=claz)
            cells_i[2:4] = [INVOKE, (c, m)]
            prev_cell[1] = index; prev_cell = cells_i

    index = ope_list_len
    cells_i = cells[index]
    cells_i[2:4] = [RETURN, None]
    prev_cell[1] = index; prev_cell = cells_i

    return cells, entrance_cell

def overwrite_goto_and_branch_to_cell(cells, entrance_cell, old_index, new_index):
    if entrance_cell[1] == old_index:
        entrance_cell[1] = new_index
        
    for cell in cells:
        if cell[1] == old_index:
            if cell[0] != old_index:
                cell[1] = new_index
        if cell[2] == GOTO:
            if cell[3] == old_index:
                cell[3] = new_index
        elif cell[2] == BRANCHS:
            if old_index in cell[3]:
                cell[3] = sort_uniq(map(lambda i: i if i != old_index else new_index, cell[3]))

def check_destination_cell_valid(cells, entrance_cell):
    footmarks = [False] * len(cells)
    branches = []
    index = entrance_cell[1]
    while True:
        while footmarks[index]:
            if not branches:
                return
            index = branches.pop()
        footmarks[index] = True
        cur_cell = cells[index]
        assert cur_cell[0] == index
        _, next_index, precomp_cmd, precomp_arg = cur_cell
        if precomp_cmd is None:
            assert False
        assert precomp_cmd is not None
        if precomp_cmd in (THROW, RETURN):
            if not branches:
                return
            index = branches.pop()
        elif precomp_cmd == GOTO:
            index = precomp_arg
        elif precomp_cmd == BRANCHS:
            branches.extend(precomp_arg)
            index = next_index
        elif precomp_cmd == INVOKE:
            index = next_index

# def replace_loopback_goto_with_throw(cells, entrance_cell):
#     footmarks = [False] * len(cells)
#     branches = []
#     index = entrance_cell[1]
#     while True:
#         while footmarks[index]:
#             if not branches:
#                 return
#             index, footmarks = branches.pop()
#         footmarks[index] = True
#         cur_cell = cells[index]
#         assert cur_cell[0] == index
#         _, next_index, precomp_cmd, precomp_arg = cur_cell
#         if precomp_cmd is None:
#             assert False
#         assert precomp_cmd is not None
#         if precomp_cmd in (THROW, RETURN):
#             if not branches:
#                 return
#             index, footmarks = branches.pop()
#         elif precomp_cmd == GOTO:
#             di = precomp_arg
#             if di == index or footmarks[di]:
#                 cur_cell[2:] = [THROW, None]
#             index = di
#         elif precomp_cmd == BRANCHS:
#             dest_indices = [di for di in precomp_arg if not (di == index or footmarks[di])]
#             if not dest_indices:
#                 cur_cell[2:] = [THROW, None]
#             else:
#                 cur_cell[3] = dest_indices
#             branches.extend((di, footmarks[:]) for di in dest_indices)
#             index = next_index
#         elif precomp_cmd == INVOKE:
#             index = next_index

def get_block_entrance_cells(cells, entrance_cell):
    cell_to_incoming_edges = collections.Counter()

    def do_it():
        footmarks = [False] * len(cells)
        branches = []
        index = entrance_cell[1]
        cell_to_incoming_edges[index] += 1
        while True:
            while footmarks[index]:
                if not branches:
                    return
                index = branches.pop()
            footmarks[index] = True
            cur_cell = cells[index]
            assert cur_cell[0] == index
            _, next_index, precomp_cmd, precomp_arg = cur_cell
            if precomp_cmd is None:
                assert False
            assert precomp_cmd is not None
            if precomp_cmd in (THROW, RETURN):
                if not branches:
                    return
                index = branches.pop()
            elif precomp_cmd == GOTO:
                index = precomp_arg
                cell_to_incoming_edges[index] += 1
            elif precomp_cmd == BRANCHS:
                dest_indices = precomp_arg
                for di in dest_indices:
                    cell_to_incoming_edges[di] += 1
                branches.extend(dest_indices)
                index = next_index
                cell_to_incoming_edges[index] += 1
            elif precomp_cmd == INVOKE:
                index = next_index
                cell_to_incoming_edges[index] += 1
            else:
                assert False
    try:
        do_it()
    finally:
        return sorted([index for index, c in cell_to_incoming_edges.iteritems() if c >= 2])

def optmize_gotos_in_cell_array(cells, entrance_cell):
    def next_valid_cell_index(index):
        for i in range(index, len(cells)):
            if cells[i][2] is not None:
                return i
        assert False
    
    def get_final_dest_index(dest_index):
        assert dest_index is not None
        dest_indices = set()
        while True:
            dest_cell = cells[dest_index]
            if dest_cell[2] is None:
                dest_index = next_valid_cell_index(dest_index)
                dest_cell = cells[dest_index]
            dest_indices.add(dest_index)
            assert dest_cell[2] is not None
            if dest_cell[2] == GOTO:
                dest_index = dest_cell[3]
                if dest_index is None:
                    break  # while True
                dest_index = next_valid_cell_index(dest_index)
                if dest_index in dest_indices:
                    dest_index = sorted(dest_indices)[-1]
                    break  # while True
                dest_indices.add(dest_index)
            else:
                break  # while True
        return dest_index

    collapsed_branchs_cell_exists = True
    while collapsed_branchs_cell_exists:
        collapsed_branchs_cell_exists = False
        for cell in cells:
            if cell[1] is not None:
                cell[1] = get_final_dest_index(cell[1])
            if cell[2] == GOTO:
                cell[3] = get_final_dest_index(cell[3])
            elif cell[2] == BRANCHS:
                dis = [get_final_dest_index(di) for di in cell[3]]
                dis = [di for di in dis if di != cell[0] + 1]
                cell[3] = sort_uniq(dis)
                if not cell[3] or cell[3] == [cell[1]]:
                    cell[:] = [cell[0], cell[1], GOTO, cell[1]]
                    collapsed_branchs_cell_exists = True

    entrance_cell[1] = get_final_dest_index(entrance_cell[1])

def remove_repetitions_in_cell_array(cells, entrance_cell):
    for cell in cells:
        if cell[2] != INVOKE:
            continue
        next_index = cell[1]
        done_cell_indices = set([cell[0]])
        while next_index is not None and next_index not in done_cell_indices:
            done_cell_indices.add(next_index)
            next_cell = cells[next_index]
            if next_cell[2] != INVOKE:
                break  # while
            if next_cell[3] == cell[3]:
                overwrite_goto_and_branch_to_cell(cells, entrance_cell, next_index, next_cell[1])
            next_index = next_cell[1]

def merge_branches_in_cell_array(cells, entrance_cell):
    for cell in cells:
        if cell[2] != BRANCHS:
            continue
        cell[3] = sort_uniq(cell[3])
        next_index = cell[1]
        done_cell_indices = set([cell[0]])
        while next_index is not None and next_index not in done_cell_indices:
            done_cell_indices.add(next_index)
            next_cell = cells[next_index]
            if next_cell[2] != BRANCHS:
                break  # while
            cell[3] = sort_uniq([index for index in cell[3] + next_cell[3] if index != next_index])
            overwrite_goto_and_branch_to_cell(cells, entrance_cell, next_index, next_cell[1])
            next_index = next_cell[1]

def repr_precompiled_cell_array(cells):
    buf = []
    cmd2str = { 
        THROW: 'precomp_manip.THROW',
        RETURN: 'precomp_manip.RETURN',
        BRANCHS: 'precomp_manip.BRANCHS',
        GOTO: 'precomp_manip.GOTO',
        INVOKE: 'precomp_manip.INVOKE'
    }
    for i, cells_i in enumerate(cells):
        index, next_index, cmd, args = cells_i
        assert index == i
        if (next_index, cmd, args) != (None, None, None):
            buf.append("[%s,%s,%s,%s]" % (index, next_index, cmd2str[cmd], repr(args)))
    return "[\n  %s\n]" % ",\n  ".join(buf)

class PrecompData(object):
    def __init__(self, cells, start_cell, bent_cells):
        self.start_cell = start_cell
        self.cells = cells
        self.bent_cells = bent_cells

def precompile_cell_array_to_cell_linked_list(cells, entrance_cell):
    ope_list_len = len(cells) - 1
    cell_valid_flags = [False] * len(cells)

    def locate_dest_cell(dest_index, cells):
        for j in range(dest_index, ope_list_len + 1):
            if cells[j][2] is not None:
                return j
        assert False

    for index in range(ope_list_len + 1):
        cells_i = cells[index]
        cell_valid_flags[index] = True
        assert cells_i[0] == index
        next_i = cells_i[1]
        if next_i is not None:
            cells_i[1] = cells[next_i]
        cmd = cells_i[2]
        if cmd == BRANCHS:
            dest_cells = [cells[locate_dest_cell(dest_index, cells)] for dest_index in cells_i[3]]
            cells_i[3] = dest_cells
        elif cmd == GOTO:
            cells_i[3] = cells[locate_dest_cell(cells_i[3], cells)]

    valid_cells = [(cells[i] if f else None) for i, f in enumerate(cell_valid_flags)]
    
    if entrance_cell[1] is None:
        return (cells[-1], valid_cells)
    else:
        return (cells[entrance_cell[1]], valid_cells)

def precompile_code(claz, ope_list,  claz_method_tables=None, remove_repetition=True):
    cells, entrance_cell = precompile_ope_list_to_cell_array(claz, ope_list, claz_method_tables)
    optmize_gotos_in_cell_array(cells, entrance_cell)
    check_destination_cell_valid(cells, entrance_cell)
    merge_branches_in_cell_array(cells, entrance_cell)
    if remove_repetition:
        remove_repetitions_in_cell_array(cells, entrance_cell)
    block_entrance_cells = get_block_entrance_cells(cells, entrance_cell)
    start_cell, valid_cells = precompile_cell_array_to_cell_linked_list(cells, entrance_cell)
    return PrecompData(valid_cells, start_cell, frozenset(block_entrance_cells))

def pretty_precompiled(precomp):
    assert precomp is not None
    buf = []
    cur_cell = precomp
    while cur_cell is not None:
        index, next_cell, cmd, arg = cur_cell
        if cmd == THROW:
            buf.append("%d: THROW" % index)
        elif cmd == RETURN:
            buf.append("%d: RETURN" % index)
        elif cmd == BRANCHS:
            buf.append("%d: BRANCHS %s" % (index, " ".join("-> %d" % dest_cell[0] for dest_cell in arg)))
        elif cmd == GOTO:
            buf.append("%d: GOTO %s" % (index, arg[0]))
        elif cmd == INVOKE:
            buf.append("%d: INVOKE %s. %s" % (index, arg[0], arg[1]))
        else:
            assert False
        cur_cell = next_cell
    return buf

def check_precompiled(precomp):
    assert precomp is not None
    def check(cur_cell):
        while cur_cell is not None:
            index, next_cell, cmd, arg = cur_cell
            if index is None:
                return (None, "index is None")
            if cmd is None:
                return (index, "cmd is None")
            if cmd == THROW:
                return None
            elif cmd == RETURN:
                return None
            elif cmd == BRANCHS:
                for dest_cell in arg:
                    dest_index = dest_cell[0]
                    if dest_index is None:
                        return (index, "dest cell's index is None")
                    if dest_index <= index:
                        return (index, "dest cell's index <= index")
                    r = check(dest_cell)
                    if r:
                        return r
            elif cmd == GOTO:
                dest_cell = arg
                dest_index = dest_cell[0]
                if dest_index is None:
                    return (index, "dest cell's index is None")
                if dest_index <= index:
                    return (index, "dest cell's index <= index")
                r = check(dest_cell)
                if r:
                    return r
            elif cmd == INVOKE:
                pass
            else:
                assert False
            cur_cell = next_cell
    check(precomp)




