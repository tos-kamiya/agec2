class A {
	public void foo() {
		System.out.println("4");
		System.out.println("5");
		System.out.println("6");
	}
}

class B {
	A a = new A();
	public void boo() {
		a.foo();
	}
}

public class Deligating {
	A a = new A();
	B b = new B();
	public void fooDirect() {
		System.out.println("1");
		System.out.println("2");
		System.out.println("3");
		a.foo();
	}
	public void fooIndirect() {
		System.out.println("1");
		System.out.println("2");
		System.out.println("3");
		b.boo();
	}
}



