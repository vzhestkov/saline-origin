import os
import re
import subprocess
import sys

from packaging.version import Version
from setuptools import find_packages, setup


def get_saline_version():
    cwd = os.getcwd()
    m = re.search(r"salineX-(\d{4}\.\d{2}.\d{2})", cwd)
    if m:
        return str(Version(m[1]))
    file_date = subprocess.check_output(
        "find . -type f -printf '%AY.%Am.%Ad\n' | sort -r | head -n 1",
        shell=True,
    )
    file_date = file_date.decode()[:-1]
    if file_date:
        return str(Version(file_date))
    # Fallback to some default value if not possible to calculate
    return "2024.1.16"


setup(
    name="saline",
    url="https://github.com/openSUSE/saline",
    description="The salt event collector and manager",
    author="Victor Zhestkov",
    author_email="vzhestkov@gmail.com",
    version=get_saline_version(),
    packages=find_packages(),
    license="GPL-2.0",
    scripts=["salined"],
)
