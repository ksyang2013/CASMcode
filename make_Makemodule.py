#!/bin/env/python
from __future__ import (absolute_import, division, print_function, unicode_literals)
from builtins import *

import os
import re
from glob import glob
from os.path import join
from six import iteritems

# Notes:
#
# This script generates the 'Makemodule.am' files included in 'Makefile.am' to
# specify all the header files to be installed, the source files to be included
# in the libraries, the command line programs, the test programs, and flags and
# libraries necessary for them to be built and run.
#
# Typical usage is something like (configure options may vary):
# python make_Makemodule.py
# ./bootstrap.sh
# ./configure CXXFLAGS="-O3 -DNDEBUG -Wno-deprecated-register"
# make -j 4
# make check -j 4
#
# include/ and src/:
# - Files to be included in the libraries, under src/, and in the installed
#   headers, under include/, include all files except those matching the 
#   'default_exclude' regex pattern below.  Excluded files include those with 
#   the following extensions: .am, .hide, .old, .orig, .lo, .Plo, .o
#
# Testing:
# - Tests are organized in groups: tests/unit/<group>/<name>_test.cpp
# - Test projects go: @abs_top_srcdir@/tests/unit/test_projects
# - A @abs_top_srcdir@/tests/unit/run_test_<group>.in file is generated for
#   each group and used to setup the testing environment for 'make check'
# - See 'tests/README.md' for more about testing
#
# Makefile.am and configure.ac:
# - Makemodule.am and unit test files generated by this script are automatically
#   included in the autotools files between the lines:
#      '# BEGIN MAKEMODULE' and '# END MAKEMODULE'

### Strings ###

unittest_dir = join('tests', 'unit')

default_include = '.*'
default_exclude = '.*\.(dirstamp|gitignore|am|hide|old|orig|lo|Plo|o)'

### Libraries ###

lib_casm = ["libcasm.la"]

boost_libs = ["$(BOOST_SYSTEM_LIB)",
              "$(BOOST_FILESYSTEM_LIB)",
              "$(BOOST_PROGRAM_OPTIONS_LIB)",
              "$(BOOST_REGEX_LIB)",
              "$(BOOST_CHRONO_LIB)"]

boost_test_libs = ["$(BOOST_UNIT_TEST_FRAMEWORK_LIB)"]

lib_casm_testing = ["libcasmtesting.a"]

### Functions ###

def rm_existing():
    """Remove existing Makemodule.am files"""
    for root, dirs, files in os.walk(os.getcwd()):
        for f in files:
            if bool(re.match('Makemodule.am(\.test)*', f)):
                os.remove(join(root,f))

def find_files(loc, include=default_include, exclude=default_exclude, verbose=False):
    """Find files, recursively, excluding files that re.match 'exclude'"""
    res = []
    for root, dirs, files in os.walk(loc):
        for f in files:
            if bool(re.match(include, f)) and not bool(re.match(exclude, f)):
                res.append(join(root,f))
            else:
                if verbose:
                    print("skipping:", join(root,f), f, bool(re.match(exclude, f)))
    return res

def write_files(f, files):
    """Write a list of files to a Makemodule.am file"""
    try:
        index = 0
        for file in files:
            f.write('  ' + file)
            if index+1 == len(files):
                f.write('\n\n')
            else:
                f.write('\\\n')
            index += 1
    except Exception as e:
        print('Failed to write files:')
        print(files)
        raise e

def append_option(f, name, option, objlist):
    """Write <name>_<option> += ..."""
    if len(objlist):
        f.write(name + '_' + option + ' += \\\n')
        write_files(f, objlist)

def append(f, var, objlist):
    """Write <var> += ..."""
    if len(objlist):
        f.write(var + ' += \\\n')
        write_files(f, objlist)

def write_option(f, name, option, objlist):
    """Write <name>_<option> = ..."""
    if len(objlist):
        f.write(name + '_' + option + ' = \\\n')
        write_files(f, objlist)

def has_tests(dir):
    """Check if '*_test.cpp' files exist in dir"""
    return len(glob(join(dir, '*_test.cpp'))) > 0

