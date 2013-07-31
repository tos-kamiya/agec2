#coding: utf-8

import unittest

import itertools
import sys

import os.path as p
sys.path.insert(0, p.join(p.dirname(p.abspath(__file__)), '..', 'src'))

from enum_generator import EnumGenerator
import clonefile_manip as cm

import mmd_clone as mmd

clone_A_lines = """
ope:
  methodA:()V
loc:
  Hoge.fuga()V,1 >0
  Hoge.hoge()V,2 >0

"""[1:-1].split('\n')

clone_B_lines = """
ope:
  methodB:()V
loc:
  Hoge.fuga()V,1 >0
  Hoge.hoge()V,2 >1

"""[1:-1].split('\n')

clone_C_lines = """
ope:
  methodC:()V
loc:
  Hoge.fuga()V,1 >1
  Hoge.hoge()V,2 >0

"""[1:-1].split('\n')

clone_D_lines = """
ope:
  methodD:()V
loc:
  Hoge.fuga()V,1 >1
  Hoge.hoge()V,2 >1

"""[1:-1].split('\n')

def decode(item, ope_enum, startingloc_enum):
    opeiseq, startlociseq, depthseq = item
    opeseq = map(ope_enum.to_str, opeiseq)
    startlocseq = map(startingloc_enum.to_str, startlociseq)
    return tuple(opeseq), tuple(u'%s >%d' % sd for sd in zip(startlocseq, depthseq))

class TestMergeMultipleDepthClone(unittest.TestCase):
    def test_on_one_shallowest(self):
        line_blocks = [clone_A_lines, clone_B_lines, clone_C_lines, clone_D_lines]
        for lbs in itertools.permutations(line_blocks):
            clone_lines = []
            for lb in lbs:
                clone_lines.extend(lb)

            ope_enum = EnumGenerator()
            startingloc_enum = EnumGenerator()

            it = cm.read_clone_iter(clone_lines)
            ope_startloc_depth_list = mmd.remove_deeper_clones(it, ope_enum, startingloc_enum)
    
            r = [decode(item, ope_enum, startingloc_enum) for item in ope_startloc_depth_list]
            self.assertEqual(r, [(('methodA:()V',), (u'Hoge.fuga()V,1 >0', u'Hoge.hoge()V,2 >0'))])

    def test_on_two_shallower(self):
        line_blocks = [clone_B_lines, clone_C_lines, clone_D_lines]
        for lbs in itertools.permutations(line_blocks):
            clone_lines = []
            for lb in lbs:
                clone_lines.extend(lb)

            ope_enum = EnumGenerator()
            startingloc_enum = EnumGenerator()
    
            it = cm.read_clone_iter(clone_lines)
            ope_startloc_depth_list = mmd.remove_deeper_clones(it, ope_enum, startingloc_enum)
    
            r = [decode(item, ope_enum, startingloc_enum) for item in ope_startloc_depth_list]
            r.sort()
            self.assertSequenceEqual(r, [
                (('methodB:()V',), (u'Hoge.fuga()V,1 >0', u'Hoge.hoge()V,2 >1')), 
                (('methodC:()V',), (u'Hoge.fuga()V,1 >1', u'Hoge.hoge()V,2 >0')), 
            ])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()