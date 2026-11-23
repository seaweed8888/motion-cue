from pathlib import Path
import os
import subprocess
import sys
from setuptools._distutils.ccompiler import new_compiler

ROOT = Path(__file__).resolve().parents[1]


def compile_cpp(directory, source, files=(), includes=()):
    source_path = directory/"check.cpp"
    source_path.write_text(source)
    compiler = new_compiler()
    objects = compiler.compile([str(source_path), *[str(ROOT/f) for f in files]],
        output_dir=str(directory), include_dirs=[str(ROOT/"firmware/include"), *map(str,includes)],
        extra_postargs=["/std:c++17", "/EHsc"] if sys.platform == "win32" else ["-std=c++17"])
    executable = directory/("check.exe" if os.name == "nt" else "check")
    compiler.link_executable(objects, str(executable), target_lang="c++")
    return executable


def run(executable, samples):
    text = "\n".join(" ".join(map(str,row)) for row in samples)
    return subprocess.check_output([str(executable)], input=text, text=True)
