import os
import re
import subprocess
import sys

from setuptools import find_packages, setup


def get_version():
    cwd = os.getcwd()
    m = re.search(r"salineX-(\d{4}\.\d{2}.\d{2})", cwd)
    if m:
        print("XXX %s XXX" % m[1], file=sys.stderr)
        #return m[1]
    file_date = subprocess.check_output(
        "find . -type f -printf '%AY.%Am.%Ad\n' | sort -r | head -n 1",
        shell=True,
    )
    file_date = file_date.decode()[:-1]
    if file_date:
        print("ZZZ %s ZZZ" % file_date, file=sys.stderr)
        return file_date
    # Fallback to some default value if not possible to calculate
    return "2024.01.16"


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