def includedir(f, includedir, include=default_include, exclude=default_exclude):
    """Write contents of Makemodule.am for copying header files
    
    - Write Makemodule.am file to copy all files/dir from include directories
    
    f: file object
    includedir: join('include', 'casm') or join('include', 'ccasm')
    """
    files = find_files(includedir, include=include, exclude=exclude)
    
    # create dictionary of '<direcoryname>:[filepaths of files in directory]'
    data = {}
    for file in files:
        dir = os.path.split(file)[0]
        if dir not in data:
            data[dir] = []
        data[dir].append(file)
    for (dir,filelist) in iteritems(data):
        # ex: dir=include/casm/app
        # ex: subpath_parts = ['casm','app']
        subpath_parts = dir.split(os.sep)[1:]
        # ex: subpath = 'casm/app'
        subpath = os.path.join(*subpath_parts)
        # ex: subpathname = 'casm_app_include'
        subpathname = '_'.join(subpath_parts + ['include'])
        f.write(subpathname + 'dir=$(includedir)/' + subpath + '\n\n')
        write_option(f, subpathname, 'HEADERS', filelist)

def testdir(f, group, extradist_ext=['*.hh', '*.cc', '*.json', '*.txt'], verbose=True):
    """Include portion of Makemodule.am for unit tests
    
    - Scans a tests/unit/<group> directory for <testname>_test.cpp unit test files,
    and if found, generates Makemodule.am entries for the test
    - Includes any 'extradist' files found.
    """
    if verbose:
        print("Test group:", group)
    loc = join(unittest_dir, group)
    
    # check_PROGRAMS
    append_option(f, 'check', 'PROGRAMS', ['casm_unit_' + group])
    
    # CXXFLAGS
    write_option(f, 'casm_unit_' + group, 'CXXFLAGS', ['$(AM_CXXFLAGS)', '-I$(top_srcdir)/tests/unit/'])
    
    # SOURCES
    files = glob(join(loc, '*_test.cpp'))
    if verbose:
        print("Test sources:")
        for file in files:
            print('  ' + file)
    write_option(f, 'casm_unit_' + group, 'SOURCES', ['tests/unit/unit_test.cpp'] + files)
    
    # LDADD
    write_option(f, 'casm_unit_' + group, 'LDADD', lib_casm + boost_libs + boost_test_libs + lib_casm_testing)
    
    # EXTRA_DIST
    extradist_files = []
    for ext in extradist_ext:
        extradist_files += glob(join(loc, ext))
    if len(extradist_files):
        if verbose:
            print("Extra-dist files:")
            for file in extradist_files:
                print('  ' + file)
        append(f, 'EXTRA_DIST', extradist_files)
    
    if verbose:
        print('')
    
    # TESTS
    append(f, 'TESTS', [join('tests', 'unit', group, 'run_test_' + group)])

