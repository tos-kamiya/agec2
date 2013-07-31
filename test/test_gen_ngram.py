#coding: utf-8

import unittest

import sys

import os.path as p
sys.path.insert(0, p.join(p.dirname(p.abspath(__file__)), '..', 'src'))

import gen_ngram as gn
import precomp_manip as pm

method_sig_and_precomp_cell_arrays = [
    ('"<init>":()V', [-1, 1, None, None],
        [
            [1,4,pm.INVOKE,('java/lang/Object', '"<init>":()V')],
            [4,5,pm.RETURN,None],
            [5,None,pm.RETURN,None]
        ]
    ),
    ('setCalendarDate:(Ljava/util/Calendar;Ljava/lang/String;Ljava/lang/String;)V',  [-1, 2, None, None],
        [
            [2,10,pm.INVOKE,(None, 'split:(Ljava/lang/String;)[Ljava/lang/String;')],
            [10,16,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [16,24,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [24,27,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [27,30,pm.INVOKE,(None, 'set:(III)V')],
            [30,31,pm.RETURN,None],
            [31,None,pm.RETURN,None]
        ]
    ),
    ('main:([Ljava/lang/String;)V', [-1, 0, None, None],
        [
            [0,7,pm.INVOKE,('java/util/Calendar', 'getInstance:()Ljava/util/Calendar;')],
            [7,15,pm.BRANCHS,[100]],
            [15,18,pm.INVOKE,(None, 'indexOf:(Ljava/lang/String;)I')],
            [18,27,pm.BRANCHS,[33]],
            [27,30,pm.INVOKE,(None, 'setCalendarDate:(Ljava/util/Calendar;Ljava/lang/String;Ljava/lang/String;)V')],
            [30,38,pm.GOTO,100],
            [38,41,pm.INVOKE,(None, 'indexOf:(Ljava/lang/String;)I')],
            [41,50,pm.BRANCHS,[56]],
            [50,53,pm.INVOKE,(None, 'setCalendarDate:(Ljava/util/Calendar;Ljava/lang/String;Ljava/lang/String;)V')],
            [53,61,pm.GOTO,100],
            [61,64,pm.INVOKE,(None, 'indexOf:(Ljava/lang/String;)I')],
            [64,72,pm.BRANCHS,[100]],
            [72,80,pm.INVOKE,(None, 'split:(Ljava/lang/String;)[Ljava/lang/String;')],
            [80,86,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [86,94,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [94,97,pm.INVOKE,('java/lang/Integer', 'parseInt:(Ljava/lang/String;)I')],
            [97,103,pm.INVOKE,(None, 'set:(III)V')],
            [103,126,pm.INVOKE,(None, 'get:(I)I')],
            [126,130,pm.INVOKE,(None, 'printf:(Ljava/lang/String;[Ljava/lang/Object;)Ljava/io/PrintStream;')],
            [130,131,pm.RETURN,None],
            [131,None,pm.RETURN,None]
        ]
    ),
    ('"static{}":()V', [-1, 44, None, None],
        [
            [44,45,pm.RETURN,None],
            [45,None,pm.RETURN,None]
        ]
    ),
]

class TestGenNgram(unittest.TestCase):
    def testGenNgram(self):
        asmfile = "ShowWeekday.Rasm"
        method_sigs = [method_sig for method_sig, _, _ in method_sig_and_precomp_cell_arrays]
        method2claz2precomp = {}
        for method_sig, entrance_cell, cell_array_data in method_sig_and_precomp_cell_arrays:
            cells = [None] * (cell_array_data[-1][0] + 1)
            for c in cell_array_data:
                cells[c[0]] = c
            for i, c in enumerate(cells):
                if c is None:
                    cells[i] = [i, None, None, None]
            pm.optmize_gotos_in_cell_array(cells, entrance_cell)
            pm.merge_branches_in_cell_array(cells, entrance_cell)
            block_entrance_cells = pm.get_block_entrance_cells(cells, entrance_cell)
            start_cell, valid_cells = pm.precompile_cell_array_to_cell_linked_list(cells, entrance_cell)
            method2claz2precomp.setdefault(method_sig, {})['ShowWeekday'] = pm.PrecompData(valid_cells, start_cell, block_entrance_cells)
            for o_cell, v_cell in zip(cells, valid_cells):
                both_none = o_cell is None and v_cell is None
                both_valid = o_cell is not None and v_cell is not None
                self.assertTrue(both_none or both_valid)

        for method_sig, c2p in sorted(method2claz2precomp.iteritems()):
            for claz in sorted(c2p.iterkeys()):
                code_ngrams = gn.gen_code_ngrams(claz, method_sig, method2claz2precomp, 6, 
                        max_call_depth=999, allow_repetitive_ngram=False)
                if method_sig == 'main:([Ljava/lang/String;)V':
                    self.assertTrue(len(code_ngrams) > 0)
                else:
                    self.assertTrue(len(code_ngrams) == 0)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()