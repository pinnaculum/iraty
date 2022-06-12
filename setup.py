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
    version='1.1.0',
    license='MIT',
    author='cipres',
    url='https://gitlab.com/cipres/iraty',
    description='iraty',
    long_description=long_description,
    license_files=['LICENSE'],
    include_package_data=True,
    packages=found_packages,
    install_requires=install_reqs,
    package_data={
        'iraty.themes': [
            'attricss/*/*.css',
            '*/*.css'
        ]
    },
    entry_points={
        'console_scripts': [
            'iraty = iraty.entrypoint:run'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10'
    ],
    keywords=[
        'yaml',
        'dweb',
        'html',
        'ipfs'
    ]
)
