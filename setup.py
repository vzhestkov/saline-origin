from distutils.core import setup

setup(
    name="saline",
    url="https://github.com/vzhestkov/saline",
    description="The salt event collector and manager",
    author="Victor Zhestkov",
    author_email="vzhestkov@gmail.com",
    version="2023.04.11",
    packages=["saline", "saline.config", "saline.data"],
    license="GPL-2.0",
    scripts=["salined"],
)
