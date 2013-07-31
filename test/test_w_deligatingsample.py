"""
This test script contains regression tests of command-line tools,
gen_ngram.py, det_clone.py, tosl_clone.py, and exp_clone.py.

Use this script to detect inintended spec changes of these tools.

Warning: These tests may fail when any implementation detail is changed.
I've taken care about that these tests independent to the order of clones 
detected or the order of n-grams are generated.
However, this is far from a perfect solution for independability 
against implementation issues. 
In some case of implementation change, these tests will fail.
"""

import unittest

import os.path as p
import subprocess

#sys.path.insert(0, p.join(p.dirname(p.abspath(__file__)), '..', 'src'))

J = p.join

PROG_DIR = p.join(p.dirname(p.abspath(__file__)), '..', 'src')
DATA_DIR = J(p.dirname(__file__), "deligatingsample")
REF_DATA_DIR = J(DATA_DIR, "reference_data")

def read_text(filepath):
    with open(filepath, "rb") as f:
        return f.read().decode("utf-8")

def split_by_empty_line(lines):
    blocks = []
    curblock = []
    for L in lines:
        if not L:
            if curblock:
                blocks.append(curblock)
                curblock = []
        else:
            curblock.append(L)
    if curblock:
        blocks.append(curblock)
        curblock = []
    return blocks

class TestWithDeligatingSample(unittest.TestCase):
    def testExpClone(self):
        text = subprocess.check_output(["python", J(PROG_DIR, "exp_clone.py"), "-t", "-a", DATA_DIR, J(REF_DATA_DIR, "clone-index.txt")]).decode('utf-8')
        text_blocks = sorted(map(tuple, split_by_empty_line(text.split('\n'))))
        ref_text = read_text(J(REF_DATA_DIR, "clone-t-index.txt"))
        ref_text_blocks = sorted(map(tuple, split_by_empty_line(ref_text.split('\n'))))
        self.assertSequenceEqual(text_blocks[0], ref_text_blocks[0])
        self.assertSequenceEqual(text_blocks[1], ref_text_blocks[1])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
