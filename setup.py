import os
from setuptools import setup, find_packages


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read().strip()


setup(
    name='Tensorplex',
    version='0.1',
    author='Jim Fan',
    url='http://github.com/StanfordVL/Tensorplex',
    description='Distributed wrapper for Tensorboard',
    # long_description=read('README.rst'),
    keywords=['Machine Learning',
              'Distributed Computing'],
    license='GPLv3',
    packages=[
        package for package in find_packages() if package.startswith("tensorplex")
    ],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Environment :: Console",
        "Programming Language :: Python :: 3"
    ],
    include_package_data=True,
    zip_safe=False
)
