"""
SimplyFire is a customizable analysis software for electrophysiologists.
It is written in Python.

SimplyFire can be downloaded from TestPyPI as follows:

pip install -i https://test.pypi.org/simple/simplyfire

To run the software from command line, use script:

py -m simplyfire

The software is currently under pre-release.
The package will be made available on PyPI once a stable-release is ready.

------
SimplyFire - Customizable analysis of electrophysiology data
Copyright (C) 2022 Megumi Mori
This program comes with ABSOLUTELY NO WARRANTY

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from setuptools import setup, find_packages
with open('README.md') as readme_file:
    readme = readme_file.read()

setup(
    name='simplyfire',
    version='0.6.0',
    author='Megumi Mori, Andrew Rosko',
    description='Customizable electrophysiology analysis software',
    long_description=readme,
    long_description_content_type='text/markdown',
    url="https://simplyfire.readthedocs.io/",
    pakage_dir={'simplyfire':'simplyfire'},
    packages = find_packages(),
    entry_points={
        'console_scripts': [
            'simplyfire = simplyfire.__main__:simplyfire'
        ]
    },
    include_package_data = True,
    install_requires=[
        'numpy>=1.21.5',
        'pandas>=1.3.5',
        'matplotlib>=3.5.1',
        'scipy>=1.7.3',
        'pyyaml>=6.0',
        'pyabf>=2.3.5',
        'packaging'
    ],
    license='GNU General Public License v3',
    zip_safe = False,
    keywords = ['neuroscience', 'analysis', 'electrophysiology', 'gui-application'],
    lincense='GPLv3',
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows'
    ],
    python_requires = '>=3.8'
)
