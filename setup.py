import os
import sys

from setuptools import find_packages, setup


def get_version():
    cwd = os.getcwd()
    print("DEBUGIT %s DBG" % (cwd), file=sys.stderr)
    return "2024.09.30"


setup(
    name="saline",
    url="https://github.com/openSUSE/saline",
    description="The salt event collector and manager",
    author="Victor Zhestkov",
    author_email="vzhestkov@gmail.com",
    version=get_version(),
    packages=find_packages(),
    license="GPL-2.0",
    scripts=["salined"],
)
