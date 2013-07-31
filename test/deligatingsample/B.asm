Compiled from "Deligating.java"
class B {
  A a;

  B();
    Code:
       0: aload_0       
       1: invokespecial #1                  // Method java/lang/Object."<init>":()V
       4: aload_0       
       5: new           #2                  // class A
       8: dup           
       9: invokespecial #3                  // Method A."<init>":()V
      12: putfield      #4                  // Field a:LA;
      15: return        
    LineNumberTable:
      line 9: 0
      line 10: 4

  public void boo();
    Code:
       0: aload_0       
       1: getfield      #4                  // Field a:LA;
       4: invokevirtual #5                  // Method A.foo:()V
       7: return        
    LineNumberTable:
      line 12: 0
      line 13: 7
}
