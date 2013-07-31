Compiled from "Deligating.java"
public class Deligating {
  A a;

  B b;

  public Deligating();
    Code:
       0: aload_0       
       1: invokespecial #1                  // Method java/lang/Object."<init>":()V
       4: aload_0       
       5: new           #2                  // class A
       8: dup           
       9: invokespecial #3                  // Method A."<init>":()V
      12: putfield      #4                  // Field a:LA;
      15: aload_0       
      16: new           #5                  // class B
      19: dup           
      20: invokespecial #6                  // Method B."<init>":()V
      23: putfield      #7                  // Field b:LB;
      26: return        
    LineNumberTable:
      line 16: 0
      line 17: 4
      line 18: 15

  public void fooDirect();
    Code:
       0: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
       3: ldc           #9                  // String 1
       5: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
       8: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
      11: ldc           #11                 // String 2
      13: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
      16: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
      19: ldc           #12                 // String 3
      21: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
      24: aload_0       
      25: getfield      #4                  // Field a:LA;
      28: invokevirtual #13                 // Method A.foo:()V
      31: return        
    LineNumberTable:
      line 20: 0
      line 21: 8
      line 22: 16
      line 23: 24
      line 24: 31

  public void fooIndirect();
    Code:
       0: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
       3: ldc           #9                  // String 1
       5: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
       8: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
      11: ldc           #11                 // String 2
      13: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
      16: getstatic     #8                  // Field java/lang/System.out:Ljava/io/PrintStream;
      19: ldc           #12                 // String 3
      21: invokevirtual #10                 // Method java/io/PrintStream.println:(Ljava/lang/String;)V
      24: aload_0       
      25: getfield      #7                  // Field b:LB;
      28: invokevirtual #14                 // Method B.boo:()V
      31: return        
    LineNumberTable:
      line 26: 0
      line 27: 8
      line 28: 16
      line 29: 24
      line 30: 31
}
