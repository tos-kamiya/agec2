#coding: utf-8

import unittest

import sys

import os.path as p
sys.path.insert(0, p.join(p.dirname(p.abspath(__file__)), '..', 'src'))

import asm_manip as am

B_asm = """
Compiled from "Inheritance.java"
class B extends A {
  B();
    Code:
       0: aload_0       
       1: invokespecial #1                  // Method A."<init>":()V
       4: return        
    LineNumberTable:
      line 6: 0

  public void calling_foo();
    Code:
       0: aload_0       
       1: invokevirtual #2                  // Method foo:()V
       4: return        
    LineNumberTable:
      line 7: 0
}
"""[1:-1].split('\n')

B_init_body = """
    Code:
       0: aload_0       
       1: invokespecial #1                  // Method A."<init>":()V
       4: return        
    LineNumberTable:
      line 6: 0
"""[1:-1].split('\n')

B_calling_foo_body = """
    Code:
       0: aload_0       
       1: invokevirtual #2                  // Method foo:()V
       4: return        
    LineNumberTable:
      line 7: 0
"""[1:-1].split('\n')

class TestAsmManip(unittest.TestCase):
    def testSplitIntoMethodIter(self):
        claz_method_sigs = [('B', '"<init>":()V'), ('B', 'calling_foo:()V')]
        for typ, values in am.split_into_method_iter('B.asm', B_asm):
            if typ == am.METHOD_CODE:
                claz_sig, body_lines = values
                self.assertTrue(claz_sig in claz_method_sigs)
                for L in body_lines:
                    self.assertTrue(L.startswith(' ' * 4))
                if claz_sig == claz_method_sigs[0]:
                    self.assertSequenceEqual(body_lines, B_init_body)
                elif claz_sig == claz_method_sigs[1]:
                    self.assertSequenceEqual(body_lines, B_calling_foo_body)
            elif typ == am.INHERITANCE:
                claz, imps, exts = values
                self.assertEqual(claz, 'B')
                self.assertSequenceEqual(imps, ('A',))
                self.assertSequenceEqual(exts, ())
            elif typ == am.COMPILED_FROM:
                self.assertEqual(values, "Inheritance.java")
            else:
                assert False
    
    def testSplitMethodBodyToCodeAndTables(self):
        code, exception_table, linenum_table = am.split_method_body_to_code_and_tables(B_init_body)
        self.assertSequenceEqual(code, [
                '       0: aload_0       ', 
                '       1: invokespecial #1                  // Method A."<init>":()V', 
                '       4: return        '
                ])
        self.assertEqual(exception_table, [])
        self.assertSequenceEqual(linenum_table, ['      line 6: 0'])
    
    def testRemoveGenericsARgs(self):
        s = "  <T extends java/lang/Object> jffi.AB$ObjectField addField(java.util.Map<T, jffi.AB$ObjectField>, T, java.lang.Class, jffi.AB$ObjectNameGenerator);"
        act = am.remove_generics_args(s)
        self.assertEqual(act, "  jffi.AB$ObjectField addField(java.util.Map, T, java.lang.Class, jffi.AB$ObjectNameGenerator);")

        s = "class com.kcp.ConstantResolver<E extends java.lang.Enum<E>> {"
        act = am.remove_generics_args(s)
        self.assertEqual(act, "class com.kcp.ConstantResolver {")
        
        s = "public class j.ffi.Struct$Enum<T extends java.lang.Enum<T>> extends j.ffi.Struct$Enum32<T> {"
        act = am.remove_generics_args(s)
        self.assertEqual(act, "public class j.ffi.Struct$Enum extends j.ffi.Struct$Enum32 {")

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
