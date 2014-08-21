
from setuptools import setup, find_packages
# Warning : do not import the distutils extension before setuptools
# It does break the cythonize function calls
from distutils.extension import Extension
from distutils.sysconfig import get_config_vars

import glob
import os
import platform
import sys

from Cython.Distutils import build_ext
from Cython.Build import cythonize

import numpy

# Symbols added in quantlib.ql from the support code are not exposed to 
# the rest of the library. We need to expose them by hand ... 
# Gorry but works ... Need to find a real solution asap
def load_symbols():
    with open('exported_symbols.txt') as fh:
        content = fh.read()
        for line in content.split('\n'):
            if line.startswith('#'):
                continue
            else:
                yield line.strip()

SYMBOLS = list(load_symbols())

DEBUG_BUILD = True

if sys.platform in ['darwin', 'linux2']:
    ## From SO: hack to remove warning about strict prototypes
    ## http://stackoverflow.com/questions/8106258/cc1plus-warning-command-line-option-wstrict-prototypes-is-valid-for-ada-c-o
    (opt,) = get_config_vars('OPT')
    os.environ['OPT'] = " ".join(
        flag for flag in opt.split() if flag != '-Wstrict-prototypes')

SUPPORT_CODE_INCLUDE = './cpp_layer'
CYTHON_DIRECTIVES = {"embedsignature": True}
BUILDING_ON_WINDOWS = False

#FIXME: would be good to be able to customize the path with envrironment
# variables in place of hardcoded paths ...
if sys.platform == 'darwin':
    INCLUDE_DIRS = ['/usr/local/include',
                    '/Users/dpinte/projects/sources/boost_1_55_0',
                    '.', SUPPORT_CODE_INCLUDE]
    LIBRARY_DIRS = ["/usr/local/lib"]
elif sys.platform == 'win32':
    INCLUDE_DIRS = [
        r'C:\dev\QuantLib-1.3',  # QuantLib headers
        r'C:\dev\boost_1_55_0_lib',  # Boost headers
        '.',
        SUPPORT_CODE_INCLUDE
    ]
    LIBRARY_DIRS = [
        r'C:\dev\QuantLib-1.3\lib',
        r'C:\dev\QuantLib-1.3\Release',
        r'C:\dev\boost_1_55_0_lib\lib32-msvc-9.0',
        r'.',
        # On Win32, we need to explicitely link with the quantlib.ql.pyd
        # We point to the directory where the generated .lib file is and 
        # allows us to link against the content of ql.pyd/.lib
        r'C:\dev\pyql\build\temp.win32-2.7\Release\quantlib'
    ]
    BUILDING_ON_WINDOWS = True

elif sys.platform == 'linux2':
    # good for Debian / ubuntu 10.04 (with QL .99 installed by default)
    INCLUDE_DIRS = ['/usr/local/include', '/usr/include', '.', SUPPORT_CODE_INCLUDE]
    LIBRARY_DIRS = ['/usr/local/lib', '/usr/lib', ]

INCLUDE_DIRS.append(numpy.get_include())

def get_define_macros():
    defines = [ ('HAVE_CONFIG_H', None)]
    #defines = []
    if sys.platform == 'win32':
        # based on the SWIG wrappers
        defines += [
            (name, None) for name in [
                '__WIN32__', 'WIN32', 'NDEBUG', '_WINDOWS', 'NOMINMAX', 'WINNT',
                '_WINDLL', '_SCL_SECURE_NO_DEPRECATE', '_CRT_SECURE_NO_DEPRECATE',
                '_SCL_SECURE_NO_WARNINGS',
            ]
        ]
    return defines

def get_extra_compile_args():
    if sys.platform == 'win32':
        args = ['/GR', '/FD', '/Zm250', '/EHsc' ]
        if DEBUG_BUILD:
            args.append('/Z7')
    else:
        args = []

    return args

