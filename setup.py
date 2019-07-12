from setuptools import setup

setup(name='metastable-playground',
      version='0.1',
      description='Physical Unclonable Function (PUF) experiments',
      url='https://github.com/DurandA/metastable-playground',
      author='Arnaud Durand',
      author_email='arnaud.durand@unifr.ch',
      packages=['metastable'],
      install_requires=[
          'migen',
          'litex'
      ],
      zip_safe=False)

