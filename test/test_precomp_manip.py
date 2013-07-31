import unittest

import sys

import os.path as p
sys.path.insert(0, p.join(p.dirname(p.abspath(__file__)), '..', 'src'))

import precomp_manip as pm

class PrecompManipTest(unittest.TestCase):
    def testClaz2IndirectDeriving(self):
        claz2deriving = {'A': ('AB', 'AC'), 'AC': ('ACD',), 'E' : ()}
        c2indd = pm.claz2indirect_deriving(claz2deriving)
        self.assertEqual(sorted(c2indd.get('A')), ['AB', 'AC', 'ACD'])
        self.assertEqual(sorted(c2indd.get('AC')), ['ACD'])
        self.assertEqual(c2indd.get('E'), None)

    def testClaz2MethodsDefinedInTheClassButNotInItsDerivings(self):
        claz2methods = {'A': ['l', 'm', 'n'], 'E': ['p'], 'AC': ['m', 'x'], 'ACD': ['n']}
        claz2indd = {'A': ('AB', 'AC', 'ACD'), 'AC': ('ACD',)}
        claz2modins = pm.claz2methods_defined_in_the_class_but_not_in_its_derivings(claz2methods, claz2indd)
        self.assertEqual(sorted(claz2modins.get('A')), ['l'])
        self.assertEqual(claz2modins.get('AB'), None)
        self.assertEqual(sorted(claz2modins.get('AC')), ['m', 'x'])
        self.assertEqual(sorted(claz2modins.get('ACD')), ['n'])
        self.assertEqual(sorted(claz2modins.get('E')), ['p'])

    def testGetBlockEntranceCellsNoBranchNoLoop(self):
        cells = [ 
             [0, 1, pm.INVOKE, ('A', 'm:()V')],
             [1, None, pm.RETURN, None],
        ]
        entrance_cell = [-1, 0, None, None]
        block_entrance_cells = pm.get_block_entrance_cells(cells, entrance_cell)
        self.assertEqual(sorted(block_entrance_cells), [])

    def testGetBlockEntranceCellsOneLoop(self):
        cells = [ 
             [0, 1, pm.INVOKE, ('A', 'm:()V')],
             [1, 2, pm.INVOKE, ('B', 'n:()V')],
             [2, 0, pm.INVOKE, ('C', 'o:()V')],
        ]
        entrance_cell = [-1, 0, None, None]
        block_entrance_cells = pm.get_block_entrance_cells(cells, entrance_cell)
        self.assertEqual(sorted(block_entrance_cells), [0])
    
    def testGetBlockEntranceCellsOneBranch(self):
        cells = [ 
             [0, 1, pm.BRANCHS, [2, 3, 4]],
             [1, 2, pm.RETURN, None],
             [2, 5, pm.INVOKE, ('A', 'm:()V')],
             [3, 5, pm.INVOKE, ('B', 'n:()V')],
             [4, 5, pm.INVOKE, ('C', 'o:()V')],
             [5, None, pm.RETURN, None],
        ]
        entrance_cell = [-1, 0, None, None]
        block_entrance_cells = pm.get_block_entrance_cells(cells, entrance_cell)
        self.assertEqual(sorted(block_entrance_cells), [5])
    
    def testOptmizeGotosInCellArray(self):
        cells = [ 
             [0, 1, pm.GOTO, 2],
             [1, 2, pm.RETURN, None],
             [2, 3, pm.GOTO, 4],
             [3, 4, pm.RETURN, None],
             [4, None, pm.RETURN, None],
        ]
        entrance_cell = [-1, 0, None, None]
        cs = [cell[:] for cell in cells]
        ec = entrance_cell[:]
        pm.optmize_gotos_in_cell_array(cs, ec)
        self.assertEqual(ec, [-1, 4, None, None])
        self.assertEqual(cs[0], [0, 1, pm.GOTO, 4])
        self.assertEqual(cs[1], [1, 4, pm.RETURN, None])
        self.assertEqual(cs[2], [2, 3, pm.GOTO, 4])
        self.assertEqual(cs[3], [3, 4, pm.RETURN, None])

    def testOptmizeGotosInCellArrayOneOperationInfiniteLoop(self):
        cells = [ 
             [0, 1, pm.GOTO, 0],
             [1, None, pm.RETURN, None],
        ]
        entrance_cell = [-1, 0, None, None]
        cs = [cell[:] for cell in cells]
        ec = entrance_cell[:]
        pm.optmize_gotos_in_cell_array(cs, ec)
        self.assertEqual(ec, [-1, 0, None, None])
        self.assertEqual(cs[0], [0, 1, pm.GOTO, 0])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()