def get_extra_link_args():
    if sys.platform == 'win32':
        # FORCE:MULTIPLE has been added to prevent linker issues with certain
        # modules. This needs to be investigated. The linker seems to be 
        # unhappy with finding some symbols in ql.lib/pyd and in the QuantLib.lib
        # 
        args = ['/subsystem:windows', '/machine:I386', '/FORCE:MULTIPLE']
        if DEBUG_BUILD:
            args.append('/DEBUG')
    elif sys.platform == 'darwin':
        major, minor, patch = [
            int(item) for item in platform.mac_ver()[0].split('.')]
        if major == 10 and minor >= 9:
            # On Mac OS 10.9 we link against the libstdc++ library.
            args = ['-stdlib=libstdc++', '-mmacosx-version-min=10.6']
        else:
            args = []
    else:
        args = []

    return args

# FIXME: Naive way to select the QL library name ...
QL_LIBRARY = 'test_dll' if BUILDING_ON_WINDOWS else 'QuantLib'

CYTHON_DIRECTIVES = {"embedsignature": True}

def collect_extensions():
    """ Collect all the directories with Cython extensions and return the list
    of Extension.

    Th function combines static Extension declaration and calls to cythonize
    to build the list of extenions.
    """

    default_args = dict(
        language='c++',
        include_dirs=INCLUDE_DIRS + [numpy.get_include()],
        library_dirs=LIBRARY_DIRS,
        define_macros = get_define_macros(),
        extra_compile_args = get_extra_compile_args(),
        extra_link_args = get_extra_link_args(),
        cython_directives = CYTHON_DIRECTIVES,
    )

    ql_extension = Extension('quantlib.ql',
        ['quantlib/ql.pyx',
         'cpp_layer/ql_settings.cpp',
         'cpp_layer/yield_piecewise_support_code.cpp',
         'cpp_layer/credit_piecewise_support_code.cpp',
         'cpp_layer/mc_vanilla_engine_support_code.cpp',
         'cpp_layer/businessdayconvention_support_code.cpp',
         'cpp_layer/simulate_support_code.cpp',
        ],
        libraries=[QL_LIBRARY], #, 'Quantlib-vc90-mt'],
        **default_args
    )

    # Dictionnary of arguments used by all the extensions linking
    # against the quantlib.ql extension. On Windows, it requires a
    # specific setup, reason why we can't use default_args.
    ql_ext_args = default_args.copy()

    if BUILDING_ON_WINDOWS:
        ql_ext_args['libraries'] = ['ql','test_dll']
        # We need to export the symbols of the support code for them to be
        # visible by the other Cython extensions linked to quantlib.ql
        ql_extension.export_symbols = SYMBOLS
    else:
        ql_ext_args['libraries'] = [QL_LIBRARY]

    settings_extension = Extension('quantlib.settings',
        ['quantlib/settings/settings.pyx'],
        **ql_ext_args
    )

    test_extension = Extension('quantlib.test.test_cython_bug',
        ['quantlib/test/test_cython_bug.pyx'],
        **ql_ext_args
    )

    simulate_extension = Extension('quantlib.sim.simulate',
        ['quantlib/sim/simulate.pyx'],
        **ql_ext_args
    )

    mc_vanilla_engine_extension = Extension(
        'quantlib.pricingengines.vanilla.mcvanillaengine',
        ['quantlib/pricingengines/vanilla/mcvanillaengine.pyx'],
        **ql_ext_args
    )
    
    date_extension = Extension(
        'quantlib.time.date',
        ['quantlib/time/date.pyx'],
        **ql_ext_args
    )
    
    calendar_extension = Extension(
        'quantlib.time.calendar',
        ['quantlib/time/calendar.pyx'],
        **ql_ext_args
    )
    
    null_calendar_extension = Extension(
        'quantlib.time.calendars.null_calendar',
        ['quantlib/time/calendars/null_calendar.pyx'],
        **ql_ext_args
    )
    
    germany_calendar_extension = Extension(
        'quantlib.time.calendars.germany',
        ['quantlib/time/calendars/germany.pyx'],
        **ql_ext_args
    )
    
    us_calendar_extension = Extension(
        'quantlib.time.calendars.united_states',
        ['quantlib/time/calendars/united_states.pyx'],
        **ql_ext_args
    )
    
    uk_calendar_extension = Extension(
        'quantlib.time.calendars.united_kingdom',
        ['quantlib/time/calendars/united_kingdom.pyx'],
        **ql_ext_args
    )
    
    switzerland_calendar_extension = Extension(
        'quantlib.time.calendars.switzerland',
        ['quantlib/time/calendars/switzerland.pyx'],
        **ql_ext_args
    )
    
    japan_calendar_extension = Extension(
        'quantlib.time.calendars.japan',
        ['quantlib/time/calendars/japan.pyx'],
        **ql_ext_args
    )
    
    schedule_extension = Extension(
        'quantlib.time.schedule',
        ['quantlib/time/schedule.pyx'],
        **ql_ext_args
    )
    
    daycounter_extension = Extension(
        'quantlib.time.daycounter',
        ['quantlib/time/daycounter.pyx'],
        **ql_ext_args
    )
    
    aadaycounter_extension = Extension(
        'quantlib.time.daycounters.actual_actual',
        ['quantlib/time/daycounters/actual_actual.pyx'],
        **ql_ext_args
    )

    th360daycounter_extension = Extension(
        'quantlib.time.daycounters.thirty360',
        ['quantlib/time/daycounters/thirty360.pyx'],
        **ql_ext_args
    )
    
    instrument_extension = Extension(
        'quantlib.instruments.instrument',
        ['quantlib/instruments/instrument.pyx'],
        **ql_ext_args
    )

    bond_extension = Extension(
        'quantlib.instruments.bonds',
        ['quantlib/instruments/bonds.pyx'],
        **ql_ext_args
    )

    engine_extension = Extension(
        'quantlib.pricingengines.engine',
        ['quantlib/pricingengines/engine.pyx'],
        **ql_ext_args
    )    
    
    cashflow_extension = Extension(
        'quantlib.cashflow',
        ['quantlib/cashflow.pyx'],
        **ql_ext_args
    )  

    manual_extensions = [
        ql_extension,
        #settings_extension,
        test_extension,
        #bond_extension,
        #date_extension,
        #calendar_extension,
        #schedule_extension,
        #instrument_extension,
        #engine_extension,
        #cashflow_extension,
        #daycounter_extension,
        #aadaycounter_extension,
        #th360daycounter_extension,
        #simulate_extension,
        #mc_vanilla_engine_extension
    ]

    cython_extension_directories = []
    for dirpath, directories, files in os.walk('quantlib'):

        # if the directory contains pyx files, cythonise it
        if len(glob.glob('{0}/*.pyx'.format(dirpath))) > 0:
            cython_extension_directories.append(dirpath)

    collected_extensions = cythonize(
        [
            Extension('*', ['{0}/*.pyx'.format(dirpath)], **ql_ext_args
            ) for dirpath in cython_extension_directories
        ]
    )

    # remove  all the manual extensions from the collected ones
    names = [extension.name for extension in manual_extensions]
    for ext in collected_extensions[:]:
        if ext.name in names: # or 'swap' not in ext.name:
            collected_extensions.remove(ext)
            continue

    extensions = manual_extensions + collected_extensions

    return extensions

setup(
    name = 'quantlib',
    version = '0.2',
    author = 'Didrik Pinte, Patrick Henaff',
    license = 'BSD',
    packages = find_packages(),
    ext_modules = collect_extensions(),
    cmdclass = {'build_ext': build_ext},
    install_requires = ['distribute', 'cython'],
    zip_safe = False
)
