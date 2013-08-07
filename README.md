[![Build Status](https://travis-ci.org/tos-kamiya/agec2.png?branch=master)](https://travis-ci.org/tos-kamiya/agec2)

# agec

Agec, an arbitrary-granularity execution clone detection tool

Agec generates all possible execution sequences from Java byte code(s)
to detect the same execution sub-sequences from the distinct places in source files.

## Short walktrough

This sample is to detect code clones from a Java file: ShowWeekday.java.

```bash
$ javac ShowWeekday.java
$ javap -c -p -l -constants ShowWeekday > disasm/ShowWeekday.asm
$ gen_ngram.py -a disasm > ngrams.txt
$ det_clone.py ngrams.txt > clone-indices-md.txt
$ mmd_clone.py clone-indices-md.txt > clone-indices.txt
$ tosl_clone.py -a disasm clone-indices.txt > clone-linenums.txt
```

## Usage

Agec's core programs are:

**gen_ngram.py**. Generates n-grams of execution sequences of Java program.

**det_clone.py**. Identifies the same n-grams and reports them as code clones.

Agec also includes the following utilities:

**mmd_clone.py**. Merge multiple-depth code clones (a clone set in which traces have distinct depths but sharing the same starting location).

**tosl_clone.py**. Converts locations of code clones (from byte-code index) to line numbers of source files.

**exp_clone.py**. Calculates some metrics from each code clone.

**run_disasm.py**. Disassembles a jar file (with 'javap' disassembler) and generate disassemble-result files.

### gen_ngram.py

gen_ngram.py reads given (disassembled) Java byte-code files, 
generates n-grams of method invocations from them and outputs n-grams to the standard output.

usage: gen_ngram.py -a asm_directory -n size > ngram

Here, 'asm_directory' is a directory which contains the disassemble result files (*.asm).
'size' is a length of each n-gram (default value is 6).

Note that a disassemble file need to be generated from *.class file with a command
'javap -c -p -l -constants', because gen_ngram.py requires a line number of each byte code.

### det_clone.py

det_clone.py reads a n-gram file, identifies the same n-grams, 
and outputs them as code clones to the standard output.

usage: det_clone.py ngram_file > clone_index

Here, 'ngram_file' is a n-gram file, which has been generated with gen_ngram.py.

Each location in the result is shown in byte-code index.
In order to convert locations to line numbers of source files, use tosl_clone.py.

### mmd_clone.py

mmd_clone.py is optional but helpful to analysis of code clones.
When two code fragments are a code clone, that is, their execution traces 
contain the same method invocation sequence at some level (in terms of call tree),
their deeper execution traces are also clones.
mmd_clone.py removes a code clone of the deeper traces in case of
its shallower clone is included in a detection result.

usage: mmd_clone.py clone_index > filtered_clone_index

Here, 'clone_index' is the code-clone detection result that has been generated with
det_clone.py. 
The output is formatted in the same format of 'clone_index'.

### tosl_clone.py

tosl_clone.py reads Java byte-code files and a code-clone detection result, 
converts each location of code clone into line number, 
and outputs the converted code-clone data to the standard output.

usage: tosl_clone.py -a asm_directory clone_index > clone-linenum

Here, 'asm_directory' is a directory containing disassembled result files and
'clone_index' is the code-clone detection result that has been generated with
det_clone.py.

### run_disasm.py

run_disasm.py disassembles Java class files 
(and optionally expands a jar file to class files before disassembling).
Because agec requires the disassembled text files as input 
that are disassembled with specific options 'javap -c -p -l -constants' of javap,
so run_disassemble.py will help such disassembling task.

To disassemble class files,

usage: run_disassemble.py classlist -o asm_direcotry

Here, classlist specifies target (disassembled) classes.
A classlist file contains a class name per line.
If an option '--classpath directory' is used, read class files from the
directory. Otherwise, the tool assumes class files are contained
in the current directory.

To expand a jar file and disassemble class files contained the jar file,

usage: run_disassemble.py --jar jar_file -o asm_directory

## Publish

* Toshihiro Kamiya, "Agec: An Execution-Semantic Clone Detection Tool," Proc. IEEE ICPC 2013, pp. 227-229 [link to the paper](http://toshihirokamiya.com/docs/p227-kamiya.pdf).

## License

Agec is distributed under [MIT License](http://opensource.org/licenses/mit-license.php).