def run_test_in(group):
    """Write 'run_test_<group>.in' file"""
    loc = join(unittest_dir, group)
    with open(join(loc, 'run_test_' + group + '.in'), 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('GROUP=' + group + '\n')
        f.write('export PATH=@abs_top_builddir@:$PATH\n')
        f.write('cd @abs_top_srcdir@\n')
        f.write('mkdir -p @abs_top_srcdir@/tests/unit/test_projects\n')
        f.write(': ${TEST_FLAGS:="--log_level=test_suite --catch_system_errors=no"}\n')
        f.write('@abs_top_builddir@/casm_unit_$GROUP ${TEST_FLAGS}\n')

def replace_lines(filename, lines_to_insert):
    """Replace lines in a file
    
    All lines in between '# BEGIN MAKEMODULE' and '# END MAKEMODULE' are replaced
    with 'lines_to_insert'.
    
    Args:
        filename (str): filename
        lines_to_insert (List[str]): list of lines to insert (should include '\n')
    """
    lines_to_write = []
    with open(filename, 'r') as f:
        line = f.readline()
        while len(line):
            if line.rstrip() == '# BEGIN MAKEMODULE':
                lines_to_write.append(line)
                lines_to_write += lines_to_insert
                while line.rstrip() != '# END MAKEMODULE':
                    line = f.readline()
            lines_to_write.append(line)
            line = f.readline()
    with open(filename, 'w') as f:
        for line in lines_to_write:
            f.write(line)

def main():

    # remove old Makemodule.am
    rm_existing()
    
    makemodules = []

    # include/casm/Makemodule.am
    dir = join('include', 'casm')
    print('Working on', dir)
    makemodules.append(join('include', 'casm', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        includedir(f, dir)
    
    # include/ccasm/Makemodule.am
    dir = join('include', 'ccasm')
    print('Working on', dir)
    makemodules.append(join('include', 'ccasm', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        includedir(f, dir)
    
    # src/casm/Makemodule.am
    dir = join('src', 'casm')
    print('Working on', dir)
    makemodules.append(join('src', 'casm', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        name = 'libcasm_la'
        append(f, 'lib_LTLIBRARIES', ['libcasm.la'])
        src_exclude = '(' + default_exclude + ')|(.*test_g(un)?zip.C)'
        write_option(f, name, 'SOURCES', find_files(dir, include='.*\.(c|cc|cpp|C)', exclude=src_exclude))
        write_option(f, name, 'LIBADD', boost_libs)
        write_option(f, name, 'LDFLAGS', ['-avoid-version', '$(BOOST_LDFLAGS)'])
        
        # always keep version uptodate
        f.write('src/casm/version/autoversion.o: .FORCE\n\n')
    
    # src/ccasm/Makemodule.am
    dir = join('src', 'ccasm')
    print('Working on', dir)
    makemodules.append(join('src', 'ccasm', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        name = 'libccasm_la'
        append(f, 'lib_LTLIBRARIES', ['libccasm.la'])
        write_option(f, name, 'SOURCES', find_files(dir, include='.*\.(c|cc|cpp|C)'))
        write_option(f, name, 'LDFLAGS', ['-avoid-version'])
    
    # apps/ccasm/Makemodule.am
    dir = join('apps', 'ccasm')
    print('Working on', dir)
    makemodules.append(join('apps', 'ccasm', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        append(f, 'bin_PROGRAMS', ['ccasm'])
        append(f, 'man1_MANS', ['man/ccasm.1'])
        write_option(f, 'ccasm', 'SOURCES', ['apps/ccasm/ccasm.cpp'])
        write_option(f, 'ccasm', 'LDADD', lib_casm + boost_libs)
        
    
    # apps/completer/Makemodule.am
    dir = join('apps', 'completer')
    print('Working on', dir)
    makemodules.append(join('apps', 'completer', 'Makemodule.am'))
    with open(makemodules[-1], 'w') as f:
        f.write('if ENABLE_BASH_COMPLETION\n\n')
        f.write('bashcompletiondir=$(BASH_COMPLETION_DIR)\n\n')
        write_option(f, 'dist_bashcompletion', 'DATA', ['apps/completer/casm'])
        append_option(f, 'bin', 'PROGRAMS', ['casm-complete'])
        write_option(f, 'casm_complete', 'SOURCES', ['apps/completer/complete.cpp'])
        write_option(f, 'casm_complete', 'LDADD', lib_casm + boost_libs)
        f.write('endif\n')
    
    # tests/unit/Makemodule.am
    dir = join('tests', 'unit')
    print('Working on', dir)
    makemodules.append(join(unittest_dir, 'Makemodule.am'))
    testnames = []
    with open(makemodules[-1], 'w') as f:
        
        # PROGRAMS (complete tests)
        append_option(f, 'check', 'PROGRAMS', ['ccasm'])
        
        # LIBRARIES
        append(f, 'noinst_LIBRARIES', ['libcasmtesting.a'])
        
        # SOURCES
        libcasmtesting_files = []
        libcasmtesting_files += glob(join(unittest_dir,'*.cpp'))
        libcasmtesting_files += glob(join(unittest_dir,'*.cc'))
        libcasmtesting_files += glob(join(unittest_dir,'*.hh'))
        write_option(f, 'libcasmtesting_a', 'SOURCES', libcasmtesting_files)
        
        # find tests
        #   find directories in 'tests/unit' that have '<testname>_test.cpp' files
        #   find 'EXTRA_DIST' files = (in test directories with *.hh *.cc *.json *.txt)
        for file_or_dir in os.listdir(unittest_dir):
            test_dir = join(unittest_dir, file_or_dir)
            if os.path.isdir(test_dir) and has_tests(test_dir):
                print(test_dir + " has tests!")
                testnames.append(file_or_dir)
                testdir(f, file_or_dir)
                run_test_in(file_or_dir)
            else:
                pass
                #print(test_dir + " does not have tests!")
     
    # Update 'Makefile.am' to include all Makemodule.am
    replace_lines('Makefile.am', ['include $(srcdir)/'+val+'\n' for val in makemodules])
    
    # Update 'configure.ac' to include all 'run_test_<name>'
    lines_to_insert = []
    for name in testnames:
        runtest = join('tests', 'unit', name, 'run_test_' + name)
        lines_to_insert.append('AC_CONFIG_FILES([' + runtest + '], [chmod +x ' + runtest + '])\n')
    replace_lines('configure.ac', lines_to_insert)


if __name__ == "__main__":
    main()

