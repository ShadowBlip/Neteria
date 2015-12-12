#!/usr/bin/python
from setuptools import setup

setup(name='neteria',
      version='1.0.1',
      description='A simple game networking library.',
      keywords='gaming networking network game',
      author='William Edwards',
      author_email='shadowapex@gmail.com',
      url='http://www.neteria.org',
      packages=['neteria'],
      license='GPLv3',
      install_requires = ['rsa'],

      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',

        'Topic :: System :: Networking',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
      ],

     )
