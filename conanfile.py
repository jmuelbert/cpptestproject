# -*- coding: utf-8 -*-
#
#  SPDX-FileCopyrightText: 2022 Jürgen Mülbert <juergen.muelbert@gmail.com>
#
#  SPDX-License-Identifier: GPL-3.0-or-later
#

import os
import re

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain
from conan.tools.files import load, rmdir
from conan.tools.gnu import AutotoolsToolchain, AutotoolsDeps
from conan.tools.microsoft import unix_path, VCVars, is_msvc
# from conan.tools.scm import Version
from conan.errors import ConanInvalidConfiguration
from conan.errors import ConanException

# TODO  replace with new tools from Conan 2.0
from conans.tools import check_min_cppstd, get_env
from conans.tools import Version
required_conan_version = ">=1.45.0"


class cppTestConan(ConanFile):
    name = "cppTest"
    homepage = "https://github.com/jmuelbert/cpptestproject"
    author = "Jürgen Mülbert"
    description = "A cpp and conan test project"
    topics = (
        "conan",
        "cpp",
        "c++",
        "cmake",
        "test",
    )

    license = "GPL V3+"
    url = "https://github.com/jmuelbert/cpptestproject"
    settings = "os", "compiler", "build_type", "arch"

    options = {
        "shared": [True, False],
        "build_docs": [True, False],
        "build_translations": [True, False]
    }

    default_options = {
        "shared": False,
        "build_docs": False,
        "build_translations": False
    }

    exports = ["License"]
    exports_sources = [
        "docs/*",
        "src/*",
        "test/*",
        "cmake/*",
        "example/*",
        "CMakeLists.txt"
    ]
    no_copy_source = True
    generators = (
        "cmake_find_package_multi",
        "markdown",
        "txt"
    )

    requires = (
        "spdlog/[>=1.9.2]",
        "cli11/2.2.0",
        "catch2/2.13.9"
    )

    @property
    def _run_tests(self):
        return get_env("CONAN_RUN_TESTS", False)

    @property
    def _use_libfmt(self):
        compiler = self.settings.compiler
        version = Version(self.settings.compiler.version)
        std_support = \
            (compiler == "Visual Studio" and version >= 17 and compiler.cppstd == 23) or \
            (compiler == "msvc" and version >= 193 and compiler.cppstd == 23)
        return not std_support

    @property
    def _use_range_v3(self):
        compiler = self.settings.compiler
        version = Version(self.settings.compiler.version)
        return "clang" in compiler and compiler.libcxx == "libc++" and version < 14

    @property
    def _msvc_version(self):
        compiler = self.settings.compiler
        if compiler.update:
            return int(f"{compiler.version}{compiler.update}")
        else:
            return int(f"{compiler.version}0")


    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def set_version(self):
        content = load(self, os.path.join(self.recipe_folder, "CMakeLists.txt"))
        version = re.search(r"project\([^\)]+VERSION (\d+\.\d+\.\d+)[^\)]*\)", content).group(1)
        self.version = version.strip()

    def requirements(self):
        if self._use_libfmt:
            self.requires("fmt/8.1.1")

        if self._use_range_v3:
            self.requires("range-v3/0.11.0")

    def build_requirements(self):
        if self.options.build_docs:
            self.tool_requires("doxygen/1.9.4")

    # TODO Replace with `valdate()` for Conan 2.0 (https://github.com/conan-io/conan/issues/10723)
    def configure(self):
        compiler = self.settings.compiler
        version = Version(str(self.settings.compiler.version))
        print(version)
        if compiler == "gcc":
            if version < 10:
                raise ConanInvalidConfiguration("mp-units requires at least g++-10")
        elif compiler == "clang":
            if version < 12:
                raise ConanInvalidConfiguration("mp-units requires at least clang++-12")
        elif compiler == "apple-clang":
            if version < 13:
                raise ConanInvalidConfiguration(
                    "mp-units requires at least AppleClang 13"
                )
        elif compiler == "Visual Studio":
            if version < 16:
                raise ConanInvalidConfiguration(
                    "mp-units requires at least Visual Studio 16.9"
                )
        elif compiler == "msvc":
            if self._msvc_version < 1928:
                raise ConanInvalidConfiguration("mp-units requires at least MSVC 19.28")
        else:
            raise ConanInvalidConfiguration("Unsupported compiler")
        check_min_cppstd(self, 20)


    # TODO Uncomment this when environment is supported in the Conan toolchain
    # def config_options(self):
    #     if not self._run_tests:
    #         # build_docs has sense only in a development or CI build
    #         del self.options.build_docs

    def generate(self):
        tc = CMakeToolchain(self)
        # if self._run_tests:  # TODO Enable this when environment is supported in the Conan toolchain
        tc.variables["BUILD_DOCS"] = bool(self.options.build_docs)
        tc.variables["BUILD_TRANSATIONS"] = bool(self.options.build_translations)
        tc.variables["APP_USE_LIBFMT"] = self._use_libfmt
        tc.generate()
        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=None if self._run_tests else "src")
        cmake.build()
        if self._run_tests:
            cmake.test()

    def package_id(self):
        self.info.header_only()

    def package(self):
        # copy(self,
        #     "LICENSE",
        #     self.source_folder,
        #       os.path.join(self.package_folder, "licenses"),
        #  )
        cmake = CMake(self)
        cmake.install()
        rmdir(os.path.join(self.package_folder, "lib", "cmake"))

    def package_info(self):
        compiler = self.settings.compiler

        # core
        self.cpp_info.components["core"].requires = ["spdlog::spdlog"]
        self.cpp_info.components["core"].requires = ["CLI11::CLI11"]
        self.cpp_info.components["core"].includedirs = ["include"]
        if compiler == "Visual Studio":
            self.cpp_info.components["core"].cxxflags = ["/utf-8"]

        if self._use_range_v3:
            self.cpp_info.components["core"].requires.append("range-v3::range-v3")

        if self.settings.os == "Macos":
            self.cpp_info.frameworkdirs.append(os.path.join(self.package_folder, 'lib'))

        # rest

        # self.cpp_info.includedirs = ['include']  # Ordered list of include paths
        # self.cpp_info.libs = ['dena_library']  # The libs to link against
        # self.cpp_info.system_libs = []  # System libs to link against
        # self.cpp_info.libdirs = ['lib']  # Directories where libraries can be found
        # self.cpp_info.resdirs = ['res']  # Directories where resources, data, etc. can be found
        # Directories where executables and shared libs can be found
        self.cpp_info.bindirs = ["bin"]
        # self.cpp_info.srcdirs = []  # Directories where sources can be found (debugging, reusing sources)
        # self.cpp_info.build_modules = {}  # Build system utility module files
        # self.cpp_info.defines = []  # preprocessor definitions
        # self.cpp_info.cflags = []  # pure C flags
        # self.cpp_info.cxxflags = []  # C++ compilation flags
        # self.cpp_info.sharedlinkflags = []  # linker flags
        # self.cpp_info.exelinkflags = []  # linker flags
        # self.cpp_info.components  # Dictionary with the different components a package may have
        # self.cpp_info.requires = None  # List of components from requirements

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
        self.copy("*.so*", dst="lib", src="lib")
        self.copy("*", dst="libexec", src="libexec")
        self.copy("*", dst="bin/archdatadir/plugins", src="bin/archdatadir/plugins")
        self.copy("*", dst="bin/archdatadir/qml", src="bin/archdatadir/qml")
        self.copy("*", dst="bin/archdatadir/libexec", src="bin/archdatadir/libexec")
        self.copy("*", dst="bin/datadir/translations", src="bin/datadir/translations")
        self.copy("*", dst="resources", src="resources")
        self.copy("license*", dst="licenses", folder=True, ignore_case=True)
