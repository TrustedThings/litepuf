from setuptools import setup

setup(name='litepuf',
      version='0.2',
      description='Physical Unclonable Function (PUF) experiments',
      url='https://github.com/TrustedThings/litepuf',
      author='Arnaud Durand',
      author_email='arnaud.durand@unifr.ch',
      packages=['metastable'],
      install_requires=[
          'migen',
          'litex'
      ],
      zip_safe=False)
