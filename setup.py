from setuptools import find_packages, setup


setup(
    name="saline",
    url="https://github.com/vzhestkov/saline",
    description="The salt event collector and manager",
    author="Victor Zhestkov",
    author_email="vzhestkov@gmail.com",
    version="2024.09.30",
    packages=find_packages(),
    license="GPL-2.0",
    scripts=["salined"],
)
