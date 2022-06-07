from setuptools import setup
from setuptools import find_packages


with open('README.md', 'r') as fh:
    long_description = fh.read()


def reqs_parse(path):
    with open(path) as f:
        return f.read().splitlines()


install_reqs = reqs_parse('requirements.txt')
found_packages = find_packages(exclude=['tests', 'tests.*'])

setup(
    name='iraty',
    version='1.0.0',
    license='GPL3',
    author='cipres',
    url='https://gitlab.com/cipres/iraty',
    description='iraty',
    long_description=long_description,
    include_package_data=True,
    packages=found_packages,
    install_requires=install_reqs,
    entry_points={
        'console_scripts': [
            'iraty = iraty.entrypoint:run'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Topic :: System :: Filesystems',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    keywords=[
        'yaml',
        'dweb',
        'html',
        'ipfs'
    ]
)
