"""
SimplyFire is a customizable analysis software for electrophysiologists.
It is written in Python.

SimplyFire can be downloaded from TestPyPI as follows:

pip install -i https://test.pypi.org/simple/ simplyfirebeta

To run the software from command line, use script:

py -m simplyfire

The software is currently under pre-release.
The package will be made available on PyPI once a stable-release is ready.

"""
from setuptools import setup, find_packages
with open('README.md') as readme_file:
    readme = readme_file.read()

setup(
    name='simplyfirebeta',
    version='3.0.2b0',
    author='Megumi Mori',
    description='Customizable electrophysiology analysis software',
    long_description=readme,
    url="https://github.com/megumi-mori/SimplyFire-beta",
    pakage_dir={'simplyfire':'simplyfire'},
    packages = find_packages(),
    entry_points={
        'console_scripts': [
            'simplyfire = simplyfire.__main__:simplyfire'
        ]
    },
    include_package_data = True,
    install_requires=[
        'numpy>=1.22.0',
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
    python_requires = '>=3.10'
)