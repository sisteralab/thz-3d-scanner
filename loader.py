import getpass
import os
import platform
import sys

cur_dir = os.path.abspath(os.path.dirname(__file__))  # Specifies the current directory.
ximc_dir = os.path.join(
    cur_dir, "ximc"
)  # Formation of the directory name with all dependencies.
ximc_package_dir = os.path.join(
    ximc_dir, "crossplatform", "wrappers", "python"
)  # Formation of the directory name with python dependencies.
sys.path.append(ximc_package_dir)  # add pyximc.py wrapper to python path

user_name = "root"
key_esc = "esc"

if platform.system() == "Windows":
    # Determining the directory with dependencies for windows depending on the bit depth.
    arch_dir = "win64" if "64" in platform.architecture()[0] else "win32"  #
    libdir = os.path.join(ximc_dir, arch_dir)
    if sys.version_info >= (3, 8):
        os.add_dll_directory(libdir)
    else:
        os.environ["Path"] = (
            libdir + ";" + os.environ["Path"]
        )  # add dll path into an environment variable
    # from msvcrt import getch as getch1
else:
    user_name = getpass.getuser()
    key_esc = "ctrl+u"
    print(user_name)
    if user_name == "root":
        pass
    else:
        pass

try:
    from pyximc import *
except ImportError as err:
    print(
        "Can't import pyximc module. The most probable reason is that you changed the relative location of the "
        "test_Python.py and pyximc.py files. See developers' documentation for details."
    )
    exit()
except OSError as err:
    # print(err.errno, err.filename, err.strerror, err.winerror) # Allows you to display detailed information by mistake.
    if platform.system() == "Windows":
        if (
            err.winerror == 193
        ):  # The bit depth of one of the libraries bindy.dll, libximc.dll, xiwrapper.dll
            # does not correspond to the operating system bit.
            print(
                "Err: The bit depth of one of the libraries bindy.dll, libximc.dll, xiwrapper.dll does not"
                " correspond to the operating system bit."
            )
        elif (
            err.winerror == 126
        ):  # One of the library bindy.dll, libximc.dll, xiwrapper.dll files is missing.
            print(
                "Err: One of the library bindy.dll, libximc.dll, xiwrapper.dll is missing."
            )
        # print(err)
        else:  # Other errors the value of which can be viewed in the code.
            print(err)
        print(
            "Warning: If you are using the example as the basis for your module, make sure that the dependencies"
            " installed in the dependencies section of the example match your directory structure."
        )
        print(
            "For correct work with the library you need: pyximc.py, bindy.dll, libximc.dll, xiwrapper.dll"
        )
    else:
        print(err)
        print(
            "Can't load libximc library. Please add all shared libraries to the appropriate places."
            " It is described in detail in developers' documentation. On Linux make sure you installed libximc-dev"
            " package.\nmake sure that the architecture of the system and the interpreter is the same"
        )
    exit()

if lib:
    print("Library loaded successfully")
    sbuf = create_string_buffer(64)
    lib.ximc_version(sbuf)
    print("Library version: " + sbuf.raw.decode().rstrip("\0"))
else:
    print("Could not load library.")
    exit()
